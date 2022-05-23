import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, Pango

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return SettingsPanel(*args)


class SettingsPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.settings = {}
        self.menu = ['settings_menu']

        self.labels['add_printer_button'] = self._gtk.Button(_("Add Printer"), "color1")

        options = self._config.get_configurable_options().copy()
        options.append({"printers": {
            "name": _("Printer Connections"),
            "type": "menu",
            "menu": "printers"
        }})

        self.labels['settings_menu'] = self._gtk.ScrolledWindow()
        self.labels['settings'] = Gtk.Grid()
        self.labels['settings_menu'].add(self.labels['settings'])
        for option in options:
            name = list(option)[0]
            self.add_option('settings', self.settings, name, option[name])

        self.labels['printers_menu'] = self._gtk.ScrolledWindow()
        self.labels['printers'] = Gtk.Grid()
        self.labels['printers_menu'].add(self.labels['printers'])
        self.printers = {}
        for printer in self._config.get_printers():
            logging.debug("Printer: %s" % printer)
            pname = list(printer)[0]
            self.printers[pname] = {
                "name": pname,
                "section": "printer %s" % pname,
                "type": "printer",
                "moonraker_host": printer[pname]['moonraker_host'],
                "moonraker_port": printer[pname]['moonraker_port'],
            }
            self.add_option("printers", self.printers, pname, self.printers[pname])

        self.content.add(self.labels['settings_menu'])

    def activate(self):
        while len(self.menu) > 1:
            self.unload_menu()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False

    def add_option(self, boxname, opt_array, opt_name, option):
        if option['type'] is None:
            return

        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (option['name']))
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.set_valign(Gtk.Align.CENTER)

        dev.add(labels)
        if option['type'] == "binary":
            box = Gtk.Box()
            box.set_vexpand(False)
            switch = Gtk.Switch()
            switch.set_hexpand(False)
            switch.set_vexpand(False)
            switch.set_active(self._config.get_config().getboolean(option['section'], opt_name))
            switch.connect("notify::active", self.switch_config_option, option['section'], opt_name,
                           option['callback'] if "callback" in option else None)
            switch.set_property("width-request", round(self._gtk.get_font_size() * 7))
            switch.set_property("height-request", round(self._gtk.get_font_size() * 3.5))
            box.add(switch)
            dev.add(box)
        elif option['type'] == "dropdown":
            dropdown = Gtk.ComboBoxText()
            i = 0
            for opt in option['options']:
                dropdown.append(opt['value'], opt['name'])
                if opt['value'] == self._config.get_config()[option['section']].get(opt_name, option['value']):
                    dropdown.set_active(i)
                i += 1
            dropdown.connect("changed", self.on_dropdown_change, option['section'], opt_name,
                             option['callback'] if "callback" in option else None)
            dropdown.set_entry_text_column(0)
            dev.add(dropdown)
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            val = int(self._config.get_config().get(option['section'], opt_name, fallback=option['value']))
            adj = Gtk.Adjustment(val, option['range'][0], option['range'][1], option['step'], option['step'] * 5)
            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
            scale.set_hexpand(True)
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            scale.set_property("width-request", round(self._screen.width / 2.2))
            dev.add(scale)
        elif option['type'] == "printer":
            logging.debug("Option: %s" % option)
            box = Gtk.Box()
            box.set_vexpand(False)
            label = Gtk.Label()
            url = "%s:%s" % (option['moonraker_host'], option['moonraker_port'])
            label.set_markup("<big>%s</big>\n%s" % (option['name'], url))
            box.add(label)
            dev.add(box)
        elif option['type'] == "menu":
            open = self._gtk.ButtonImage("settings", None, "color3")
            open.connect("clicked", self.load_menu, option['menu'])
            open.set_hexpand(False)
            open.set_halign(Gtk.Align.END)
            dev.add(open)

        frame.add(dev)
        frame.show_all()

        opt_array[opt_name] = {
            "name": option['name'],
            "row": frame
        }

        opts = sorted(opt_array)
        opts = sorted(list(opt_array), key=lambda x: opt_array[x]['name'])
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()
