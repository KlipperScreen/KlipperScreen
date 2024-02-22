#*********************************
# Lulzbot KlipperScreen Main Menu
# By Carl Smith  2024 - FAME3D  
#*********************************

import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from panels.menu import Panel as MenuPanel

class Panel(MenuPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title, items)
        self.main_menu = Gtk.Grid()
        self.main_menu.set_hexpand(True)
        self.main_menu.set_vexpand(True)
        scroll = self._gtk.ScrolledWindow()

        logging.info("### Making Lulzbot MainMenu")

        # Build new top row live extruder temp, bed temp, and fan buttons.  Buttons are defined here 
        # rather than in create_top_panel so they can be seen by the update routine
        self.ext_temp = self._gtk.Button('nozzle1', "°C", "color1", self.bts * 1.5, Gtk.PositionType.LEFT, 1)
        self.bed_temp = self._gtk.Button('bed', "°C", "color2", self.bts * 1.3, Gtk.PositionType.LEFT, 1)
        self.fan_spd  = self._gtk.Button('fan', "%", "color3", self.bts * 1.5, Gtk.PositionType.LEFT, 1)
        self.top_panel = self.create_top_panel()
        self.main_menu.attach(self.top_panel, 0, 0, 2, 1)
        
        self.labels['menu'] = self.arrangeMenuItems(items, 4, True)
        scroll.add(self.labels['menu'])
        self.main_menu.attach(scroll, 0, 1, 2, 2)
        self.content.add(self.main_menu)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        self.update_top_panel()

    def create_top_panel(self):
        #Buttons are defined in the init so they can be seen by the update routine
        
        self.ext_temp.connect("clicked", self.menu_item_clicked, {"name": "Temperature", "panel": "temperature"})
        self.bed_temp.connect("clicked", self.menu_item_clicked, {"name": "Temperature", "panel": "temperature"})
        self.fan_spd.connect("clicked", self.menu_item_clicked, {"name": "Fan", "panel": "fan"})

        self.ext_temp.get_style_context().add_class("buttons_main_top")
        self.bed_temp.get_style_context().add_class("buttons_main_top")
        self.fan_spd.get_style_context().add_class("buttons_main_top")

        top = self._gtk.HomogeneousGrid()
        top.set_property("height-request", 80)
        top.set_vexpand(False)
        top.set_margin_bottom(10)
        top.attach(self.ext_temp, 0, 0, 1, 1)
        top.attach(self.bed_temp, 1, 0, 1, 1)
        top.attach(self.fan_spd,  2, 0, 1, 1)
        
        return top

    def update_top_panel(self):
        ext_temp = self._printer.get_dev_stat("extruder", "temperature")
        ext_target = self._printer.get_dev_stat("extruder", "target")
        ext_label = f"{int(ext_temp)} / {int(ext_target)}°C"

        bed_temp = self._printer.get_dev_stat("heater_bed", "temperature")
        bed_target = self._printer.get_dev_stat("heater_bed", "target")
        bed_label = f" {int(bed_temp)} / {int(bed_target)}°C"

        fs = self._printer.get_fan_speed("fan")
        fan_label = f" {float(fs) * 100:.0f}%"
        
        self.ext_temp.set_label(ext_label)
        self.bed_temp.set_label(bed_label)
        self.fan_spd.set_label(fan_label)
        return
