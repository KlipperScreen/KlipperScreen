import logging
import logging.handlers
import os
import re
import subprocess
import sys
import threading
import time
import traceback
from queue import SimpleQueue as Queue

import ctypes
import struct

dpms_loaded = False
try:
    ctypes.cdll.LoadLibrary('libXext.so.6')
    libXext = ctypes.CDLL('libXext.so.6')

    class DPMS_State:
        Fail = -1
        On = 0
        Standby = 1
        Suspend = 2
        Off = 3

    def get_DPMS_state(display_name_in_byte_string=b':0'):
        state = DPMS_State.Fail
        if not isinstance(display_name_in_byte_string, bytes):
            raise TypeError
        display_name = ctypes.c_char_p()
        display_name.value = display_name_in_byte_string
        libXext.XOpenDisplay.restype = ctypes.c_void_p
        display = ctypes.c_void_p(libXext.XOpenDisplay(display_name))
        dummy1_i_p = ctypes.create_string_buffer(8)
        dummy2_i_p = ctypes.create_string_buffer(8)
        if display.value:
            if libXext.DPMSQueryExtension(display, dummy1_i_p, dummy2_i_p) \
                    and libXext.DPMSCapable(display):
                onoff_p = ctypes.create_string_buffer(1)
                state_p = ctypes.create_string_buffer(2)
                if libXext.DPMSInfo(display, state_p, onoff_p):
                    onoff = struct.unpack('B', onoff_p.raw)[0]
                    if onoff:
                        state = struct.unpack('H', state_p.raw)[0]
            libXext.XCloseDisplay(display)
        return state

    dpms_loaded = True
except Exception:
    pass


def get_network_interfaces():
    stream = os.popen("ip addr | grep ^'[0-9]' | cut -d ' ' -f 2 | grep -o '[a-zA-Z0-9\\.]*'")
    return [i for i in stream.read().strip().split('\n') if not i.startswith('lo')]


def get_wireless_interfaces():
    p = subprocess.Popen(["which", "iwconfig"], stdout=subprocess.PIPE)

    while p.poll() is None:
        time.sleep(.1)
    if p.poll() != 0:
        return None

    try:
        p = subprocess.Popen(["iwconfig"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = p.stdout.read().decode('ascii').split('\n')
    except Exception as e:
        logging.critical(e, exc_info=True)
        logging.info("Error with running iwconfig command")
        return None
    interfaces = []
    for line in result:
        match = re.search('^(\\S+)\\s+.*$', line)
        if match:
            interfaces.append(match[1])

    return interfaces


def get_software_version():
    prog = ('git', '-C', os.path.dirname(__file__), 'describe', '--always',
            '--tags', '--long', '--dirty')
    try:
        process = subprocess.Popen(prog, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        ver, err = process.communicate()
        retcode = process.wait()
        if retcode == 0:
            version = ver.strip()
            if isinstance(version, bytes):
                version = version.decode()
            return version
        else:
            logging.debug(f"Error getting git version: {err}")
    except OSError:
        logging.exception("Error runing git describe")
    return "?"


def patch_threading_excepthook():
    """Installs our exception handler into the threading modules Thread object
    Inspired by https://bugs.python.org/issue1230540
    """
    old_init = threading.Thread.__init__

    def new_init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        old_run = self.run

        def run_with_excepthook(*args, **kwargs):
            try:
                old_run(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                sys.excepthook(*sys.exc_info(), thread_identifier=threading.get_ident())

        self.run = run_with_excepthook

    threading.Thread.__init__ = new_init


# Rotating file handler based on Klipper and Moonraker's implementation
class KlipperScreenLoggingHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, software_version, filename, **kwargs):
        super(KlipperScreenLoggingHandler, self).__init__(filename, **kwargs)
        self.rollover_info = {
            'header': f"{'-' * 20}KlipperScreen Log Start{'-' * 20}",
            'version': f"Git Version: {software_version}",
        }
        lines = [line for line in self.rollover_info.values() if line]
        if self.stream is not None:
            self.stream.write("\n".join(lines) + "\n")

    def set_rollover_info(self, name, item):
        self.rollover_info[name] = item

    def doRollover(self):
        super(KlipperScreenLoggingHandler, self).doRollover()
        lines = [line for line in self.rollover_info.values() if line]
        if self.stream is not None:
            self.stream.write("\n".join(lines) + "\n")


# Logging based on Arksine's logging setup
def setup_logging(log_file, software_version):
    root_logger = logging.getLogger()
    queue = Queue()
    queue_handler = logging.handlers.QueueHandler(queue)
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(logging.DEBUG)

    stdout_hdlr = logging.StreamHandler(sys.stdout)
    stdout_fmt = logging.Formatter(
        '%(asctime)s [%(filename)s:%(funcName)s()] - %(message)s')
    stdout_hdlr.setFormatter(stdout_fmt)
    fh = listener = None
    try:
        fh = KlipperScreenLoggingHandler(software_version, log_file, maxBytes=8000000, backupCount=1)
        formatter = logging.Formatter('%(asctime)s [%(filename)s:%(funcName)s()] - %(message)s')
        fh.setFormatter(formatter)
        listener = logging.handlers.QueueListener(queue, fh, stdout_hdlr)
    except Exception as e:
        print(
            f"Unable to create log file at '{os.path.normpath(log_file)}'.\n"
            f"Make sure that the folder '{os.path.dirname(log_file)}' exists\n"
            f"and KlipperScreen has Read/Write access to the folder.\n"
            f"{e}\n"
        )
    if listener is None:
        listener = logging.handlers.QueueListener(queue, stdout_hdlr)
    listener.start()

    def logging_exception_handler(ex_type, value, tb, thread_identifier=None):
        logging.exception(
            f'Uncaught exception {ex_type}: {value}\n'
            f'Traceback: {traceback.format_tb(tb)}'
        )

    sys.excepthook = logging_exception_handler
    logging.captureWarnings(True)

    return listener, fh
