#!/usr/bin/python

import argparse
import gi
import gettext
import time
import threading

import json
import requests
import websocket
import importlib
import logging
import os
import re
import signal
import subprocess
import sys
import traceback


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from jinja2 import Environment, Template

from ks_includes import functions
from ks_includes.KlippyWebsocket import KlippyWebsocket
from ks_includes.KlippyRest import KlippyRest
from ks_includes.files import KlippyFiles
from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.printer import Printer
from ks_includes.wifi import WifiManager

from ks_includes.config import KlipperScreenConfig

PRINTER_BASE_STATUS_OBJECTS = [
    'bed_mesh',
    'idle_timeout',
    'configfile',
    'gcode_move',
    'fan',
    'toolhead',
    'virtual_sdcard',
    'print_stats',
    'heater_bed',
    'extruder',
    'pause_resume',
    'webhooks'
]

klipperscreendir = os.getcwd()

class KlipperScreen(Gtk.Window):
    """ Class for creating a screen for Klipper via HDMI """
    _cur_panels = []
    bed_temp_label = None
    connecting = False
    connected_printer = None
    currentPanel = None
    files = None
    filename = ""
    keyboard = None
    keyboard_height = 200
    last_update = {}
    load_panel = {}
    number_tools = 1
    panels = {}
    popup_message = None
    printer = None
    printer_select_callbacks = []
    printer_select_prepanel = None
    rtl_languages = ['he_il']
    subscriptions = []
    shutdown = True
    _ws = None

    def __init__(self, args, version):
        self.dpms_timeout = None
        self.version = version

        configfile = os.path.normpath(os.path.expanduser(args.configfile))

        self.lang = gettext.translation('KlipperScreen', localedir='ks_includes/locales', fallback=True)
        self._config = KlipperScreenConfig(configfile, self.lang, self)

        self.wifi = WifiManager()
        self.wifi.start()

        logging.debug("OS Language: %s" % os.getenv('LANG'))

        self.lang_ltr = True
        for lang in self.rtl_languages:
            if os.getenv('LANG').lower().startswith(lang):
                self.lang_ltr = False
                Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
                logging.debug("Enabling RTL mode")
                break

        _ = self.lang.gettext

        Gtk.Window.__init__(self)
        self.width = self._config.get_main_config().getint("width", Gdk.Screen.get_width(Gdk.Screen.get_default()))
        self.height = self._config.get_main_config().getint("height", Gdk.Screen.get_height(Gdk.Screen.get_default()))
        self.set_default_size(self.width, self.height)
        self.set_resizable(False)
        logging.info("Screen resolution: %sx%s" % (self.width, self.height))

        self.gtk = KlippyGtk(self.width, self.height)
        self.init_style()

        self.printer_initializing(_("Initializing"))

        self.set_screenblanking_timeout(self._config.get_main_config_option('screen_blanking'))

        # Move mouse to 0,0
        os.system("/usr/bin/xdotool mousemove 0 0")
        # Change cursor to blank
        if self._config.get_main_config().getboolean("show_cursor", fallback=False):
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.ARROW))
        else:
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.BLANK_CURSOR))

        printers = self._config.get_printers()
        logging.debug("Printers: %s" % printers)
        if len(printers) == 1:
            pname = list(self._config.get_printers()[0])[0]
            self.connect_printer(pname)
        else:
            self.show_panel("printer_select","printer_select","Printer Select", 2)

    def connect_printer_widget(self, widget, name):
        self.connect_printer(name)

    def connect_printer(self, name):
        _ = self.lang.gettext

        if self.connected_printer == name:
            if self.printer_select_prepanel != None:
                self.show_panel(self.printer_select_prepanel, "","", 2)
                self.printer_select_prepanel = None
            while len(self.printer_select_callbacks) > 0:
                i = self.printer_select_callbacks.pop(0)
                i()
            return

        self.printer_select_callbacks = []
        self.printer_select_prepanel = None

        if self.files is not None:
            self.files.stop()
            self.files = None

        for printer in self._config.get_printers():
            pname = list(printer)[0]

            if pname != name:
                continue
            data = printer[pname]
            break

        if self._ws is not None:
            self._ws.close()
        self.connecting = True

        logging.info("Connecting to printer: %s" % name)
        self.apiclient = KlippyRest(data["moonraker_host"], data["moonraker_port"], data["moonraker_api_key"])

        self.printer = Printer({
            "software_version": "Unknown"
        }, {
            'configfile': {
                'config': {}
            },
            'print_stats': {
                'state': 'disconnected'
            },
            'virtual_sdcard': {
                'is_active': False
            }
        })

        self._remove_all_panels()
        panels = list(self.panels)
        if len(self.subscriptions) > 0:
            self.subscriptions = []
        for panel in panels:
            del self.panels[panel]
        self.printer_initializing(_("Connecting to %s") % name)

        self.printer.set_callbacks({
            "disconnected": self.state_disconnected,
            "error": self.state_error,
            "paused": self.state_paused,
            "printing": self.state_printing,
            "ready": self.state_ready,
            "startup": self.state_startup,
            "shutdown": self.state_shutdown
        })

        powerdevs = self.apiclient.send_request("machine/device_power/devices")
        logging.debug("Found power devices: %s" % powerdevs)
        if powerdevs != False:
            self.printer.configure_power_devices(powerdevs['result'])
            self.panels['splash_screen'].show_restart_buttons()

        self._ws = KlippyWebsocket(self,
            {
                "on_connect": self.init_printer,
                "on_message": self._websocket_callback,
                "on_close": self.printer_initializing
            },
            data["moonraker_host"],
            data["moonraker_port"]
        )
        self._ws.initial_connect()
        self.connecting = False

        self.files = KlippyFiles(self)
        self.files.start()

        self.connected_printer = name
        logging.debug("Connected to printer: %s" % name)

    def ws_subscribe(self):
        requested_updates = {
            "objects": {
                "bed_mesh": ["profile_name","mesh_max","mesh_min","probed_matrix"],
                "configfile": ["config"],
                "fan": ["speed"],
                "gcode_move": ["extrude_factor","gcode_position","homing_origin","speed_factor"],
                "idle_timeout": ["state"],
                "pause_resume": ["is_paused"],
                "print_stats": ["print_duration","total_duration","filament_used","filename","state","message"],
                "toolhead": ["homed_axes","estimated_print_time","print_time","position","extruder"],
                "virtual_sdcard": ["file_position","is_active","progress"],
                "webhooks": ["state","state_message"]
            }
        }
        for extruder in self.printer.get_tools():
            requested_updates['objects'][extruder] = ["target","temperature","pressure_advance","smooth_time"]
        for h in self.printer.get_heaters():
            requested_updates['objects'][h] = ["target","temperature"]

        self._ws.klippy.object_subscription(requested_updates)

    def _load_panel(self, panel, *args):
        if not panel in self.load_panel:
            logging.debug("Loading panel: %s" % panel)
            panel_path = os.path.join(os.path.dirname(__file__), 'panels', "%s.py" % panel)
            logging.info("Panel path: %s" % panel_path)
            if not os.path.exists(panel_path):
                msg = f"Panel {panel} does not exist"
                logging.info(msg)
                raise Exception(msg)

            module = importlib.import_module("panels.%s" % panel)
            if not hasattr(module, "create_panel"):
                msg = f"Cannot locate create_panel function for {panel}"
                logging.info(msg)
                raise Exception(msg)
            self.load_panel[panel] = getattr(module, "create_panel")

        try:
            return self.load_panel[panel](*args)
        except Exception:
            msg = f"Unable to create panel {panel}"
            logging.exception(msg)
            raise Exception(msg)

    def show_panel(self, panel_name, type, title, remove=None, pop=True, **kwargs):
        if panel_name not in self.panels:
            self.panels[panel_name] = self._load_panel(type, self, title)

            try:
                if kwargs != {}:
                    self.panels[panel_name].initialize(panel_name, **kwargs)
                else:
                    self.panels[panel_name].initialize(panel_name)
            except:
                del self.panels[panel_name]
                logging.exception("Unable to load panel %s" % type)
                self.show_error_modal("Unable to load panel %s" % type)
                return

            if hasattr(self.panels[panel_name],"process_update"):
                self.panels[panel_name].process_update("notify_status_update", self.printer.get_data())

        try:
            if remove == 2:
                self._remove_all_panels()
            elif remove == 1:
                self._remove_current_panel(pop)

            logging.debug("Attaching panel %s" % panel_name)

            self.add(self.panels[panel_name].get())
            self.show_all()

            if hasattr(self.panels[panel_name],"activate"):
                self.panels[panel_name].activate()
                self.show_all()
        except:
            logging.exception("Error attaching panel")

        self._cur_panels.append(panel_name)
        logging.debug("Current panel hierarchy: %s", str(self._cur_panels))

    def show_popup_message(self, message):
        if self.popup_message != None:
            self.close_popup_message()

        box = Gtk.Box()
        box.get_style_context().add_class("message_popup")
        box.set_size_request(self.width, self.gtk.get_header_size())
        label = Gtk.Label()
        if "must home axis first" in message.lower():
            message = "Must home all axis first."
        label.set_text(message)

        close = Gtk.Button.new_with_label("X")
        close.set_can_focus(False)
        close.props.relief = Gtk.ReliefStyle.NONE
        close.connect("clicked", self.close_popup_message)

        box.pack_start(label, True, True, 0)
        box.pack_end(close, False, False, 0)
        box.set_halign(Gtk.Align.CENTER)

        cur_panel = self.panels[self._cur_panels[-1]]
        for i in ['back','estop','home']:
            if i in cur_panel.control:
                cur_panel.control[i].set_sensitive(False)
        cur_panel.get().put(box, 0,0)

        self.show_all()
        self.popup_message = box

        GLib.timeout_add(10000, self.close_popup_message)

        return False

    def close_popup_message(self, widget=None):
        if self.popup_message == None:
            return

        cur_panel = self.panels[self._cur_panels[-1]]
        for i in ['back','estop','home']:
            if i in cur_panel.control:
                cur_panel.control[i].set_sensitive(True)
        cur_panel.get().remove(self.popup_message)
        self.popup_message = None
        self.show_all()

    def show_error_modal(self, err):
        _ = self.lang.gettext
        logging.exception("Showing error modal: %s", err)

        buttons = [
            {"name":_("Go Back"),"response": Gtk.ResponseType.CANCEL}
        ]

        label = Gtk.Label()
        label.set_markup(("%s \n\n" % err) +
            _("Check /tmp/KlipperScreen.log for more information.\nPlease submit an issue on GitHub for help."))
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        dialog = self.gtk.Dialog(self,  buttons, label, self.error_modal_response)

    def error_modal_response(self, widget, response_id):
        widget.destroy()

    def init_style(self):
        style_provider = Gtk.CssProvider()


        css = open(klipperscreendir + "/styles/style.css")
        css_data = css.read()
        css.close()
        css_data = css_data.replace("KS_FONT_SIZE",str(self.gtk.get_font_size()))

        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css_data.encode())

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def is_printing(self):
        return self.printer.get_state() == "printing"

    def _go_to_submenu(self, widget, name):
        logging.info("#### Go to submenu " + str(name))
        #self._remove_current_panel(False)

        # Find current menu item
        panels = list(self._cur_panels)
        if "main_panel" in self._cur_panels:
            menu = "__main"
        elif "splash_screen" in self._cur_panels:
            menu = "__splashscreen"
        else:
            menu = "__print"

        logging.info("#### Menu " + str(menu))
        disname = self._config.get_menu_name(menu, name)
        menuitems = self._config.get_menu_items(menu, name)
        if len(menuitems) == 0:
            logging.info("No items in menu, returning.")
            return

        self.show_panel(self._cur_panels[-1] + '_' + name, "menu", disname, 1, False, display_name=disname,
            items=menuitems)

    def _remove_all_panels(self):
        while len(self._cur_panels) > 0:
            self._remove_current_panel(True, False)
        self.show_all()

    def _remove_current_panel(self, pop=True, show=True):
        if len(self._cur_panels) > 0:
            self.remove(self.panels[self._cur_panels[-1]].get())
            if pop == True:
                self._cur_panels.pop()
                if len(self._cur_panels) > 0:
                    self.add(self.panels[self._cur_panels[-1]].get())
                    if show == True:
                        self.show_all()

    def _menu_go_back (self, widget=None):
        logging.info("#### Menu go back")
        self.remove_keyboard()
        self._remove_current_panel()

    def _menu_go_home(self):
        logging.info("#### Menu go home")
        self.remove_keyboard()
        while len(self._cur_panels) > 1:
            self._remove_current_panel()

    def add_subscription (self, panel_name):
        add = True
        for sub in self.subscriptions:
            if sub == panel_name:
                return

        self.subscriptions.append(panel_name)

    def remove_subscription (self, panel_name):
        for i in range(len(self.subscriptions)):
            if self.subscriptions[i] == panel_name:
                self.subscriptions.pop(i)
                return

    def check_dpms_state(self):
        state = functions.get_DPMS_state()
        if state == functions.DPMS_State.Off and "screensaver" not in self._cur_panels:
            logging.info("### Creating screensaver panel")
            self.show_panel("screensaver", "screensaver", "Screen Saver", 1, False)
        elif state == functions.DPMS_State.On and "screensaver" in self._cur_panels:
            logging.info("### Remove screensaver panel")
            self._menu_go_back()
        return True

    def set_screenblanking_timeout(self, time):
        # Disable screen blanking
        os.system("xset -display :0 s off")
        os.system("xset -display :0 s noblank")

        if functions.dpms_loaded == False:
            logging.info("DPMS functions not loaded. Unable to protect on button click when DPMS is enabled.")


        logging.debug("Changing power save to: %s" % time)
        if time == "off":
            if self.dpms_timeout != None:
                GLib.source_remove(self.dpms_timeout)
                self.dpms_timeout = None
            os.system("xset -display :0 -dpms")
            return

        time = int(time)
        if time < 0:
            return
        os.system("xset -display :0 dpms 0 %s 0" % time)
        if self.dpms_timeout == None and functions.dpms_loaded == True:
            self.dpms_timeout = GLib.timeout_add(1000, self.check_dpms_state)

    def show_printer_select(self, widget=None):
        logging.debug("Saving panel: %s" % self._cur_panels[0])
        self.printer_select_prepanel = self._cur_panels[0]
        self.show_panel("printer_select","printer_select","Printer Select", 2)

    def state_disconnected(self):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_disconnected]
            return

        _ = self.lang.gettext
        logging.debug("### Going to disconnected")
        self.printer_initializing(_("Klipper has disconnected"))

    def state_error(self):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_error]
            return

        _ = self.lang.gettext
        msg = self.printer.get_stat("webhooks","state_message")
        if "FIRMWARE_RESTART" in msg:
            self.printer_initializing(
                _("Klipper has encountered an error.\nIssue a FIRMWARE_RESTART to attempt fixing the issue.")
            )
        elif "micro-controller" in msg:
            self.printer_initializing(
                _("Klipper has encountered an error with the micro-controller.\nPlease recompile and flash.")
            )
        else:
            self.printer_initializing(
                _("Klipper has encountered an error.")
            )

    def state_paused(self):
        if "job_status" not in self._cur_panels:
            self.printer_printing()

    def state_printing(self):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_printing]
            return

        if "job_status" not in self._cur_panels:
            self.printer_printing()

    def state_ready(self):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_ready]
            return

        # Do not return to main menu if completing a job, timeouts/user input will return
        if "job_status" in self._cur_panels or "main_menu" in self._cur_panels:
            return
        self.printer_ready()

    def state_startup(self):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_startup]
            return

        _ = self.lang.gettext
        self.printer_initializing(_("Klipper is attempting to start"))

    def state_shutdown(self):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_shutdown]
            return

        _ = self.lang.gettext
        self.printer_initializing(_("Klipper has shutdown"))

    def _websocket_callback(self, action, data):
        _ = self.lang.gettext

        if self.connecting == True:
            return

        if action == "notify_klippy_disconnected":
            logging.debug("Received notify_klippy_disconnected")
            self.printer.change_state("disconnected")
            return
        elif action == "notify_klippy_ready":
            self.printer.change_state("ready")
        elif action == "notify_status_update" and self.printer.get_state() != "shutdown":
            self.printer.process_update(data)
        elif action == "notify_filelist_changed":
            logging.debug("Filelist changed: %s", json.dumps(data,indent=2))
            #self.files.add_file()
        elif action == "notify_metadata_update":
            self.files.request_metadata(data['filename'])
        elif action == "notify_power_changed":
            logging.debug("Power status changed: %s", data)
            self.printer.process_power_update(data)
        elif self.printer.get_state() not in ["error","shutdown"] and action == "notify_gcode_response":
            if "Klipper state: Shutdown" in data:
                logging.debug("Shutdown in gcode response, changing state to shutdown")
                self.printer.change_state("shutdown")

            if not (data.startswith("B:") and
                re.search(r'B:[0-9\.]+\s/[0-9\.]+\sT[0-9]+:[0-9\.]+', data)):
                if data.startswith("!! "):
                    self.show_popup_message(data[3:])
                logging.debug(json.dumps([action, data], indent=2))

        if self._cur_panels[-1] in self.subscriptions:
            self.panels[self._cur_panels[-1]].process_update(action, data)

    def _confirm_send_action(self, widget, text, method, params={}):
        _ = self.lang.gettext

        buttons = [
            {"name":_("Continue"), "response": Gtk.ResponseType.OK},
            {"name":_("Cancel"),"response": Gtk.ResponseType.CANCEL}
        ]

        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(text)
            text = j2_temp.render()
        except:
            logging.debug("Error parsing jinja for confirm_send_action")

        label = Gtk.Label()
        label.set_markup(text)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        dialog = self.gtk.Dialog(self, buttons, label, self._confirm_send_action_response,  method, params)

    def _confirm_send_action_response(self, widget, response_id, method, params):
        if response_id == Gtk.ResponseType.OK:
            self._send_action(widget, method, params)

        widget.destroy()

    def _send_action(self, widget, method, params):
        self._ws.send_method(method, params)

    def printer_initializing(self, text=None):
        self.shutdown = True
        self.close_popup_message()
        self.show_panel('splash_screen',"splash_screen", "Splash Screen", 2)
        if text != None:
            self.panels['splash_screen'].update_text(text)
            self.panels['splash_screen'].show_restart_buttons()

    def init_printer(self):
        _ = self.lang.gettext

        printer_info = self.apiclient.get_printer_info()
        data = self.apiclient.send_request("printer/objects/query?" + "&".join(PRINTER_BASE_STATUS_OBJECTS))
        powerdevs = self.apiclient.send_request("machine/device_power/devices")
        data = data['result']['status']

        # Reinitialize printer, in case the printer was shut down and anything has changed.
        self.printer.reinit(printer_info['result'], data)
        self.ws_subscribe()

        if powerdevs != False:
            self.printer.configure_power_devices(powerdevs['result'])

    def printer_ready(self):
        _ = self.lang.gettext
        self.close_popup_message()
        # Force update to printer webhooks state in case the update is missed due to websocket subscribe not yet sent
        self.printer.process_update({"webhooks":{"state":"ready","state_message": "Printer is ready"}})
        self.show_panel('main_panel', "main_menu", _("Home"), 2,
            items=self._config.get_menu_items("__main"), extrudercount=self.printer.get_extruder_count())
        self.ws_subscribe()
        if "job_status" in self.panels:
            self.remove_subscription("job_status")
            del self.panels["job_status"]

    def printer_printing(self):
        self.close_popup_message()
        self.show_panel('job_status',"job_status", "Print Status", 2)

    def show_keyboard(self, widget=None):
        if self.keyboard is not None:
            return

        env = os.environ.copy()
        env["MB_KBD_CONFIG"] = "/home/pi/.matchbox/keyboard.xml"
        env["MB_KBD_CONFIG"] = "ks_includes/locales/keyboard.xml"
        p = subprocess.Popen(["matchbox-keyboard", "--xid"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env)
        #p = subprocess.Popen(["onboard", "--xid"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        xid = int(p.stdout.readline())
        logging.debug("XID %s" % xid)
        logging.debug("PID %s" % p.pid)
        keyboard = Gtk.Socket()
        #keyboard.connect("plug-added", self.plug_added)

        action_bar_width = self.gtk.get_action_bar_width()

        box = Gtk.VBox()
        box.set_size_request(self.width - action_bar_width, self.keyboard_height)
        box.add(keyboard)

        cur_panel = self.panels[self._cur_panels[-1]]
        #for i in ['back','estop','home']:
        #    if i in cur_panel.control:
        #        cur_panel.control[i].set_sensitive(False)
        cur_panel.get().put(box, action_bar_width, self.height - 200)
        self.show_all()
        keyboard.add_id(xid)
        keyboard.show()

        self.keyboard = {
            "box": box,
            "panel": cur_panel.get(),
            "process": p,
            "socket": keyboard
        }

    def remove_keyboard(self, widget=None):
        if self.keyboard is None:
            return

        self.keyboard['panel'].remove(self.keyboard['box'])
        os.kill(self.keyboard['process'].pid, signal.SIGTERM)
        self.keyboard = None

def main():

    version = functions.get_software_version()
    parser = argparse.ArgumentParser(description="KlipperScreen - A GUI for Klipper")
    parser.add_argument(
        "-c","--configfile", default="~/KlipperScreen.conf", metavar='<configfile>',
        help="Location of KlipperScreen configuration file"
    )
    parser.add_argument(
        "-l","--logfile", default="/tmp/KlipperScreen.log", metavar='<logfile>',
        help="Location of KlipperScreen logfile output"
    )
    args = parser.parse_args()

    functions.setup_logging(
        os.path.normpath(os.path.expanduser(args.logfile)),
        version
    )

    logging.info("KlipperScreen version: %s" % version)


    win = KlipperScreen(args, version)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    try:
        main()
    except:
        logging.exception("Fatal error in main loop")
