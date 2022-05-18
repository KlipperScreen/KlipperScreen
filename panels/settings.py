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
        self.menu_cur = 'main_box'
        self.menu = ['main_box']

        self.labels['main_box'] = self.create_box('main')

        printbox = Gtk.Box(spacing=0)
        printbox.set_vexpand(False)
        self.labels['add_printer_button'] = self._gtk.Button(_("Add Printer"), "color1")
        self.labels['printers_box'] = self.create_box('printers', printbox)

        options = self._config.get_configurable_options().copy()
        options.append({"printers": {
            "name": _("Printer Connections"),
            "type": "menu",
            "menu": "printers"
        }})

        for option in options:
            name = list(option)[0]
            self.add_option('main', self.settings, name, option[name])

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

        self.content.add(self.labels['main_box'])

    def activate(self):
        while len(self.menu) > 1:
            self.unload_menu()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False

    def create_box(self, name, insert=None):
        # Create a scroll window for the options
        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        # Create a grid for all options
        self.labels[name] = Gtk.Grid()
        scroll.add(self.labels[name])

        # Create a box to contain all of the above
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        if insert is not None:
            box.pack_start(insert, False, False, 0)
        box.pack_start(scroll, True, True, 0)
        return box

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
            switch.set_property("width-request", round(self._gtk.get_font_size()*7))
            switch.set_property("height-request", round(self._gtk.get_font_size()*3.5))
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
            val = int(self._config.get_config().get(option['section'], opt_name, fallback=option['value']))
            adj = Gtk.Adjustment(val, option['range'][0], option['range'][1], option['step'], option['step']*5)
            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
            scale.set_hexpand(True)
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            scale.set_property("width-request", round(self._screen.width/2.2))
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

    def load_menu(self, widget, name):
        if ("%s_box" % name) not in self.labels:
            return

        for child in self.content.get_children():
            self.content.remove(child)

        self.menu.append('%s_box' % name)
        self.content.add(self.labels[self.menu[-1]])
        self.content.show_all()

    def unload_menu(self, widget=None):
        logging.debug("self.menu: %s" % self.menu)
        if len(self.menu) <= 1 or self.menu[-2] not in self.labels:
            return

        self.menu.pop()
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels[self.menu[-1]])
        self.content.show_all()

    def on_dropdown_change(self, combo, section, option, callback=None):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            value = model[tree_iter][1]
            logging.debug("[%s] %s changed to %s" % (section, option, value))
            self._config.set(section, option, value)
            self._config.save_user_config_options()
            if callback is not None:
                callback(value)

    def scale_moved(self, widget, event, section, option):
        logging.debug("[%s] %s changed to %s" % (section, option, widget.get_value()))
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, option, str(int(widget.get_value())))
        self._config.save_user_config_options()

    def switch_config_option(self, switch, gparam, section, option, callback=None):
        logging.debug("[%s] %s toggled %s" % (section, option, switch.get_active()))
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, option, "True" if switch.get_active() else "False")
        self._config.save_user_config_options()
        if callback is not None:
            callback(switch.get_active())
