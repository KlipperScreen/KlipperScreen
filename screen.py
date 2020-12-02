#!/usr/bin/python

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
    currentPanel = None
    bed_temp_label = None
    number_tools = 1

    panels = {}
    load_panel = {}
    _cur_panels = []
    files = None
    filename = ""
    subscriptions = []
    last_update = {}
    shutdown = True
    printer = None

    def __init__(self):
        self._config = KlipperScreenConfig()
        self.init_style()
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
        self.lang = gettext.translation('KlipperScreen', localedir='ks_includes/locales')
        _ = self.lang.gettext

        self.apiclient = KlippyRest("127.0.0.1",7125)
        Gtk.Window.__init__(self)

        self.width = Gdk.Screen.get_width(Gdk.Screen.get_default())
        self.height = Gdk.Screen.get_height(Gdk.Screen.get_default())
        self.set_default_size(self.width, self.height)
        self.set_resizable(False)
        self.version = get_software_version()
        logger.info("KlipperScreen version: %s" % self.version)
        logger.info("Screen resolution: %sx%s" % (self.width, self.height))

        #self._load_panels()

        self.printer_initializing(_("Initializing"))

        self._ws = KlippyWebsocket(self, {
            "on_connect": self.init_printer,
            "on_message": self._websocket_callback,
            "on_close": self.printer_initializing
        })
        self._ws.connect()

        # Disable DPMS
        os.system("/usr/bin/xset -display :0 s off")
        os.system("/usr/bin/xset -display :0 -dpms")
        os.system("/usr/bin/xset -display :0 s noblank")

        return


    def ws_subscribe(self):
        requested_updates = {
            "objects": {
                "configfile": ["config"],
                "extruder": ["target","temperature","pressure_advance","smooth_time"],
                "fan": ["speed"],
                "gcode_move": ["homing_origin","extrude_factor","speed_factor"],
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
        label.get_style_context().add_class("text")

        dialog = KlippyGtk.Dialog(self,  buttons, label, self.error_modal_response)

    def error_modal_response(self, widget, response_id):
        widget.destroy()


    def init_style(self):
        style_provider = Gtk.CssProvider()
        style_provider.load_from_path(klipperscreendir + "/style.css")

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

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
        return

        grid = self.arrangeMenuItems(menu, 4)

        b = KlippyGtk.ButtonImage('back', 'Back')
        b.connect("clicked", self._menu_go_back)
        grid.attach(b, 4, 2, 1, 1)

        self._cur_panels.append(cur_item['name']) #str(cur_item['name']))
        self.panels[cur_item['name']] = grid
        self.add(self.panels[cur_item['name']])
        self.show_all()

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
                if "job_status" in self._cur_panels:
                    if active == False and paused == False:
                        self.printer_ready()
                else:
                    if active == True or paused == True:
                        self.printer_printing()
        elif action == "notify_filelist_changed":
            logger.debug("Filelist changed: %s", json.dumps(data,indent=2))
            #self.files.add_file()
        elif action == "notify_metadata_update":
            self.files.update_metadata(data['filename'])
        elif action == "notify_power_changed":
            logger.debug("Power status changed: %s", data)
            self.printer.process_power_update(data)
        elif self.shutdown == False and action == "notify_gcode_response":
            if "Klipper state: Shutdown" in data:
                self.shutdown == True
                self.printer_initializing(_("Klipper has shutdown"))

            if not (data.startswith("B:") and
                re.search(r'B:[0-9\.]+\s/[0-9\.]+\sT[0-9]+:[0-9\.]+', data)):
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
        label.get_style_context().add_class("text")

        dialog = KlippyGtk.Dialog(self, buttons, label, self._confirm_send_action_response,  method, params)

    def _confirm_send_action_response(self, widget, response_id, method, params):
        if response_id == Gtk.ResponseType.OK:
            self._send_action(widget, method, params)

        widget.destroy()

    def _send_action(self, widget, method, params):
        self._ws.send_method(method, params)

    def printer_initializing(self, text=None):
        self.shutdown = True
        self.show_panel('splash_screen',"splash_screen", "Splash Screen", 2)
        if text != None:
            self.panels['splash_screen'].update_text(text)
            self.panels['splash_screen'].show_restart_buttons()

    def init_printer(self):
        _ = self.lang.gettext
        self.shutdown = False

        status_objects = [
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

        if printer_info['result']['state'] == "shutdown":
            if "FIRMWARE_RESTART" in printer_info['result']['state_message']:
                self.printer_initializing(
                    _("Klipper has encountered an error.\nIssue a FIRMWARE_RESTART to attempt fixing the issue.")
                )
            else:
                self.printer_initializing(_("Klipper has shutdown"))
            return
        if (data['print_stats']['state'] == "printing" or data['print_stats']['state'] == "paused"):
            self.printer_printing()
            return
        self.printer_ready()

    def printer_ready(self):
        if self.shutdown == True:
            self.init_printer()
            return

        self.files.add_timeout()
        self.show_panel('main_panel', "main_menu", "Main Menu", 2, items=self._config.get_menu_items("__main"),
            extrudercount=self.printer.get_extruder_count())

    def printer_printing(self):
        self.ws_subscribe()
        self.files.remove_timeout()
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
