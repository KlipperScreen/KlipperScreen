# -*- coding: utf-8 -*-
import datetime
import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango
from jinja2 import Environment

from ks_includes.screen_panel import ScreenPanel


class BasePanel(ScreenPanel):
    def __init__(self, screen, title, back=True, action_bar=True, printer_name=True):
        super().__init__(screen, title, back, action_bar, printer_name)
        self.current_panel = None
        self.time_min = -1
        self.time_format = self._config.get_main_config().getboolean("24htime", True)
        self.time_update = None
        self.titlebar_name_type = None
        self.buttons_showing = {
            'back': not(back),
            'macros_shortcut': False,
            'printer_select': False
        }

        # Action bar buttons
        self.control['back'] = self._gtk.ButtonImage('back', None, None, 1)
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = self._gtk.ButtonImage('main', None, None, 1)
        self.control['home'].connect("clicked", self.menu_return, True)

        if len(self._config.get_printers()) > 1:
            self.control['printer_select'] = self._gtk.ButtonImage('shuffle', None, None, 1)
            self.control['printer_select'].connect("clicked", self._screen.show_printer_select)

        self.control['macros_shortcut'] = self._gtk.ButtonImage('custom-script', None, None, 1)
        self.control['macros_shortcut'].connect("clicked", self.menu_item_clicked, "gcode_macros", {
            "name": "Macros",
            "panel": "gcode_macros"
        })

        self.control['estop'] = self._gtk.ButtonImage('emergency', None, None, 1)
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
        self.action_bar.add(self.control['macros_shortcut'])
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
        self.control['time_box'].pack_end(self.control['time'], True, True, 5)

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
        printer_cfg = self._config.get_printer_config(self._screen.connected_printer)
        if printer_cfg is not None:
            self.titlebar_name_type = printer_cfg.get("titlebar_name_type", None)
        else:
            self.titlebar_name_type = None
        logging.info("Titlebar name type: %s", self.titlebar_name_type)

        for child in self.control['temp_box'].get_children():
            self.control['temp_box'].remove(child)

        if not show or self._screen.printer.get_temp_store_devices() is None:
            return

        for device in self._screen.printer.get_temp_store_devices():
            if device.startswith("extruder"):
                if self._screen.printer.extrudercount > 1:
                    if device == "extruder":
                        icon = self._gtk.Image("extruder-0", .5)
                    else:
                        icon = self._gtk.Image("extruder-%s" % device[8:], .5)
                else:
                    icon = self._gtk.Image("extruder", .5)
            elif device.startswith("heater_bed"):
                icon = self._gtk.Image("bed", .5)
            # Extra items
            elif self.titlebar_name_type is not None:
                # The item has a name, do not use an icon
                icon = None
            elif device.startswith("temperature_fan"):
                icon = self._gtk.Image("fan", .5)
            elif device.startswith("heater_generic"):
                icon = self._gtk.Image("heater", .5)
            else:
                icon = self._gtk.Image("heat-up", .5)

            self.labels[device] = Gtk.Label(label="100º")
            self.labels[device].set_ellipsize(Pango.EllipsizeMode.START)

            self.labels[device + '_box'] = Gtk.Box()
            if icon is not None:
                self.labels[device + '_box'].pack_start(icon, False, False, 3)
            self.labels[device + '_box'].pack_start(self.labels[device], False, False, 0)

        # Limit the number of items according to resolution
        if self._screen.width <= 480:
            nlimit = 3
        elif self._screen.width <= 800:
            nlimit = 4
        else:
            nlimit = 5

        n = 0
        if self._screen.printer.get_tools():
            self.current_extruder = self._screen.printer.get_stat("toolhead", "extruder")
            self.control['temp_box'].add(self.labels["%s_box" % self.current_extruder])
            n += 1

        if self._screen.printer.has_heated_bed():
            self.control['temp_box'].add(self.labels['heater_bed_box'])
            n += 1

        # Options in the config have priority
        if printer_cfg is not None:
            titlebar_items = printer_cfg.get("titlebar_items", "")
            if titlebar_items is not None:
                titlebar_items = [str(i.strip()) for i in titlebar_items.split(',')]
                logging.info("Titlebar items: %s", titlebar_items)
                for device in self._screen.printer.get_temp_store_devices():
                    # Users can fill the bar if they want
                    if n >= nlimit + 1:
                        break
                    if not (device.startswith("extruder") or device.startswith("heater_bed")):
                        name = device.split(" ")[1:][0]
                    else:
                        name = device
                    for item in titlebar_items:
                        if name == item:
                            self.control['temp_box'].add(self.labels["%s_box" % device])
                            n += 1
                            break

        # If there is enough space fill with heater_generic
        for device in self._screen.printer.get_temp_store_devices():
            if n >= nlimit:
                break
            if device.startswith("heater_generic"):
                self.control['temp_box'].add(self.labels["%s_box" % device])
                n += 1
        self.control['temp_box'].show_all()

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

        if hasattr(self.current_panel, "back"):
            if not self.current_panel.back():
                self._screen._menu_go_back()
        else:
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
                            name = device.split(" ")[1:][0].capitalize().replace("_", " ") + ": "
                        elif self.titlebar_name_type == "short":
                            name = device.split(" ")[1:][0][:1].upper() + ": "
                    self.labels[device].set_label("%s%d°" % (name, round(temp)))

        if "toolhead" in data and "extruder" in data["toolhead"]:
            if data["toolhead"]["extruder"] != self.current_extruder:
                self.control['temp_box'].remove(self.labels["%s_box" % self.current_extruder])
                self.current_extruder = data["toolhead"]["extruder"]
                self.control['temp_box'].pack_start(self.labels["%s_box" % self.current_extruder], True, True, 3)
                self.control['temp_box'].reorder_child(self.labels["%s_box" % self.current_extruder], 0)
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
            self.buttons_showing['macros_shortcut'] = True
        elif show is False and self.buttons_showing['macros_shortcut'] is True:
            self.action_bar.remove(self.control['macros_shortcut'])
            self.buttons_showing['macros_shortcut'] = False
        self._screen.show_all()

    def show_printer_select(self, show=True):
        if len(self._config.get_printers()) <= 1:
            return
        if show and self.buttons_showing['printer_select'] is False:
            self.action_bar.add(self.control['printer_select'])
            self.action_bar.reorder_child(self.control['printer_select'], 2)
            self.buttons_showing['printer_select'] = True
        elif show is False and self.buttons_showing['printer_select']:
            self.action_bar.remove(self.control['printer_select'])
            self.buttons_showing['printer_select'] = False
        self._screen.show_all()

    def set_title(self, title):
        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except Exception:
            logging.debug("Error parsing jinja for title: %s" % title)

        self.titlelbl.set_label("%s | %s" % (self._screen.connecting_to_printer, title))

    def update_time(self):
        now = datetime.datetime.now()
        confopt = self._config.get_main_config().getboolean("24htime", True)
        if now.minute != self.time_min or self.time_format != confopt:
            if confopt:
                self.control['time'].set_text(now.strftime("%H:%M"))
            else:
                self.control['time'].set_text(now.strftime("%I:%M %p"))
        return True
