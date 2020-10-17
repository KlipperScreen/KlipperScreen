#!/usr/bin/python

import gi
import time
import threading

import json
import requests
import websocket
import logging
import os
import asyncio


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyWebsocket import KlippyWebsocket
from KlippyRest import KlippyRest
from files import KlippyFiles
from KlippyGtk import KlippyGtk
from printer import Printer

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

logging.basicConfig(filename="/tmp/KlipperScreen.log", level=logging.INFO)

klipperscreendir = os.getcwd()
config = klipperscreendir + "/KlipperScreen.config"
logging.info("Config file: " + config)

class KlipperScreen(Gtk.Window):
    """ Class for creating a screen for Klipper via HDMI """
    currentPanel = None
    bed_temp_label = None
    number_tools = 1

    panels = {}
    _cur_panels = []
    filename = ""
    subscriptions = []
    last_update = {}
    shutdown = True
    printer = None

    def __init__(self):
        self.read_config()
        self.init_style()

        self.apiclient = KlippyRest("127.0.0.1",7125)
        Gtk.Window.__init__(self)

        self.set_default_size(Gdk.Screen.get_width(Gdk.Screen.get_default()), Gdk.Screen.get_height(Gdk.Screen.get_default()))
        self.set_resizable(False)
        logging.info(str(Gdk.Screen.get_width(Gdk.Screen.get_default()))+"x"+str(Gdk.Screen.get_height(Gdk.Screen.get_default())))

        self.printer_initializing("Connecting to Moonraker")

        ready = False

        try:
            info = self.apiclient.get_info()
        except Exception:
            return

        if info == False:
            return

        if not hasattr(self, "_ws"):
            self.create_websocket()

        if info['result']['state'] == "ready" and "M112" in info['result']['state_message']:
            print("Emergency stopped")
            self.printer_initializing("Shutdown due to Emergency Stop")

        status_objects = [
            'idle_timeout',
            'configfile',
            'toolhead',
            'virtual_sdcard',
            'print_stats',
            'heater_bed',
            'extruder',
            'pause_resume'
        ]
        r = requests.get("http://127.0.0.1:7125/printer/objects/query?" + "&".join(status_objects))

        requested_updates = {
            "toolhead": [],
            "virtual_sdcard": [],
            "print_stats": [],
            "heater_bed": [],
            "extruder": [],
            "configfile": []
        }

        #TODO: Check that we get good data
        data = json.loads(r.content)
        data = data['result']['status']
        for x in data:
            self.last_update[x] = data[x]

        self.printer_config = data['configfile']['config']
        #self.read_printer_config()
        self.printer = Printer(data)

        # Initialize target values. TODO: methodize this
        print (json.dumps(data, indent=2))
        self.printer.set_dev_stat("heater_bed", "target", data['heater_bed']['target'])
        self.printer.set_dev_stat("extruder", "target", data['extruder']['target'])

        print (info)
        if (data['print_stats']['state'] == "printing" or data['print_stats']['state'] == "paused"):
            self.printer_printing()
        elif info['result']['state'] == "ready":
            self.printer_ready()

        while (self._ws.is_connected() == False):
            print("### Main: Waiting for websocket")
            continue

        self.files = KlippyFiles(self)

        self._ws.klippy.object_subscription(requested_updates)



    def read_printer_config(self):
        logging.info("### Reading printer config")
        self.toolcount = 0
        self.extrudercount = 0
        for x in self.printer_config.keys():
            if x.startswith('extruder'):
                if x.startswith('extruder_stepper') or "shared_heater" in self.printer_config[x]:
                    self.toolcount += 1
                    continue
                self.extrudercount += 1

        logging.info("### Toolcount: " + str(self.toolcount) + " Heaters: " + str(self.extrudercount))

        self._printer = Printer(self.toolcount, self.extrudercount)

    def show_panel(self, panel_name, type, remove=None, pop=True, **kwargs):
        if remove == 2:
            self._remove_all_panels()
        elif remove == 1:
            self._remove_current_panel(pop)

        if panel_name not in self.panels:
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

            if kwargs != {}:
                print(type)
                self.panels[panel_name].initialize(panel_name, **kwargs)
            else:
                self.panels[panel_name].initialize(panel_name)

            if hasattr(self.panels[panel_name],"process_update"):
                self.panels[panel_name].process_update(self.last_update)

        self.add(self.panels[panel_name].get())
        self.show_all()
        self._cur_panels.append(panel_name)
        logging.info(self._cur_panels)


    def read_config (self):
        with open(config) as config_file:
            self._config = json.load(config_file)


    def init_style(self):
        style_provider = Gtk.CssProvider()
        style_provider.load_from_path(klipperscreendir + "/style.css")

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def create_websocket(self):
        self._ws = KlippyWebsocket(self, self._websocket_callback)
        self._ws.connect()
        self._curr = 0


    def _go_to_submenu(self, widget, name):
        logging.info("#### Go to submenu " + str(name))
        #self._remove_current_panel(False)

        # Find current menu item
        panels = list(self._cur_panels)
        if "job_status" not in self._cur_panels:
            cur_item = self._find_current_menu_item(name, self._config['mainmenu'], panels.pop(0))
            menu = cur_item['items']
        else:
            menu = self._config['printmenu']

        logging.info("#### Menu " + str(menu))
        #self.show_panel("_".join(self._cur_panels) + '_' + name, "menu", 1, False, menu=menu)

        print(menu)
        self.show_panel(self._cur_panels[-1] + '_' + name, "menu", 1, False, items=menu)
        return

        grid = self.arrangeMenuItems(menu, 4)

        b = KlippyGtk.ButtonImage('back', 'Back')
        b.connect("clicked", self._menu_go_back)
        grid.attach(b, 4, 2, 1, 1)

        self._cur_panels.append(cur_item['name']) #str(cur_item['name']))
        self.panels[cur_item['name']] = grid
        self.add(self.panels[cur_item['name']])
        self.show_all()



    def _find_current_menu_item(self, menu, items, names):
        for item in items:
            if item['name'] == menu:
                return item
        #TODO: Add error check

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
        logging.info("#### Menu go back")
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
        #print(json.dumps(data, indent=2))

        self.printer.process_update(data)

        if "webhooks" in data:
            print(data)


        if "webhooks" in data and "state" in data['webhooks']:
            if data['webhooks']['state'] == "shutdown":
                logging.info("### Going to disconnected state")
                self.printer_initializing("Klipper has shutdown")
            elif data['webhooks']['state'] == "ready":
                logging.info("### Going to ready state")
                self.printer_ready()
        else:
            active = self.printer.get_stat('virtual_sdcard','is_active')
            paused = self.printer.get_stat('pause_resume','is_paused')
            if "job_status" in self._cur_panels:
                if active == False and paused == False:
                    self.printer_ready()
            else:
                if active == True or paused == True:
                    self.printer_printing()




        if action == "notify_status_update":
            if "heater_bed" in data:
                d = data["heater_bed"]
                if "target" in d:
                    self.printer.set_dev_stat("heater_bed", "target", d["target"])
                if "temperature" in d:
                    self.printer.set_dev_stat("heater_bed", "temperature", d["temperature"])
            for x in self.printer.get_tools():
                if x in data:
                    d = data[x]
                    if "target" in d:
                        self.printer.set_dev_stat(x, "target", d["target"])
                    if "temperature" in d:
                        self.printer.set_dev_stat(x, "temperature", d["temperature"])

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

    def printer_ready(self):
        self.shutdown = False
        self.show_panel('main_panel', "MainPanel", 2, items=self._config['mainmenu'], extrudercount=self.printer.get_extruder_count())

    def printer_printing(self):
        self.show_panel('job_status',"JobStatusPanel", 2)

def main():
    log_file = ("/tmp/KlipperScreen.log")
    root_logger = logging.getLogger()

    win = KlipperScreen()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
