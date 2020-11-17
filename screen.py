#!/usr/bin/python

import gi
import time
import threading

import json
import requests
import websocket
import logging
import os
import re
import subprocess


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyWebsocket import KlippyWebsocket
from KlippyRest import KlippyRest
from files import KlippyFiles
from KlippyGtk import KlippyGtk
from printer import Printer

from ks_includes.config import KlipperScreenConfig

# Do this better in the future
from panels.screen_panel import *
from panels.bed_level import *
from panels.extrude import *
from panels.fan import *
from panels.fine_tune import *
from panels.job_status import *
from panels.main_menu import *
from panels.menu import *
from panels.move import *
from panels.network import *
from panels.preheat import *
from panels.print import *
from panels.splash_screen import *
from panels.system import *
from panels.temperature import *
from panels.zcalibrate import *

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

        self.apiclient = KlippyRest("127.0.0.1",7125)
        Gtk.Window.__init__(self)

        self.width = Gdk.Screen.get_width(Gdk.Screen.get_default())
        self.height = Gdk.Screen.get_height(Gdk.Screen.get_default())
        self.set_default_size(self.width, self.height)
        self.set_resizable(False)
        self.version = get_software_version()
        logger.info("KlipperScreen version: %s" % self.version)
        logger.info("Screen resolution: %sx%s" % (self.width, self.height))

        self.printer_initializing("Initializing")

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
                "print_stats": ["print_duration","total_duration","filament_used","filename","state","message"],
                "toolhead": ["homed_axes","estimated_print_time","print_time","position","extruder"],
                "virtual_sdcard": ["file_position","is_active","progress"],
                "webhooks": ["state","state_message"]
            }
        }
        self._ws.klippy.object_subscription(requested_updates)

    def show_panel(self, panel_name, type, remove=None, pop=True, **kwargs):
        if panel_name not in self.panels:
            try:
                if type == "SplashScreenPanel":
                    self.panels[panel_name] = SplashScreenPanel(self)
                elif type == "MainPanel":
                    self.panels[panel_name] = MainPanel(self)
                elif type == "menu":
                    self.panels[panel_name] = MenuPanel(self)
                elif type == "bed_level":
                    self.panels[panel_name] = BedLevelPanel(self)
                elif type == "extrude":
                    self.panels[panel_name] = ExtrudePanel(self)
                elif type == "finetune":
                    self.panels[panel_name] = FineTune(self)
                elif type == "JobStatusPanel":
                    self.panels[panel_name] = JobStatusPanel(self)
                elif type == "move":
                    self.panels[panel_name] = MovePanel(self)
                elif type == "network":
                    self.panels[panel_name] = NetworkPanel(self)
                elif type == "preheat":
                    self.panels[panel_name] = PreheatPanel(self)
                elif type == "print":
                    self.panels[panel_name] = PrintPanel(self)
                elif type == "temperature":
                    self.panels[panel_name] = TemperaturePanel(self)
                elif type == "fan":
                    self.panels[panel_name] = FanPanel(self)
                elif type == "system":
                    self.panels[panel_name] = SystemPanel(self)
                elif type == "zcalibrate":
                    self.panels[panel_name] = ZCalibratePanel(self)
                #Temporary for development
                else:
                    self.panels[panel_name] = MovePanel(self)
            except:
                self.show_error_modal("Unable to load panel %s" % panel_name)
                return

            try:
                if kwargs != {}:
                    self.panels[panel_name].initialize(panel_name, **kwargs)
                else:
                    self.panels[panel_name].initialize(panel_name)
            except:
                self.show_error_modal("Unable to load panel %s" % panel_name)
                return

            if hasattr(self.panels[panel_name],"process_update"):
                self.panels[panel_name].process_update(self.printer.get_data())

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
        logger.exception("Showing error modal: %s", err)
        dialog = Gtk.Dialog()
        dialog.set_default_size(self.width - 15, self.height - 15)
        dialog.set_resizable(False)
        dialog.set_transient_for(self)
        dialog.set_modal(True)

        dialog.add_button(button_text="Cancel", response_id=Gtk.ResponseType.CANCEL)
        dialog.connect("response", self.error_modal_response)
        dialog.get_style_context().add_class("dialog")

        content_area = dialog.get_content_area()
        content_area.set_margin_start(15)
        content_area.set_margin_end(15)
        content_area.set_margin_top(15)
        content_area.set_margin_bottom(15)

        label = Gtk.Label()
        label.set_markup(("%s \n\nCheck /tmp/KlipperScreen.log for more information.\nPlease submit an issue "
            + "on GitHub for help.") % err)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.get_style_context().add_class("text")

        grid = Gtk.Grid()
        grid.add(label)
        grid.set_size_request(self.width - 60, -1)
        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)

        content_area.add(grid)
        dialog.resize(self.width - 15, self.height - 15)
        dialog.show_all()

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
        #self.show_panel("_".join(self._cur_panels) + '_' + name, "menu", 1, False, menu=menu)

        menuitems = self._config.get_menu_items(menu, name)
        if len(menuitems) == 0:
            logger.info("No items in menu, returning.")
            return

        self.show_panel(self._cur_panels[-1] + '_' + name, "menu", 1, False, items=menuitems)
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
            self._remove_current_panel()



    def _remove_current_panel(self, pop=True):
        if len(self._cur_panels) > 0:
            self.remove(
                self.panels[
                    self._cur_panels[-1]
                ].get()
            )
            if pop == True:
                self._cur_panels.pop()
                if len(self._cur_panels) > 0:
                    self.add(self.panels[self._cur_panels[-1]].get())
                    self.show_all()

    def _menu_go_back (self, widget):
        logger.info("#### Menu go back")
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
        #print(json.dumps([action, data], indent=2))

        if action == "notify_klippy_disconnected":
            logger.info("### Going to disconnected state")
            self.printer_initializing("Klipper has shutdown")
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
                    self.printer_initializing("Klipper shutdown")
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
        elif self.shutdown == False and not (action == "notify_gcode_response" and data.startswith("B:")
                and re.search(r'B:[0-9\.]+\s/[0-9\.]+\sT[0-9]+:[0-9\.]+', data)):
            logger.debug(json.dumps([action, data], indent=2))

        for sub in self.subscriptions:
            self.panels[sub].process_update(data)


    def _send_action(self, widget, method, params):
        self._ws.send_method(method, params)

    def printer_initializing(self, text=None):
        self.shutdown = True
        self.show_panel('splash_screen',"SplashScreenPanel", 2)
        if text != None:
            self.panels['splash_screen'].update_text(text)
            self.panels['splash_screen'].show_restart_buttons()

    def init_printer(self):
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
        info = self.apiclient.get_printer_info()
        data = self.apiclient.send_request("printer/objects/query?" + "&".join(status_objects))
        if info == False or data == False:
            self.printer_initializing("Moonraker error")
            return
        data = data['result']['status']

        # Reinitialize printer, in case the printer was shut down and anything has changed.
        self.printer.__init__(data)
        self.ws_subscribe()

        if self.files == None:
            self.files = KlippyFiles(self)
        else:
            self.files.add_timeout()

        if info['result']['state'] == "shutdown":
            if "FIRMWARE_RESTART" in info['result']['state_message']:
                self.printer_initializing(
                    "Klipper has encountered an error. Issue a FIRMWARE_RESTART to attempt fixing the issue."
                )
            else:
                self.printer_initializing("Klippy is shutdown")
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
        self.show_panel('main_panel', "MainPanel", 2, items=self._config.get_menu_items("__main"), extrudercount=self.printer.get_extruder_count())

    def printer_printing(self):
        self.ws_subscribe()
        self.files.remove_timeout()
        self.show_panel('job_status',"JobStatusPanel", 2)

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
