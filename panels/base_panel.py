# -*- coding: utf-8 -*-
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango
from jinja2 import Environment
from datetime import datetime
from math import log
from contextlib import suppress
from ks_includes.screen_panel import ScreenPanel


class BasePanel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.current_panel = None
        self.time_min = -1
        self.time_format = self._config.get_main_config().getboolean("24htime", True)
        self.time_update = None
        self.titlebar_items = []
        self.titlebar_name_type = None
        self.current_extruder = None
        # Action bar buttons
        abscale = self.bts * 1.1
        self.control['back'] = self._gtk.Button('back', scale=abscale)
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = self._gtk.Button('main', scale=abscale)
        self.control['home'].connect("clicked", self._screen._menu_go_back, True)
        self.control['estop'] = self._gtk.Button('emergency', scale=abscale)
        self.control['estop'].connect("clicked", self.emergency_stop)
        for control in self.control:
            self.set_control_sensitive(False, control)
        self.control['printer_select'] = self._gtk.Button('shuffle', scale=abscale)
        self.control['printer_select'].connect("clicked", self._screen.show_printer_select)
        self.control['printer_select'].set_no_show_all(True)

        self.shorcut = {
            "name": "Macros",
            "panel": "gcode_macros",
            "icon": "custom-script",
        }
        self.control['shortcut'] = self._gtk.Button(self.shorcut['icon'], scale=abscale)
        self.control['shortcut'].connect("clicked", self.menu_item_clicked, self.shorcut)
        self.control['shortcut'].set_no_show_all(True)

        # Any action bar button should close the keyboard
        for item in self.control:
            self.control[item].connect("clicked", self._screen.remove_keyboard)

        # Action bar
        self.action_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        if self._screen.vertical_mode:
            self.action_bar.set_hexpand(True)
            self.action_bar.set_vexpand(False)
        else:
            self.action_bar.set_hexpand(False)
            self.action_bar.set_vexpand(True)
        self.action_bar.get_style_context().add_class('action_bar')
        self.action_bar.set_size_request(self._gtk.action_bar_width, self._gtk.action_bar_height)
        self.action_bar.add(self.control['back'])
        self.action_bar.add(self.control['home'])
        self.action_bar.add(self.control['printer_select'])
        self.action_bar.add(self.control['shortcut'])
        self.action_bar.add(self.control['estop'])
        self.show_printer_select(len(self._config.get_printers()) > 1)

        # Titlebar

        # This box will be populated by show_heaters
        self.control['temp_box'] = Gtk.Box(spacing=10)

        self.titlelbl = Gtk.Label()
        self.titlelbl.set_hexpand(True)
        self.titlelbl.set_halign(Gtk.Align.CENTER)
        self.titlelbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_title(title)

        self.control['time'] = Gtk.Label(label="00:00 AM")
        self.control['time_box'] = Gtk.Box()
        self.control['time_box'].set_halign(Gtk.Align.END)
        self.control['time_box'].pack_end(self.control['time'], True, True, 10)

        self.titlebar = Gtk.Box(spacing=5)
        self.titlebar.get_style_context().add_class("title_bar")
        self.titlebar.set_valign(Gtk.Align.CENTER)
        self.titlebar.add(self.control['temp_box'])
        self.titlebar.add(self.titlelbl)
        self.titlebar.add(self.control['time_box'])

        # Main layout
        self.main_grid = Gtk.Grid()

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

        self.update_time()

    def show_heaters(self, show=True):
        try:
            for child in self.control['temp_box'].get_children():
                self.control['temp_box'].remove(child)
            devices = self._printer.get_temp_devices()
            if not show or not devices:
                return

            img_size = self._gtk.img_scale * self.bts
            for device in devices:
                self.labels[device] = Gtk.Label()
                self.labels[device].set_ellipsize(Pango.EllipsizeMode.START)

                self.labels[f'{device}_box'] = Gtk.Box()
                icon = self.get_icon(device, img_size)
                if icon is not None:
                    self.labels[f'{device}_box'].pack_start(icon, False, False, 3)
                self.labels[f'{device}_box'].pack_start(self.labels[device], False, False, 0)

            # Limit the number of items according to resolution
            nlimit = int(round(log(self._screen.width, 10) * 5 - 10.5))

            n = 0
            self.current_extruder = self._printer.get_stat("toolhead", "extruder")
            if self.current_extruder and f"{self.current_extruder}_box" in self.labels:
                self.control['temp_box'].add(self.labels[f"{self.current_extruder}_box"])
                n += 1

            for device in devices:
                if device == 'heater_bed':
                    self.control['temp_box'].add(self.labels['heater_bed_box'])
                    n += 1
                    continue
                # Users can fill the bar if they want
                if n >= nlimit + 1:
                    break
                name = device.split()[1] if len(device.split()) > 1 else device
                for item in self.titlebar_items:
                    if name == item:
                        self.control['temp_box'].add(self.labels[f"{device}_box"])
                        n += 1
                        break

            # If there is enough space fill with heater_generic
            for device in self._printer.get_heaters():
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
            if self._printer.extrudercount > 1:
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
        show = self._printer is not None and self._printer.state not in ('disconnected', 'startup', 'shutdown', 'error')
        self.show_shortcut(show)
        self.show_heaters(show)
        self.set_control_sensitive(show, control='estop')
        for control in ('back', 'home'):
            self.set_control_sensitive(len(self._screen._cur_panels) > 1, control=control)
        self.current_panel = panel
        self.set_title(panel.title)
        self.content.add(panel.content)

    def back(self, widget=None):
        if self.current_panel is None:
            return
        self._screen.remove_keyboard()
        if hasattr(self.current_panel, "back") \
                and not self.current_panel.back() \
                or not hasattr(self.current_panel, "back"):
            self._screen._menu_go_back()

    def process_update(self, action, data):
        if action == "notify_update_response":
            if self.update_dialog is None:
                self.show_update_dialog()
            with suppress(KeyError):
                self.labels['update_progress'].set_text(
                    f"{self.labels['update_progress'].get_text().strip()}\n"
                    f"{data['message']}\n")
            with suppress(KeyError):
                if data['complete']:
                    logging.info("Update complete")
                    if self.update_dialog is not None:
                        try:
                            self.update_dialog.set_response_sensitive(Gtk.ResponseType.OK, True)
                            self.update_dialog.get_widget_for_response(Gtk.ResponseType.OK).show()
                        except AttributeError:
                            logging.error("error trying to show the updater button the dialog might be closed")
                            self._screen.updating = False
                            for dialog in self._screen.dialogs:
                                self._gtk.remove_dialog(dialog)

        if action != "notify_status_update" or self._screen.printer is None:
            return
        devices = (self._printer.get_temp_devices())
        if devices is not None:
            for device in devices:
                temp = self._printer.get_dev_stat(device, "temperature")
                if temp is not None and device in self.labels:
                    name = ""
                    if not (device.startswith("extruder") or device.startswith("heater_bed")):
                        if self.titlebar_name_type == "full":
                            name = device.split()[1] if len(device.split()) > 1 else device
                            name = f'{self.prettify(name)}: '
                        elif self.titlebar_name_type == "short":
                            name = device.split()[1] if len(device.split()) > 1 else device
                            name = f"{name[:1].upper()}: "
                    self.labels[device].set_label(f"{name}{int(temp)}°")

        with suppress(Exception):
            if data["toolhead"]["extruder"] != self.current_extruder:
                self.control['temp_box'].remove(self.labels[f"{self.current_extruder}_box"])
                self.current_extruder = data["toolhead"]["extruder"]
                self.control['temp_box'].pack_start(self.labels[f"{self.current_extruder}_box"], True, True, 3)
                self.control['temp_box'].reorder_child(self.labels[f"{self.current_extruder}_box"], 0)
                self.control['temp_box'].show_all()

        return False

    def remove(self, widget):
        self.content.remove(widget)

    def set_control_sensitive(self, value=True, control='shortcut'):
        self.control[control].set_sensitive(value)

    def show_shortcut(self, show=True):
        show = (
            show
            and self._config.get_main_config().getboolean('side_macro_shortcut', True)
            and self._printer.get_printer_status_data()["printer"]["gcode_macros"]["count"] > 0
        )
        self.control['shortcut'].set_visible(show)
        self.set_control_sensitive(self._screen._cur_panels[-1] != self.shorcut['panel'])

    def show_printer_select(self, show=True):
        self.control['printer_select'].set_visible(show)

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

    def set_ks_printer_cfg(self, printer):
        ScreenPanel.ks_printer_cfg = self._config.get_printer_config(printer)
        if self.ks_printer_cfg is not None:
            self.titlebar_name_type = self.ks_printer_cfg.get("titlebar_name_type", None)
            titlebar_items = self.ks_printer_cfg.get("titlebar_items", None)
            if titlebar_items is not None:
                self.titlebar_items = [str(i.strip()) for i in titlebar_items.split(',')]
                logging.info(f"Titlebar name type: {self.titlebar_name_type} items: {self.titlebar_items}")
            else:
                self.titlebar_items = []

    def show_update_dialog(self):
        if self.update_dialog is not None:
            return
        button = [{"name": _("Finish"), "response": Gtk.ResponseType.OK}]
        self.labels['update_progress'] = Gtk.Label()
        self.labels['update_progress'].set_halign(Gtk.Align.START)
        self.labels['update_progress'].set_valign(Gtk.Align.START)
        self.labels['update_progress'].set_ellipsize(Pango.EllipsizeMode.END)
        self.labels['update_scroll'] = self._gtk.ScrolledWindow(steppers=False)
        self.labels['update_scroll'].set_size_request(self._gtk.width - 30, self._gtk.height * .6)
        self.labels['update_scroll'].set_property("overlay-scrolling", True)
        self.labels['update_scroll'].add(self.labels['update_progress'])
        self.labels['update_scroll'].connect("size-allocate", self._autoscroll)
        dialog = self._gtk.Dialog(_("Updating"), button, self.labels['update_scroll'], self.finish_updating)
        dialog.connect("delete-event", self.close_update_dialog)
        dialog.set_response_sensitive(Gtk.ResponseType.OK, False)
        dialog.get_widget_for_response(Gtk.ResponseType.OK).hide()
        self.update_dialog = dialog
        self._screen.updating = True

    def finish_updating(self, dialog, response_id):
        if response_id != Gtk.ResponseType.OK:
            return
        logging.info("Finishing update")
        self._screen.updating = False
        self._gtk.remove_dialog(dialog)
        self._screen._menu_go_back(home=True)

    def close_update_dialog(self, *args):
        logging.info("Closing update dialog")
        if self.update_dialog in self._screen.dialogs:
            self._screen.dialogs.remove(self.update_dialog)
        self.update_dialog = None
        self._screen._menu_go_back(home=True)
