import logging
import logging.handlers
import os
import subprocess
import sys
import traceback
from queue import SimpleQueue as Queue



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

# Timed rotating file handler based on Klipper and Moonraker's implementation
class KlipperScreenLoggingHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, software_version, filename, **kwargs):
        super(KlipperScreenLoggingHandler, self).__init__(filename, **kwargs)
        self.rollover_info = {
            'header': f"{'-'*20}KlipperScreen Log Start{'-'*20}",
            'version': f"Git Version: {software_version}",
        }
        lines = [line for line in self.rollover_info.values() if line]
        if self.stream is not None:
            self.stream.write("\n".join(lines) + "\n")

    def set_rollover_info(self, name, item):
        self.rollover_info[name] = item

    def doRollover(self):
        super(MoonrakerLoggingHandler, self).doRollover()
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

    fh = None
    if log_file:
        fh = KlipperScreenLoggingHandler(software_version, log_file, when='midnight', backupCount=2)
        formatter = logging.Formatter(
            '%(asctime)s [%(filename)s:%(funcName)s()] - %(message)s')
        fh.setFormatter(formatter)
        listener = logging.handlers.QueueListener(
            queue, fh, stdout_hdlr)
    else:
        listener = logging.handlers.QueueListener(
            queue, stdout_hdlr)
    listener.start()

    def logging_exception_handler(type, value, tb):
        logging.exception("Uncaught exception %s: %s\nTraceback: %s" % (type, value, "\n".join(traceback.format_tb(tb))))
    sys.excepthook = logging_exception_handler

    return listener, fh
