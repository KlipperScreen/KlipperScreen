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
import subprocess


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from ks_includes.KlippyWebsocket import KlippyWebsocket
from ks_includes.KlippyRest import KlippyRest
from ks_includes.files import KlippyFiles
from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.printer import Printer

from ks_includes.config import KlipperScreenConfig

# Create logging
logger = logging.getLogger('KlipperScreen')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

fh = logging.FileHandler('/tmp/KlipperScreen.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)

ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

klipperscreendir = os.getcwd()
config = klipperscreendir + "/KlipperScreen.config"
logger.info("Config file: " + config)

class KlipperScreen(Gtk.Window):
    """ Class for creating a screen for Klipper via HDMI """
    _cur_panels = []
    bed_temp_label = None
    currentPanel = None
    files = None
    filename = ""
    last_update = {}
    load_panel = {}
    number_tools = 1
    panels = {}
    popup_message = None
    printer = None
    subscriptions = []
    shutdown = True

    def __init__(self):
        self.version = get_software_version()
        logger.info("KlipperScreen version: %s" % self.version)

        parser = argparse.ArgumentParser(description="KlipperScreen - A GUI for Klipper")
        parser.add_argument(
            "-c","--configfile", default="~/KlipperScreen.conf", metavar='<configfile>',
            help="Location of KlipperScreen configuration file"
        )
        args = parser.parse_args()
        configfile = os.path.normpath(os.path.expanduser(args.configfile))


        self._config = KlipperScreenConfig(configfile)
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
        self.lang = gettext.translation('KlipperScreen', localedir='ks_includes/locales', fallback=True)
        _ = self.lang.gettext

        self.apiclient = KlippyRest(self._config.get_main_config_option("moonraker_host"),
            self._config.get_main_config_option("moonraker_port"),
            self._config.get_main_config_option("moonraker_api_key", False))

        Gtk.Window.__init__(self)
        self.width = self._config.get_main_config().getint("width", Gdk.Screen.get_width(Gdk.Screen.get_default()))
        self.height = self._config.get_main_config().getint("height", Gdk.Screen.get_height(Gdk.Screen.get_default()))
        self.set_default_size(self.width, self.height)
        self.set_resizable(False)
        logger.info("Screen resolution: %sx%s" % (self.width, self.height))

        self.gtk = KlippyGtk(self.width, self.height)
        self.init_style()

        #self._load_panels()

        self.printer_initializing(_("Initializing"))

        self._ws = KlippyWebsocket(self,
            {
                "on_connect": self.init_printer,
                "on_message": self._websocket_callback,
                "on_close": self.printer_initializing
            },
            self._config.get_main_config_option("moonraker_host"),
            self._config.get_main_config_option("moonraker_port")
        )
        self._ws.initial_connect()

        # Disable DPMS
        os.system("/usr/bin/xset -display :0 s off")
        os.system("/usr/bin/xset -display :0 -dpms")
        os.system("/usr/bin/xset -display :0 s noblank")

        return


    def ws_subscribe(self):
        requested_updates = {
            "objects": {
                "bed_mesh": ["profile_name","mesh_max","mesh_min","probed_matrix"],
                "configfile": ["config"],
                "extruder": ["target","temperature","pressure_advance","smooth_time"],
                "fan": ["speed"],
                "gcode_move": ["extrude_factor","gcode_position","homing_origin","speed_factor"],
                "heater_bed": ["target","temperature"],
                "pause_resume": ["is_paused"],
                "print_stats": ["print_duration","total_duration","filament_used","filename","state","message"],
                "toolhead": ["homed_axes","estimated_print_time","print_time","position","extruder"],
                "virtual_sdcard": ["file_position","is_active","progress"],
                "webhooks": ["state","state_message"]
            }
        }
        self._ws.klippy.object_subscription(requested_updates)

    def _load_panel(self, panel, *args):
        if not panel in self.load_panel:
            logger.debug("Loading panel: %s" % panel)
            panel_path = os.path.join(os.path.dirname(__file__), 'panels', "%s.py" % panel)
            logger.info("Panel path: %s" % panel_path)
            if not os.path.exists(panel_path):
                msg = f"Panel {panel} does not exist"
                logger.info(msg)
                raise Exception(msg)

            module = importlib.import_module("panels.%s" % panel)
            if not hasattr(module, "create_panel"):
                msg = f"Cannot locate create_panel function for {panel}"
                logger.info(msg)
                raise Exception(msg)
            self.load_panel[panel] = getattr(module, "create_panel")

        try:
            return self.load_panel[panel](*args)
        except Exception:
            msg = f"Unable to create panel {panel}"
            logger.exception(msg)
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
                self.show_error_modal("Unable to load panel %s" % type)
                return

            if hasattr(self.panels[panel_name],"process_update"):
                self.panels[panel_name].process_update("notify_status_update", self.printer.get_data())

        if hasattr(self.panels[panel_name],"activate"):
            self.panels[panel_name].activate()

        if remove == 2:
            self._remove_all_panels()
        elif remove == 1:
            self._remove_current_panel(pop)

        self.add(self.panels[panel_name].get())
        self.show_all()
        self._cur_panels.append(panel_name)
        logger.debug("Current panel hierarchy: %s", str(self._cur_panels))

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
        logger.exception("Showing error modal: %s", err)

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
        #style_provider.load_from_path(klipperscreendir + "/style.css")

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
        return "job_status" in self._cur_panels

    def _go_to_submenu(self, widget, name):
        logger.info("#### Go to submenu " + str(name))
        #self._remove_current_panel(False)

        # Find current menu item
        panels = list(self._cur_panels)
        if "job_status" not in self._cur_panels:
            menu = "__main"
        else:
            menu = "__print"

        logger.info("#### Menu " + str(menu))
        disname = self._config.get_menu_name(menu, name)
        menuitems = self._config.get_menu_items(menu, name)
        if len(menuitems) == 0:
            logger.info("No items in menu, returning.")
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
        logger.info("#### Menu go back")
        self._remove_current_panel()

    def _menu_go_home(self):
        logger.info("#### Menu go home")
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

    def _websocket_callback(self, action, data):
        _ = self.lang.gettext
        #print(json.dumps([action, data], indent=2))

        if action == "notify_klippy_disconnected":
            logger.info("### Going to disconnected state")
            self.printer_initializing(_("Klipper has shutdown"))
            return
        elif action == "notify_klippy_ready":
            logger.info("### Going to ready state")
            self.init_printer()
        elif action == "notify_status_update" and self.shutdown == False:
            self.printer.process_update(data)
            if "webhooks" in data:
                print(json.dumps([action, data], indent=2))
            if "webhooks" in data and "state" in data['webhooks']:
                if data['webhooks']['state'] == "ready":
                    logger.info("### Going to ready state")
                    self.printer_ready()
                elif data['webhooks']['state'] == "shutdown":
                    self.shutdown == True
                    self.printer_initializing(_("Klipper has shutdown"))
            else:
                active = self.printer.get_stat('virtual_sdcard','is_active')
                paused = self.printer.get_stat('pause_resume','is_paused')
                if "job_status" not in self._cur_panels:
                    if active == True or paused == True:
                        self.printer_printing()
        elif action == "notify_filelist_changed":
            logger.debug("Filelist changed: %s", json.dumps(data,indent=2))
            #self.files.add_file()
        elif action == "notify_metadata_update":
            self.files.request_metadata(data['filename'])
        elif action == "notify_power_changed":
            logger.debug("Power status changed: %s", data)
            self.printer.process_power_update(data)
        elif self.shutdown == False and action == "notify_gcode_response":
            if "Klipper state: Shutdown" in data:
                self.shutdown == True
                self.printer_initializing(_("Klipper has shutdown"))

            if not (data.startswith("B:") and
                re.search(r'B:[0-9\.]+\s/[0-9\.]+\sT[0-9]+:[0-9\.]+', data)):
                if data.startswith("!! "):
                    self.show_popup_message(data[3:])
                logger.debug(json.dumps([action, data], indent=2))

        for sub in self.subscriptions:
            self.panels[sub].process_update(action, data)

    def _confirm_send_action(self, widget, text, method, params):
        _ = self.lang.gettext

        buttons = [
            {"name":_("Continue"), "response": Gtk.ResponseType.OK},
            {"name":_("Cancel"),"response": Gtk.ResponseType.CANCEL}
        ]

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
        self.shutdown = False

        status_objects = [
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
            'pause_resume'
        ]
        printer_info = self.apiclient.get_printer_info()
        data = self.apiclient.send_request("printer/objects/query?" + "&".join(status_objects))
        powerdevs = self.apiclient.send_request("machine/device_power/devices")
        if printer_info == False or data == False:
            self.printer_initializing(_("Moonraker error"))
            return
        data = data['result']['status']

        # Reinitialize printer, in case the printer was shut down and anything has changed.
        self.printer.__init__(printer_info['result'], data)
        self.ws_subscribe()

        if powerdevs != False:
            self.printer.configure_power_devices(powerdevs['result'])

        if self.files == None:
            self.files = KlippyFiles(self)
        else:
            self.files.add_timeout()

        if printer_info['result']['state'] in ("error","shutdown","startup"):
            if printer_info['result']['state'] == "startup":
                self.printer_initializing(_("Klipper is attempting to start"))
            elif printer_info['result']['state'] == "error":
                if "FIRMWARE_RESTART" in printer_info['result']['state_message']:
                    self.printer_initializing(
                        _("Klipper has encountered an error.\nIssue a FIRMWARE_RESTART to attempt fixing the issue.")
                    )
                elif "micro-controller" in printer_info['result']['state_message']:
                    self.printer_initializing(
                        _("Klipper has encountered an error with the micro-controller.\nPlease recompile and flash.")
                    )
                else:
                    self.printer_initializing(
                        _("Klipper has encountered an error.")
                    )
            else:
                self.printer_initializing(_("Klipper has shutdown"))
            return
        if (data['print_stats']['state'] == "printing" or data['print_stats']['state'] == "paused"):
            filename = self.printer.get_stat("print_stats","filename")
            if not self.files.file_metadata_exists(filename):
                self.files.request_metadata(filename)
            self.printer_printing()
            return
        self.printer_ready()

    def printer_ready(self):
        if self.shutdown == True:
            self.init_printer()
            return

        self.files.add_timeout()
        self.close_popup_message()
        self.show_panel('main_panel', "main_menu", "Main Menu", 2, items=self._config.get_menu_items("__main"),
            extrudercount=self.printer.get_extruder_count())
        if "job_status" in self.panels:
            self.remove_subscription("job_status")
            del self.panels["job_status"]

    def printer_printing(self):
        self.ws_subscribe()
        self.files.remove_timeout()
        self.close_popup_message()
        self.show_panel('job_status',"job_status", "Print Status", 2)

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
            logger.debug(f"Error getting git version: {err}")
    except OSError:
        logger.exception("Error runing git describe")
    return "?"

def main():

    win = KlipperScreen()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    try:
        main()
    except:
        logger.exception("Fatal error in main loop")
