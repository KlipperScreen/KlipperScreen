# -*- coding: utf-8 -*-
import contextlib
import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango
from jinja2 import Environment
from datetime import datetime
from math import log

from ks_includes.screen_panel import ScreenPanel


class BasePanel(ScreenPanel):
    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)
        self.current_panel = None
        self.time_min = -1
        self.time_format = self._config.get_main_config().getboolean("24htime", True)
        self.time_update = None
        self.titlebar_name_type = None
        self.buttons_showing = {
            'back': not back,
            'macros_shortcut': False,
            'printer_select': False,
            'estop': False,
        }
        self.current_extruder = None
        # Action bar buttons
        self.control['back'] = self._gtk.ButtonImage('back', scale=1)
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = self._gtk.ButtonImage('main', scale=1)
        self.control['home'].connect("clicked", self.menu_return, True)

        if len(self._config.get_printers()) > 1:
            self.control['printer_select'] = self._gtk.ButtonImage('shuffle', scale=1)
            self.control['printer_select'].connect("clicked", self._screen.show_printer_select)

        self.control['macros_shortcut'] = self._gtk.ButtonImage('custom-script', scale=1)
        self.control['macros_shortcut'].connect("clicked", self.menu_item_clicked, "gcode_macros", {
            "name": "Macros",
            "panel": "gcode_macros"
        })

        self.control['estop'] = self._gtk.ButtonImage('emergency', scale=1)
        self.control['estop'].connect("clicked", self.emergency_stop)

        # Any action bar button should close the keyboard
        for item in self.control:
            self.control[item].connect("clicked", self._screen.remove_keyboard)

        # Action bar
        self.action_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        if self._screen.vertical_mode:
            self.action_bar.set_hexpand(True)
            self.action_bar.set_vexpand(False)
            self.action_bar.set_size_request(0, self._gtk.get_action_bar_height())
        else:
            self.action_bar.set_hexpand(False)
            self.action_bar.set_vexpand(True)
            self.action_bar.set_size_request(self._gtk.get_action_bar_width(), 0)

        self.action_bar.get_style_context().add_class('action_bar')
        self.action_bar.add(self.control['back'])
        self.action_bar.add(self.control['home'])
        if len(self._config.get_printers()) > 1:
            self.action_bar.add(self.control['printer_select'])
        self.show_macro_shortcut(self._config.get_main_config().getboolean('side_macro_shortcut', True))
        self.action_bar.add(self.control['estop'])

        # Titlebar

        # This box will be populated by show_heaters
        self.control['temp_box'] = Gtk.Box(spacing=10)

        self.titlelbl = Gtk.Label()
        self.titlelbl.set_hexpand(True)
        self.titlelbl.set_halign(Gtk.Align.CENTER)
        self.titlelbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_title(title)

        self.control['time'] = Gtk.Label("00:00 AM")
        self.control['time_box'] = Gtk.Box()
        self.control['time_box'].set_halign(Gtk.Align.END)
        self.control['time_box'].pack_end(self.control['time'], True, True, 10)

        self.titlebar = Gtk.Box(spacing=5)
        self.titlebar.set_size_request(0, self._gtk.get_titlebar_height())
        self.titlebar.set_valign(Gtk.Align.CENTER)
        self.titlebar.add(self.control['temp_box'])
        self.titlebar.add(self.titlelbl)
        self.titlebar.add(self.control['time_box'])

        # Main layout
        self.main_grid = Gtk.Grid()
        # To achieve rezisability this needs to be removed
        # The main issue is that currently the content doesn't expand correctly
        self.main_grid.set_size_request(self._screen.width, self._screen.height)

        if self._screen.vertical_mode:
            self.main_grid.attach(self.titlebar, 0, 0, 1, 1)
            self.main_grid.attach(self.content, 0, 1, 1, 1)
            self.main_grid.attach(self.action_bar, 0, 2, 1, 1)
            self.action_bar.set_orientation(orientation=Gtk.Orientation.HORIZONTAL)
        else:
            self.main_grid.attach(self.action_bar, 0, 0, 1, 2)
            self.action_bar.set_orientation(orientation=Gtk.Orientation.VERTICAL)
            self.main_grid.attach(self.titlebar, 1, 0, 1, 1)
            self.main_grid.attach(self.content, 1, 1, 1, 1)

        # Layout is and content are on screen_panel
        self.layout.add(self.main_grid)

    def initialize(self, panel_name):
        self.update_time()
        return

    def show_heaters(self, show=True):
        try:
            for child in self.control['temp_box'].get_children():
                self.control['temp_box'].remove(child)
            if not show or self._screen.printer.get_temp_store_devices() is None:
                return

            printer_cfg = self._config.get_printer_config(self._screen.connected_printer)
            if printer_cfg is not None:
                self.titlebar_name_type = printer_cfg.get("titlebar_name_type", None)
            else:
                self.titlebar_name_type = None
            logging.info(f"Titlebar name type: {self.titlebar_name_type}")

            img_size = self._gtk.img_scale * .5
            for device in self._screen.printer.get_temp_store_devices():
                self.labels[device] = Gtk.Label(label="100º")
                self.labels[device].set_ellipsize(Pango.EllipsizeMode.START)

                self.labels[f'{device}_box'] = Gtk.Box()
                icon = self.get_icon(device, img_size)
                if icon is not None:
                    self.labels[f'{device}_box'].pack_start(icon, False, False, 3)
                self.labels[f'{device}_box'].pack_start(self.labels[device], False, False, 0)

            # Limit the number of items according to resolution
            nlimit = int(round(log(self._screen.width, 10) * 5 - 10.5))

            n = 0
            if self._screen.printer.get_tools():
                self.current_extruder = self._screen.printer.get_stat("toolhead", "extruder")
                if self.current_extruder and f"{self.current_extruder}_box" in self.labels:
                    self.control['temp_box'].add(self.labels[f"{self.current_extruder}_box"])
                    n += 1

            if self._screen.printer.has_heated_bed():
                self.control['temp_box'].add(self.labels['heater_bed_box'])
                n += 1

            # Options in the config have priority
            if printer_cfg is not None:
                titlebar_items = printer_cfg.get("titlebar_items", None)
                if titlebar_items is not None:
                    titlebar_items = [str(i.strip()) for i in titlebar_items.split(',')]
                    logging.info(f"Titlebar items: {titlebar_items}")
                    for device in self._screen.printer.get_temp_store_devices():
                        # Users can fill the bar if they want
                        if n >= nlimit + 1:
                            break
                        name = device.split()[1] if len(device.split()) > 1 else device
                        for item in titlebar_items:
                            if name == item:
                                self.control['temp_box'].add(self.labels[f"{device}_box"])
                                n += 1
                                break

            # If there is enough space fill with heater_generic
            for device in self._screen.printer.get_temp_store_devices():
                if n >= nlimit:
                    break
                if device.startswith("heater_generic"):
                    self.control['temp_box'].add(self.labels[f"{device}_box"])
                    n += 1
            self.control['temp_box'].show_all()
        except Exception as e:
            logging.debug(f"Couldn't create heaters box: {e}")

    def get_icon(self, device, img_size):
        if device.startswith("extruder"):
            if self._screen.printer.extrudercount > 1:
                if device == "extruder":
                    device = "extruder0"
                return self._gtk.Image(f"extruder-{device[8:]}", img_size, img_size)
            return self._gtk.Image("extruder", img_size, img_size)
        elif device.startswith("heater_bed"):
            return self._gtk.Image("bed", img_size, img_size)
        # Extra items
        elif self.titlebar_name_type is not None:
            # The item has a name, do not use an icon
            return None
        elif device.startswith("temperature_fan"):
            return self._gtk.Image("fan", img_size, img_size)
        elif device.startswith("heater_generic"):
            return self._gtk.Image("heater", img_size, img_size)
        else:
            return self._gtk.Image("heat-up", img_size, img_size)

    def activate(self):
        if self.time_update is None:
            self.time_update = GLib.timeout_add_seconds(1, self.update_time)

    def add_content(self, panel):
        self.current_panel = panel
        self.set_title(panel.get_title())
        self.content.add(panel.get_content())

    def back(self, widget):
        if self.current_panel is None:
            return

        self._screen.remove_keyboard()

        if hasattr(self.current_panel, "back") \
                and not self.current_panel.back() \
                or not hasattr(self.current_panel, "back"):
            self._screen._menu_go_back()

    def process_update(self, action, data):
        if action != "notify_status_update" or self._screen.printer is None:
            return

        devices = self._screen.printer.get_temp_store_devices()
        if devices is not None:
            for device in devices:
                temp = self._screen.printer.get_dev_stat(device, "temperature")
                if temp is not None and device in self.labels:
                    name = ""
                    if not (device.startswith("extruder") or device.startswith("heater_bed")):
                        if self.titlebar_name_type == "full":
                            name = device.split()[1] if len(device.split()) > 1 else device
                            name = f'{name.capitalize().replace("_", " ")}: '
                        elif self.titlebar_name_type == "short":
                            name = device.split()[1] if len(device.split()) > 1 else device
                            name = f"{name[:1].upper()}: "
                    self.labels[device].set_label(f"{name}{int(temp)}°")

        with contextlib.suppress(KeyError):
            if data["toolhead"]["extruder"] != self.current_extruder:
                self.control['temp_box'].remove(self.labels[f"{self.current_extruder}_box"])
                self.current_extruder = data["toolhead"]["extruder"]
                self.control['temp_box'].pack_start(self.labels[f"{self.current_extruder}_box"], True, True, 3)
                self.control['temp_box'].reorder_child(self.labels[f"{self.current_extruder}_box"], 0)
                self.control['temp_box'].show_all()

    def remove(self, widget):
        self.content.remove(widget)

    def show_back(self, show=True):
        if show is True and self.buttons_showing['back'] is False:
            self.control['back'].set_sensitive(True)
            self.control['home'].set_sensitive(True)
            self.buttons_showing['back'] = True
        elif show is False and self.buttons_showing['back'] is True:
            self.control['back'].set_sensitive(False)
            self.control['home'].set_sensitive(False)
            self.buttons_showing['back'] = False

    def show_macro_shortcut(self, show=True):
        if show is True and self.buttons_showing['macros_shortcut'] is False:
            self.action_bar.add(self.control['macros_shortcut'])
            if self.buttons_showing['printer_select'] is False:
                self.action_bar.reorder_child(self.control['macros_shortcut'], 2)
            else:
                self.action_bar.reorder_child(self.control['macros_shortcut'], 3)
            self.control['macros_shortcut'].show()
            self.buttons_showing['macros_shortcut'] = True
        elif show is False and self.buttons_showing['macros_shortcut'] is True:
            self.action_bar.remove(self.control['macros_shortcut'])
            self.buttons_showing['macros_shortcut'] = False

    def show_printer_select(self, show=True):
        if len(self._config.get_printers()) <= 1:
            return
        if show and self.buttons_showing['printer_select'] is False:
            self.action_bar.add(self.control['printer_select'])
            self.action_bar.reorder_child(self.control['printer_select'], 2)
            self.buttons_showing['printer_select'] = True
            self.control['printer_select'].show()
        elif show is False and self.buttons_showing['printer_select']:
            self.action_bar.remove(self.control['printer_select'])
            self.buttons_showing['printer_select'] = False

    def set_title(self, title):
        if not title:
            self.titlelbl.set_label(f"{self._screen.connecting_to_printer}")
            return
        try:
            env = Environment(extensions=["jinja2.ext.i18n"], autoescape=True)
            env.install_gettext_translations(self._config.get_lang())
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except Exception as e:
            logging.debug(f"Error parsing jinja for title: {title}\n{e}")

        self.titlelbl.set_label(f"{self._screen.connecting_to_printer} | {title}")

    def update_time(self):
        now = datetime.now()
        confopt = self._config.get_main_config().getboolean("24htime", True)
        if now.minute != self.time_min or self.time_format != confopt:
            if confopt:
                self.control['time'].set_text(f'{now:%H:%M }')
            else:
                self.control['time'].set_text(f'{now:%I:%M %p}')
            self.time_min = now.minute
            self.time_format = confopt
        return True

    def show_estop(self, show=True):
        if show and self.buttons_showing['estop'] is False:
            self.action_bar.add(self.control['estop'])
            self.buttons_showing['estop'] = True
            self.control['estop'].show()
        elif show is False and self.buttons_showing['estop']:
            self.action_bar.remove(self.control['estop'])
            self.buttons_showing['estop'] = False
