# -*- coding: utf-8 -*-
import logging
import os
import pathlib
import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango, GdkPixbuf
from jinja2 import Environment
from datetime import datetime
from math import log
from ks_includes.screen_panel import ScreenPanel

try:
    import psutil
    psutil_available = True
except ImportError:
    psutil_available = False
    logging.debug("psutil is not installed. Unable to do battery check.")


class BasePanel(ScreenPanel):
    def __init__(self, screen, title=None):
        super().__init__(screen, title)
        self.current_panel = None
        self.time_min = -1
        self.time_format = self._config.get_main_config().getboolean("24htime", True)
        self.time_update = None
        self.battery_update = None
        self.titlebar_items = []
        self.titlebar_name_type = None
        self.show_spoolman_in_title = False
        self.spoolman_low_limit = 0
        self.spoolman_blink_timeout = None
        self.spoolman_blink_state = False
        self.spoolman_icon_size = int(self._gtk.font_size * 1.1)
        self.spoolman_icon_alert_pixbuf = None
        self.current_extruder = None
        self.last_usage_report = datetime.now()
        self.usage_report = 0
        # Action bar buttons
        self.abscale = self.bts * 1.1
        self.control['back'] = self._gtk.Button('back', scale=self.abscale)
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = self._gtk.Button('main', scale=self.abscale)
        self.control['home'].connect("clicked", self._screen._menu_go_back, True)
        for control in self.control:
            self.set_control_sensitive(False, control)
        self.control['estop'] = self._gtk.Button('emergency', scale=self.abscale)
        self.control['estop'].connect("clicked", self.emergency_stop)
        self.control['estop'].set_no_show_all(True)
        self.shutdown = {
            "panel": "shutdown",
        }
        self.control['shutdown'] = self._gtk.Button('shutdown', scale=self.abscale)
        self.control['shutdown'].connect("clicked", self.menu_item_clicked, self.shutdown)
        self.control['shutdown'].set_no_show_all(True)
        self.control['printer_select'] = self._gtk.Button('shuffle', scale=self.abscale)
        self.control['printer_select'].connect("clicked", self._screen.show_printer_select)
        self.control['printer_select'].set_no_show_all(True)

        self.shorcut = {
            "panel": "gcode_macros",
            "icon": "custom-script",
        }
        self.control['shortcut'] = self._gtk.Button(self.shorcut['icon'], scale=self.abscale)
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
        self.action_bar.add(self.control['shutdown'])
        self.show_printer_select(len(self._config.get_printers()) > 1)

        # Titlebar

        # This box will be populated by show_heaters
        self.control['temp_box'] = Gtk.Box(spacing=10)

        self.titlelbl = Gtk.Label(hexpand=True, halign=Gtk.Align.CENTER, ellipsize=Pango.EllipsizeMode.END)

        self.control['time'] = Gtk.Label(label="00:00 AM")
        self.control['time_box'] = Gtk.Box(halign=Gtk.Align.END)
        self.control['time_box'].pack_end(self.control['time'], True, True, 10)

        self.battery_icons = self.load_battery_icons()
        self.labels['battery'] = Gtk.Label()
        self.labels['battery_icon'] = self._gtk.Image()
        self.labels['battery_icon'].set_from_pixbuf(self.battery_icons['unknown'])
        self.control['battery_box'] = Gtk.Box(halign=Gtk.Align.END)
        self.control['battery_box'].set_no_show_all(True)
        self.control['battery_box'].add(self.labels['battery'])
        self.control['battery_box'].add(self.labels['battery_icon'])
        for widget in self.control['battery_box']:
            widget.show()

        self.labels['spoolman_icon'] = Gtk.Image()
        self.labels['spoolman_weight'] = Gtk.Label()
        self.control['spoolman_box'] = Gtk.Box(halign=Gtk.Align.END, spacing=1)
        self.control['spoolman_box'].set_no_show_all(True)
        self.control['spoolman_box'].add(self.labels['spoolman_icon'])
        self.control['spoolman_box'].add(self.labels['spoolman_weight'])
        self.labels['spoolman_icon'].show()
        self.labels['spoolman_weight'].show()
        self.load_spoolman_icons()

        self.titlebar = Gtk.Box(spacing=5, valign=Gtk.Align.CENTER)
        self.titlebar.get_style_context().add_class("title_bar")
        self.titlebar.add(self.control['temp_box'])
        self.titlebar.add(self.titlelbl)
        self.titlebar.add(self.control['time_box'])
        self.titlebar.add(self.control['battery_box'])
        self.set_title(title)

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

    def load_battery_icons(self):
        img_size = self._gtk.img_scale * self.bts
        return {
            'charging': self._gtk.PixbufFromIcon('battery-charging', img_size, img_size),
            '100': self._gtk.PixbufFromIcon('battery-100', img_size, img_size),
            '75': self._gtk.PixbufFromIcon('battery-75', img_size, img_size),
            '50': self._gtk.PixbufFromIcon('battery-50', img_size, img_size),
            '25': self._gtk.PixbufFromIcon('battery-25', img_size, img_size),
            '0': self._gtk.PixbufFromIcon('battery-0', img_size, img_size),
            'unknown': self._gtk.PixbufFromIcon('battery-unknown', img_size, img_size),
        }

    def reload_icons(self):
        button: Gtk.Button
        for button in self.action_bar.get_children():
            img = button.get_image()
            name = button.get_name()
            pixbuf = img.get_pixbuf()
            if pixbuf is not None:
                size = pixbuf.get_width()
            else:
                logging.error(f"Couldn't get pixbuf for {name},"
                              f"a custom theme may have caused this")
                size = self._gtk.img_scale * self.abscale * 1.4
            button.set_image(self._gtk.Image(name, size, size))

        self.battery_icons = self.load_battery_icons()
        self.battery_percentage()
        self.update_spoolman_alert_visuals(self.spoolman_blink_state)

    def load_spoolman_icons(self):
        self.spoolman_icon_alert_pixbuf = self.get_spoolman_icon_pixbuf("981E1F", full_icon=True)

    def get_spoolman_icon_pixbuf(self, color, full_icon=False):
        klipperscreendir = pathlib.Path(__file__).parent.resolve().parent
        icon_path = os.path.join(klipperscreendir, "styles", self._screen.theme, "images", "spool.svg")
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(klipperscreendir, "styles", "spool.svg")
        try:
            svg = pathlib.Path(icon_path).read_text(encoding="utf-8")
            svg = svg.replace("var(--filament-color)", f"#{color}")
            if full_icon:
                svg = re.sub(r'fill:\s*(?!none)[^;"\']+', f'fill:#{color}', svg)
            loader = GdkPixbuf.PixbufLoader()
            loader.set_size(self.spoolman_icon_size, self.spoolman_icon_size)
            loader.write(svg.encode())
            loader.close()
            return loader.get_pixbuf()
        except Exception as e:
            logging.error(f"Couldn't load spoolman icon: {e}")
            return self._gtk.PixbufFromIcon("spool", self.spoolman_icon_size, self.spoolman_icon_size)

    def get_active_spoolman_color(self):
        if (
                self._printer is None
                or not self._printer.active_spool
                or "filament" not in self._printer.active_spool
                or not self._printer.active_spool["filament"]
        ):
            return "FFFFFF"
        filament = self._printer.active_spool["filament"]
        color = filament.get("color_hex", "FFFFFF")
        if not color:
            return "FFFFFF"
        return color.lstrip("#")

    def show_heaters(self, show=True):
        for child in self.control['temp_box'].get_children():
            self.control['temp_box'].remove(child)
        self.control['spoolman_box'].hide()
        if self._printer is None or not show:
            return
        try:
            devices = self._printer.get_temp_devices()
            if not devices:
                return
            img_size = self._gtk.img_scale * self.bts
            for device in devices:
                self.labels[device] = Gtk.Label(ellipsize=Pango.EllipsizeMode.START)
                self.labels[f'{device}_box'] = Gtk.Box()
                icon = self.get_icon(device, img_size)
                if icon is not None:
                    self.labels[f'{device}_box'].pack_start(icon, False, False, 3)
                self.labels[f'{device}_box'].pack_start(self.labels[device], False, False, 0)

            # Limit the number of items according to resolution
            nlimit = int(round(log(self._screen.width, 10) * 5 - 10.5))
            n = 0
            if len(self._printer.get_tools()) > (nlimit - 1):
                self.current_extruder = self._printer.get_stat("toolhead", "extruder")
                if self.current_extruder and f"{self.current_extruder}_box" in self.labels:
                    self.control['temp_box'].add(self.labels[f"{self.current_extruder}_box"])
            else:
                self.current_extruder = False
            for device in devices:
                if n >= nlimit:
                    break
                if device.startswith("extruder") and self.current_extruder is False:
                    self.control['temp_box'].add(self.labels[f"{device}_box"])
                    n += 1
                elif device.startswith("heater"):
                    self.control['temp_box'].add(self.labels[f"{device}_box"])
                    n += 1
            for item in self.titlebar_items:
                if item == "spoolman" and self._printer.spoolman:
                    self.control['temp_box'].add(self.control['spoolman_box'])
                    continue
                for device in devices:
                    name = device.split()[1] if len(device.split()) > 1 else device
                    if name == item and self.labels[f"{device}_box"].get_parent() is None:
                        self.control['temp_box'].add(self.labels[f"{device}_box"])
                        break

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
        if self.battery_update is None:
            self.battery_update = GLib.timeout_add_seconds(60, self.battery_percentage)

    def add_content(self, panel):
        printing = self._printer and self._printer.state in {"printing", "paused"}
        connected = self._printer and self._printer.state not in {'disconnected', 'startup', 'shutdown', 'error'}
        printer_select = 'printer_select' not in self._screen._cur_panels
        self.control['estop'].set_visible(printing)
        self.control['shutdown'].set_visible(not printing)
        self.show_shortcut(connected and printer_select)
        self.show_heaters(connected and printer_select)
        self.refresh_spoolman_weight(connected and printer_select)
        self.show_printer_select(len(self._config.get_printers()) > 1)
        for control in ('back', 'home'):
            self.set_control_sensitive(len(self._screen._cur_panels) > 1, control=control)
        self.current_panel = panel
        self.set_title(panel.title)
        self.content.add(panel.content)

    def stop_spoolman_blink(self):
        if self.spoolman_blink_timeout is not None:
            GLib.source_remove(self.spoolman_blink_timeout)
            self.spoolman_blink_timeout = None
        self.spoolman_blink_state = False

    def update_spoolman_alert_visuals(self, alert):
        if alert:
            self.labels['spoolman_icon'].set_from_pixbuf(self.spoolman_icon_alert_pixbuf)
            self.labels['spoolman_weight'].get_style_context().add_class("spoolman_low")
        else:
            self.labels['spoolman_icon'].set_from_pixbuf(
                self.get_spoolman_icon_pixbuf(self.get_active_spoolman_color())
            )
            self.labels['spoolman_weight'].get_style_context().remove_class("spoolman_low")

    def blink_spoolman_low(self):
        self.spoolman_blink_state = not self.spoolman_blink_state
        self.update_spoolman_alert_visuals(self.spoolman_blink_state)
        return True

    def update_spoolman_weight_label(self):
        if (
                self._printer is None
                or not self.show_spoolman_in_title
        ):
            self.stop_spoolman_blink()
            self.update_spoolman_alert_visuals(False)
            self.labels['spoolman_weight'].set_label("- g")
            self.control['spoolman_box'].show()
            return
        if (
                not self._printer.spoolman
                or not self._printer.active_spool
                or "remaining_weight" not in self._printer.active_spool
                or self._printer.active_spool["remaining_weight"] is None
        ):
            self.stop_spoolman_blink()
            self.update_spoolman_alert_visuals(False)
            self.labels['spoolman_weight'].set_label("- g")
            self.control['spoolman_box'].show()
            return
        remaining_weight = self._printer.active_spool["remaining_weight"]
        self.labels['spoolman_weight'].set_label(f'{round(remaining_weight):.0f}g')
        if self.spoolman_low_limit > 0 and remaining_weight < self.spoolman_low_limit:
            if self.spoolman_blink_timeout is None:
                self.spoolman_blink_state = True
                self.update_spoolman_alert_visuals(True)
                self.spoolman_blink_timeout = GLib.timeout_add(700, self.blink_spoolman_low)
        else:
            self.stop_spoolman_blink()
            self.update_spoolman_alert_visuals(False)
        self.control['spoolman_box'].show()

    def refresh_spoolman_weight(self, show=True, spool_id=None):
        if self._printer is None or not self.show_spoolman_in_title:
            self.stop_spoolman_blink()
            self.update_spoolman_alert_visuals(False)
            self.control['spoolman_box'].hide()
            return
        if not show:
            self.stop_spoolman_blink()
            self.update_spoolman_alert_visuals(False)
            self.control['spoolman_box'].hide()
            return
        if not self._printer.spoolman:
            self._printer.set_active_spool(checked=False)
            self.update_spoolman_weight_label()
            return
        if spool_id is None and self._printer.active_spool_checked:
            self.update_spoolman_weight_label()
            return
        if spool_id is None:
            result = self._screen.apiclient.send_request("server/spoolman/spool_id")
            if result is False:
                logging.error("Error trying to fetch active spool id")
                self._printer.set_active_spool(checked=False)
                self.update_spoolman_weight_label()
                return
            if "spool_id" not in result or not result["spool_id"]:
                self._printer.set_active_spool()
                self.update_spoolman_weight_label()
                return
            spool_id = result["spool_id"]
        elif not spool_id:
            self._printer.set_active_spool()
            self.update_spoolman_weight_label()
            return

        spool = self._screen.apiclient.post_request("server/spoolman/proxy", json={
            "request_method": "GET",
            "path": f"/v1/spool/{spool_id}",
        })
        if not spool or "result" not in spool:
            logging.error("Error trying to fetch active spool information")
            self._printer.set_active_spool(spool_id=spool_id, checked=False)
            self.update_spoolman_weight_label()
            return
        self._printer.set_active_spool(spool_id=spool_id, spool=spool["result"])
        self.update_spoolman_weight_label()

    def back(self, widget=None):
        if self.current_panel is None:
            return
        self._screen.remove_keyboard()
        if hasattr(self.current_panel, "back") \
                and not self.current_panel.back() \
                or not hasattr(self.current_panel, "back"):
            self._screen._menu_go_back()

    def process_update(self, action, data):
        if action == "notify_active_spool_set":
            spool_id = data.get("spool_id") if isinstance(data, dict) else None
            self.refresh_spoolman_weight(
                self._printer is not None and self._printer.state not in {'disconnected', 'startup', 'shutdown', 'error'},
                spool_id=spool_id
            )
            return
        if action == "notify_proc_stat_update":
            cpu = data["system_cpu_usage"]["cpu"]
            memory = (data["system_memory"]["used"] / data["system_memory"]["total"]) * 100
            error = "message_popup_error"
            ctx = self.titlebar.get_style_context()
            msg = f"CPU: {cpu:2.0f}%    RAM: {memory:2.0f}%"
            if cpu > 80 or memory > 85:
                if self.usage_report < 3:
                    self.usage_report += 1
                    return
                self.last_usage_report = datetime.now()
                if not ctx.has_class(error):
                    ctx.add_class(error)
                self._screen.log_notification(f"{self._screen.connecting_to_printer}: {msg}", 2)
                self.titlelbl.set_label(msg)
            elif ctx.has_class(error):
                if (datetime.now() - self.last_usage_report).seconds < 5:
                    self.titlelbl.set_label(msg)
                    return
                self.usage_report = 0
                ctx.remove_class(error)
                self.titlelbl.set_label(f"{self._screen.connecting_to_printer}")
            return

        if action == "notify_update_response":
            if self.update_dialog is None:
                self.show_update_dialog()
            if 'message' in data:
                self.labels['update_progress'].set_text(
                    f"{self.labels['update_progress'].get_text().strip()}\n"
                    f"{data['message']}\n")
            if 'complete' in data and data['complete']:
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
            return
        if action != "notify_status_update" or self._screen.printer is None:
            return
        devices = self._printer.get_temp_devices()
        if not devices:
            return
        for device in devices:
            temp = self._printer.get_stat(device, "temperature")
            if temp and device in self.labels:
                name = ""
                if not (device.startswith("extruder") or device.startswith("heater_bed")):
                    if self.titlebar_name_type == "full":
                        name = device.split()[1] if len(device.split()) > 1 else device
                        name = f'{self.prettify(name)}: '
                    elif self.titlebar_name_type == "short":
                        name = device.split()[1] if len(device.split()) > 1 else device
                        name = f"{name[:1].upper()}: "
                self.labels[device].set_label(f"{name}{temp:.0f}°")

        if (self.current_extruder and 'toolhead' in data and 'extruder' in data['toolhead']
                and data["toolhead"]["extruder"] != self.current_extruder):
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
            and self._config.get_main_config().getboolean('side_macro_shortcut', False)
            and self._printer.get_printer_status_data()["printer"]["gcode_macros"]["count"] > 0
            and self._screen._cur_panels[-1] != 'printer_select'
        )
        self.control['shortcut'].set_visible(show)
        self.set_control_sensitive(self._screen._cur_panels[-1] != self.shorcut['panel'])
        self.set_control_sensitive(self._screen._cur_panels[-1] != self.shutdown['panel'], control='shutdown')

    def show_printer_select(self, show=True):
        self.control['printer_select'].set_visible(
            show and 'printer_select' not in self._screen._cur_panels
        )

    def set_title(self, title):
        self.titlebar.get_style_context().remove_class("message_popup_error")
        if (
                self._screen.connecting_to_printer != "Printer"
                and 'printer_select' not in self._screen._cur_panels
        ):
            printer = self._screen.connecting_to_printer
        else:
            printer = ""
        if not title:
            self.titlelbl.set_label(f"{printer}")
            return
        try:
            env = Environment(extensions=["jinja2.ext.i18n"], autoescape=True)
            env.install_gettext_translations(self._config.get_lang())
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except Exception as e:
            logging.debug(f"Error parsing jinja for title: {title}\n{e}")

        self.titlelbl.set_label(f"{printer} {title}")

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

    def get_battery_icon(self, charge: float, plugged: bool):
        if plugged:
            return self.battery_icons['charging']
        elif charge > 75:
            return self.battery_icons['100']
        elif charge > 50:
            return self.battery_icons['75']
        elif charge > 25:
            return self.battery_icons['50']
        elif charge > 10:
            return self.battery_icons['25']
        elif charge >= 0:
            return self.battery_icons['0']
        else:
            return self.battery_icons['unknown']

    def battery_percentage(self):
        if not psutil_available:
            return False
        battery = psutil.sensors_battery()
        if battery and battery.percent:
            self.labels['battery_icon'].set_from_pixbuf(
                self.get_battery_icon(battery.percent, battery.power_plugged)
            )
            self.labels['battery'].set_text(f'{battery.percent:.0f}%')
            self.control['battery_box'].show()
            return True
        else:
            logging.debug("Battery information not available.")
            self.control['battery_box'].hide()
            return False

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
            self.show_spoolman_in_title = "spoolman" in self.titlebar_items
            self.spoolman_low_limit = self.ks_printer_cfg.getfloat("spoolman_low_limit", fallback=0)
        else:
            self.titlebar_items = []
            self.show_spoolman_in_title = False
            self.spoolman_low_limit = 0
        self.refresh_spoolman_weight(
            self._printer is not None and self._printer.state not in {'disconnected', 'startup', 'shutdown', 'error'}
        )

    def show_update_dialog(self):
        if self.update_dialog is not None:
            return
        button = [{"name": _("Finish"), "response": Gtk.ResponseType.OK}]
        self.labels['update_progress'] = Gtk.Label(hexpand=True, vexpand=True, ellipsize=Pango.EllipsizeMode.END)
        self.labels['update_scroll'] = self._gtk.ScrolledWindow(steppers=False)
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
