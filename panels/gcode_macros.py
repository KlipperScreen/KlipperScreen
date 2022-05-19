import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, GLib, Pango

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return MacroPanel(*args)


class MacroPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.macros = {}
        self.loaded_macros = []
        self.sort_char = [" ↑", " ↓"]
        self.sort_reverse = False

        macros_box = self.create_box('macros')
        self.labels['shown_box'] = self.create_box('shown')

        sort = Gtk.Label(_("Sort:"))
        sort.set_hexpand(False)
        self.sort_lbl = _("Name")
        self.sort_btn = self._gtk.Button(self.sort_lbl + self.sort_char[0], "color1")
        self.sort_btn.connect("clicked", self.change_sort)
        self.sort_btn.set_hexpand(True)
        adjust = self._gtk.ButtonImage("settings", None, "color2", 1, Gtk.PositionType.LEFT, False)
        adjust.connect("clicked", self.load_menu, 'shown')
        adjust.set_hexpand(False)

        sbox = Gtk.HBox()
        sbox.set_vexpand(False)
        sbox.pack_start(sort, False, False, 5)
        sbox.pack_start(self.sort_btn, True, True, 5)
        sbox.pack_start(adjust, True, True, 5)

        self.labels['main_box'] = Gtk.VBox()
        self.labels['main_box'].set_vexpand(True)
        self.labels['main_box'].pack_start(sbox, False, False, 0)
        self.labels['main_box'].pack_start(macros_box, True, True, 0)

        self.menu = ['main_box']
        self.content.add(self.labels['main_box'])

    def activate(self):
        while len(self.menu) > 1:
            self.unload_menu()
        self.reload_macros()

    def add_gcode_macro(self, macro):
        # Support for hiding macros by name
        if macro.startswith("_"):
            return

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % macro)
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        btn = self._gtk.ButtonImage("resume", None, "color3")
        btn.connect("clicked", self.run_gcode_macro, macro)
        btn.set_hexpand(False)
        btn.set_halign(Gtk.Align.END)

        labels = Gtk.VBox()
        labels.add(name)

        dev = Gtk.HBox(spacing=5)
        dev.add(labels)
        dev.add(btn)

        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")
        frame.add(dev)

        self.macros[macro] = {
            "row": frame
        }

        macros = sorted(self.macros, reverse=self.sort_reverse, key=str.casefold)
        pos = macros.index(macro)

        self.loaded_macros.append(macro)
        self.labels['macros'].insert_row(pos)
        self.labels['macros'].attach(self.macros[macro]['row'], 0, pos, 1, 1)

    def run_gcode_macro(self, widget, macro):
        self._screen._ws.klippy.gcode_script(macro)

    def change_sort(self, widget):
        self.sort_reverse ^= True
        if self.sort_reverse:
            self.sort_btn.set_label(self.sort_lbl + self.sort_char[1])
        else:
            self.sort_btn.set_label(self.sort_lbl + self.sort_char[0])
        self.sort_btn.show()

        GLib.idle_add(self.reload_macros)

    def reload_macros(self):
        self.labels['macros'].remove_column(0)
        self.macros = {}
        self.loaded_macros = []
        self.allmacros = {}
        self.labels['shown'].remove_column(0)
        self.load_gcode_macros()

    def load_gcode_macros(self):
        macros = self._screen.printer.get_gcode_macros()
        section_name = "displayed_macros %s" % self._screen.connected_printer
        logging.info("Macro section name [%s]" % section_name)

        for x in macros:
            macro = x[12:].strip()

            if macro in self.loaded_macros:
                continue

            if (section_name not in self._config.get_config().sections() or
                    self._config.get_config().getboolean(section_name, macro.lower(), fallback=True)):
                self.add_gcode_macro(macro)

        for macro in self._printer.get_config_section_list("gcode_macro "):
            macro = macro[12:]
            # Support for hiding macros by name
            if macro.startswith("_"):
                continue

            self.allmacros[macro] = {
                "name": macro,
                "section": "displayed_macros %s" % self._screen.connected_printer,
            }
        for macro in list(self.allmacros):
            self.add_option('shown', self.allmacros, macro, self.allmacros[macro])

        self.labels['macros'].show_all()

    def add_option(self, boxname, opt_array, opt_name, option):
        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (option['name']))
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        box = Gtk.Box()
        box.set_vexpand(False)
        switch = Gtk.Switch()
        switch.set_hexpand(False)
        switch.set_vexpand(False)
        switch.set_active(self._config.get_config().getboolean(option['section'], opt_name, fallback=True))
        switch.connect("notify::active", self.switch_config_option, option['section'], opt_name)
        switch.set_property("width-request", round(self._gtk.get_font_size() * 7))
        switch.set_property("height-request", round(self._gtk.get_font_size() * 3.5))
        box.add(switch)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.set_valign(Gtk.Align.CENTER)
        dev.add(name)
        dev.add(box)

        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")
        frame.add(dev)
        frame.show_all()
        opt_array[opt_name] = {
            "name": option['name'],
            "row": frame
        }

        opts = sorted(self.allmacros, key=str.casefold)
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

    def create_box(self, name):
        # Create a scroll window for the macros
        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        # Create a grid for all macros
        self.labels[name] = Gtk.Grid()
        scroll.add(self.labels[name])

        # Create a box to contain all of the above
        box = Gtk.VBox(spacing=0)
        box.set_vexpand(True)
        box.pack_start(scroll, True, True, 0)
        return box

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            self.reload_macros()
            return True
        return False

    def switch_config_option(self, switch, gparam, section, option):
        logging.debug("[%s] %s toggled %s" % (section, option, switch.get_active()))
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, option, "True" if switch.get_active() else "False")
        self._config.save_user_config_options()
