import logging
import re
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return MacroPanel(*args)


class MacroPanel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.sort_reverse = False
        self.sort_btn = self._gtk.Button("arrow-up", _("Name"), "color1", self.bts, Gtk.PositionType.RIGHT, 1)
        self.sort_btn.connect("clicked", self.change_sort)
        self.sort_btn.set_hexpand(True)
        self.options = {}
        self.macros = {}
        self.menu = ['macros_menu']

        adjust = self._gtk.Button("settings", " " + _("Settings"), "color2", self.bts, Gtk.PositionType.LEFT, 1)
        adjust.connect("clicked", self.load_menu, 'options', _("Settings"))
        adjust.set_hexpand(False)

        sbox = Gtk.Box()
        sbox.set_vexpand(False)
        sbox.pack_start(self.sort_btn, True, True, 5)
        sbox.pack_start(adjust, True, True, 5)

        self.labels['macros_list'] = self._gtk.ScrolledWindow()
        self.labels['macros'] = Gtk.Grid()
        self.labels['macros_list'].add(self.labels['macros'])

        self.labels['macros_menu'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['macros_menu'].set_vexpand(True)
        self.labels['macros_menu'].pack_start(sbox, False, False, 0)
        self.labels['macros_menu'].pack_start(self.labels['macros_list'], True, True, 0)

        self.content.add(self.labels['macros_menu'])
        self.labels['options_menu'] = self._gtk.ScrolledWindow()
        self.labels['options'] = Gtk.Grid()
        self.labels['options_menu'].add(self.labels['options'])

    def activate(self):
        while len(self.menu) > 1:
            self.unload_menu()
        self.reload_macros()

    def add_gcode_macro(self, macro):
        # Support for hiding macros by name
        if macro.startswith("_"):
            return

        name = Gtk.Label()
        name.set_markup(f"<big><b>{macro}</b></big>")
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.CHAR)

        btn = self._gtk.Button("resume", style="color3")
        btn.connect("clicked", self.run_gcode_macro, macro)
        btn.set_hexpand(False)
        btn.set_halign(Gtk.Align.END)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)

        row = Gtk.Box(spacing=5)
        row.get_style_context().add_class("frame-item")
        row.add(labels)
        row.add(btn)

        self.macros[macro] = {
            "row": row,
            "params": {},
        }
        pattern = r'params\.(?P<param>..*)\|default\((?P<default>..*)\).*'
        gcode = self._printer.get_macro(macro)
        if gcode and "gcode" in gcode:
            gcode = gcode["gcode"].split("\n")
        else:
            logging.debug(f"Couldn't load {macro}\n{gcode}")
            return
        i = 0
        for line in gcode:
            if line.startswith("{") and "params." in line:
                result = re.search(pattern, line)
                if result:
                    result = result.groupdict()
                    default = result["default"] if "default" in result else ""
                    entry = Gtk.Entry()
                    entry.set_text(default)
                    self.macros[macro]["params"].update({result["param"]: entry})

        for param in self.macros[macro]["params"]:
            labels.add(Gtk.Label(param))
            self.macros[macro]["params"][param].connect("focus-in-event", self._screen.show_keyboard)
            self.macros[macro]["params"][param].connect("focus-out-event", self._screen.remove_keyboard)
            labels.add(self.macros[macro]["params"][param])

    def run_gcode_macro(self, widget, macro):
        params = ""
        for param in self.macros[macro]["params"]:
            value = self.macros[macro]["params"][param].get_text()
            if value:
                params += f'{param}={value} '
        self._screen._ws.klippy.gcode_script(f"{macro} {params}")

    def change_sort(self, widget):
        self.sort_reverse ^= True
        if self.sort_reverse:
            self.sort_btn.set_image(self._gtk.Image("arrow-down", self._gtk.img_scale * self.bts))
        else:
            self.sort_btn.set_image(self._gtk.Image("arrow-up", self._gtk.img_scale * self.bts))
        self.sort_btn.show()

        GLib.idle_add(self.reload_macros)

    def reload_macros(self):
        self.labels['macros'].remove_column(0)
        self.macros = {}
        self.options = {}
        self.labels['options'].remove_column(0)
        self.load_gcode_macros()

    def load_gcode_macros(self):
        for macro in self._printer.get_gcode_macros():
            macro = macro[12:].strip()
            if macro.startswith("_"):  # Support for hiding macros by name
                continue
            self.options[macro] = {
                "name": macro,
                "section": f"displayed_macros {self._screen.connected_printer}",
            }
            show = self._config.get_config().getboolean(self.options[macro]["section"], macro.lower(), fallback=True)
            if macro not in self.macros and show:
                self.add_gcode_macro(macro)

        for macro in list(self.options):
            self.add_option('options', self.options, macro, self.options[macro])
        macros = sorted(self.macros, reverse=self.sort_reverse, key=str.casefold)
        for macro in macros:
            pos = macros.index(macro)
            self.labels['macros'].insert_row(pos)
            self.labels['macros'].attach(self.macros[macro]['row'], 0, pos, 1, 1)
            self.labels['macros'].show_all()

    def add_option(self, boxname, opt_array, opt_name, option):
        name = Gtk.Label()
        name.set_markup(f"<big><b>{option['name']}</b></big>")
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
        switch.set_property("width-request", round(self._gtk.font_size * 7))
        switch.set_property("height-request", round(self._gtk.font_size * 3.5))
        box.add(switch)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.get_style_context().add_class("frame-item")
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.set_valign(Gtk.Align.CENTER)
        dev.add(name)
        dev.add(box)

        opt_array[opt_name] = {
            "name": option['name'],
            "row": dev
        }

        opts = sorted(self.options, key=str.casefold)
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            self.reload_macros()
            return True
        return False
