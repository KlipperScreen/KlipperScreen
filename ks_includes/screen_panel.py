import datetime
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGtk import find_widget


class ScreenPanel:
    _screen = None
    _config = None
    _files = None
    _printer = None
    _gtk = None
    ks_printer_cfg = None

    def __init__(self, screen, title, **kwargs):
        self.menu = []
        ScreenPanel._screen = screen
        ScreenPanel._config = screen._config
        ScreenPanel._files = screen.files
        ScreenPanel._printer = screen.printer
        ScreenPanel._gtk = screen.gtk
        self.labels = {}
        self.control = {}
        self.title = title
        self.devices = {}
        self.active_heaters = []
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        self.content.get_style_context().add_class("content")
        self._show_heater_power = self._config.get_main_config().getboolean('show_heater_power', False)
        self.bts = self._gtk.bsidescale

        self.update_dialog = None

    def _autoscroll(self, scroll, *args):
        adj = scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def emergency_stop(self, widget):
        if self._config.get_main_config().getboolean('confirm_estop', False):
            self._screen._confirm_send_action(widget, _("Are you sure you want to run Emergency Stop?"),
                                              "printer.emergency_stop")
        else:
            self._screen._ws.klippy.emergency_stop()

    def get_file_image(self, filename, width=None, height=None, small=False):
        if not self._files.has_thumbnail(filename):
            return None
        loc = self._files.get_thumbnail_location(filename, small)
        if loc is None:
            return None
        width = width if width is not None else self._gtk.img_width
        height = height if height is not None else self._gtk.img_height
        if loc[0] == "file":
            return self._gtk.PixbufFromFile(loc[1], width, height)
        if loc[0] == "http":
            return self._gtk.PixbufFromHttp(loc[1], width, height)
        return None

    def menu_item_clicked(self, widget, item):
        panel_args = {}
        if 'name' in item:
            panel_args['title'] = item['name']
        if 'extra' in item:
            panel_args['extra'] = item['extra']
        self._screen.show_panel(item['panel'], **panel_args)

    def load_menu(self, widget, name, title=None):
        logging.info(f"loading menu {name}")
        if f"{name}_menu" not in self.labels:
            logging.error(f"{name} not in labels")
            return

        for child in self.content.get_children():
            self.content.remove(child)

        self.menu.append(f'{name}_menu')
        logging.debug(f"self.menu: {self.menu}")
        self.content.add(self.labels[self.menu[-1]])
        self.content.show_all()
        if title:
            self._screen.base_panel.set_title(f"{self.title} | {title}")

    def unload_menu(self, widget=None):
        if len(self.menu) <= 1 or self.menu[-2] not in self.labels:
            return
        self._screen.base_panel.set_title(self._screen.panels[self._screen._cur_panels[-1]].title)
        self.menu.pop()
        logging.debug(f"self.menu: {self.menu}")
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels[self.menu[-1]])
        self.content.show_all()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False

    def on_dropdown_change(self, combo, section, option, callback=None):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            value = model[tree_iter][1]
            logging.debug(f"[{section}] {option} changed to {value}")
            self._config.set(section, option, value)
            self._config.save_user_config_options()
            if callback is not None:
                callback(value)

    def scale_moved(self, widget, event, section, option):
        logging.debug(f"[{section}] {option} changed to {widget.get_value()}")
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, option, str(int(widget.get_value())))
        self._config.save_user_config_options()

    def switch_config_option(self, switch, gparam, section, option, callback=None):
        logging.debug(f"[{section}] {option} toggled {switch.get_active()}")
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, option, "True" if switch.get_active() else "False")
        self._config.save_user_config_options()
        if callback is not None:
            callback(switch.get_active())

    @staticmethod
    def format_time(seconds):
        spc = "\u00A0"  # Non breakable space
        if seconds is None or seconds < 1:
            return "-"
        days = seconds // 86400
        day_units = ngettext("day", "days", days)
        seconds %= 86400
        hours = seconds // 3600
        hour_units = ngettext("hour", "hours", hours)
        seconds %= 3600
        minutes = round(seconds / 60)
        min_units = ngettext("minute", "minutes", minutes)
        seconds %= 60
        sec_units = ngettext("second", "seconds", seconds)
        return f"{f'{days:2.0f}{spc}{day_units}{spc}' if days > 0 else ''}" \
               f"{f'{hours:2.0f}{spc}{hour_units}{spc}' if hours > 0 else ''}" \
               f"{f'{minutes:2.0f}{spc}{min_units}{spc}' if minutes > 0 and days == 0 else ''}" \
               f"{f'{seconds:2.0f}{spc}{sec_units}' if days == 0 and hours == 0 and minutes == 0 else ''}"

    def format_eta(self, total, elapsed):
        if total is None:
            return "-"
        seconds = total - elapsed
        if seconds <= 0:
            return "-"
        days = seconds // 86400
        seconds %= 86400
        hours = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        eta = datetime.datetime.now() + datetime.timedelta(days=days, hours=hours, minutes=minutes)
        if self._config.get_main_config().getboolean("24htime", True):
            return f"{self.format_time(total - elapsed)} | {eta:%H:%M} {f' +{days:2.0f}d' if days > 0 else ''}"
        return f"{self.format_time(total - elapsed)} | {eta:%I:%M %p} {f' +{days:2.0f}d' if days > 0 else ''}"

    @staticmethod
    def format_size(size):
        size = float(size)
        suffixes = ["kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
        for i, suffix in enumerate(suffixes, start=2):
            unit = 1024 ** i
            if size < unit:
                return f"{(1024 * size / unit):.1f} {suffix}"

    @staticmethod
    def format_speed(bitrate):
        bitrate = float(bitrate)
        suffixes = ["Kbits/s", "Mbits/s", "Gbits/s", "Tbits/s", "Pbits/s", "Ebits/s", "Zbits/s", "Ybits/s"]
        for i, suffix in enumerate(suffixes, start=1):
            unit = 1000 ** i
            if bitrate < unit:
                return f"{(1000 * bitrate / unit):.0f} {suffix}"

    @staticmethod
    def prettify(name: str):
        name = name.replace("_", " ")
        if name.islower():
            name = name.title()
        return name

    def update_temp(self, dev, temp, target, power, lines=1, digits=1):
        new_label_text = f"{temp or 0:.{digits}f}"
        if self._printer.device_has_target(dev) and target:
            new_label_text += f"/{target:.0f}"
        if dev not in self.devices:
            new_label_text += "°"

        show_power = self._show_heater_power and power
        if show_power:
            new_label_text += f" {power * 100:3.0f}%"

        if dev in self.labels:
            # Job_Status
            find_widget(self.labels[dev], Gtk.Label).set_text(new_label_text)
        elif dev in self.devices:
            # Temperature and Main_Menu
            find_widget(self.devices[dev]["temp"], Gtk.Label).set_text(new_label_text)

    def add_option(self, boxname, opt_array, opt_name, option):
        if option['type'] is None:
            return
        name = Gtk.Label(
            hexpand=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, xalign=0)
        name.set_markup(f"<big><b>{option['name']}</b></big>")

        labels = Gtk.Box(spacing=0, orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        labels.add(name)
        if 'tooltip' in option:
            tooltip = Gtk.Label(
                label=option['tooltip'],
                hexpand=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
                wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, xalign=0)
            labels.add(tooltip)

        row_box = Gtk.Box(spacing=5, valign=Gtk.Align.CENTER, hexpand=True, vexpand=False)
        row_box.get_style_context().add_class("frame-item")
        row_box.add(labels)

        setting = {}
        if option['type'] == "binary":
            switch = Gtk.Switch(active=self._config.get_config().getboolean(option['section'], opt_name, fallback=True))
            switch.set_vexpand(False)
            switch.set_valign(Gtk.Align.CENTER)
            switch.connect("notify::active", self.switch_config_option, option['section'], opt_name,
                           option['callback'] if "callback" in option else None)
            row_box.add(switch)
            setting = {opt_name: switch}
        elif option['type'] == "dropdown":
            dropdown = Gtk.ComboBoxText()
            for i, opt in enumerate(option['options']):
                dropdown.append(opt['value'], opt['name'])
                if opt['value'] == self._config.get_config()[option['section']].get(opt_name, option['value']):
                    dropdown.set_active(i)
            dropdown.connect("changed", self.on_dropdown_change, option['section'], opt_name,
                             option['callback'] if "callback" in option else None)
            dropdown.set_entry_text_column(0)
            row_box.add(dropdown)
            setting = {opt_name: dropdown}
        elif option['type'] == "scale":
            row_box.set_orientation(Gtk.Orientation.VERTICAL)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,
                                             min=option['range'][0], max=option['range'][1], step=option['step'])
            scale.set_hexpand(True)
            scale.set_value(int(self._config.get_config().get(option['section'], opt_name, fallback=option['value'])))
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            row_box.add(scale)
            setting = {opt_name: scale}
        elif option['type'] == "printer":
            box = Gtk.Box(vexpand=False)
            label = Gtk.Label(f"{option['moonraker_host']}:{option['moonraker_port']}")
            box.add(label)
            row_box.add(box)
        elif option['type'] == "menu":
            open_menu = self._gtk.Button("settings", style="color3")
            open_menu.connect("clicked", self.load_menu, option['menu'], option['name'])
            open_menu.set_hexpand(False)
            open_menu.set_halign(Gtk.Align.END)
            row_box.add(open_menu)
        elif option['type'] == "button":
            select = self._gtk.Button("load", style="color3")
            if "callback" in option:
                select.connect("clicked", option['callback'], option['name'])
            select.set_hexpand(False)
            select.set_halign(Gtk.Align.END)
            row_box.add(select)

        opt_array[opt_name] = {
            "name": option['name'],
            "row": row_box
        }

        opts = sorted(list(opt_array), key=lambda x: opt_array[x]['name'].casefold())
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()
        return setting
