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

        # Create a scroll window for the macros
        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        # Create a grid for all macros
        self.labels['macros'] = Gtk.Grid()
        scroll.add(self.labels['macros'])

        sort = Gtk.Label(_("Sort:"))
        sort.set_hexpand(False)
        self.sort_lbl = _("Name")
        self.sort_btn = self._gtk.Button(self.sort_lbl + self.sort_char[0], "color1")
        self.sort_btn.connect("clicked", self.change_sort)
        self.sort_btn.set_hexpand(True)
        #adjust = self._gtk.ButtonImage('fine-tune', '', "color2", 1, Gtk.PositionType.LEFT, False)

        sbox = Gtk.HBox()
        sbox.set_vexpand(False)
        sbox.pack_start(sort, False, False, 5)
        sbox.pack_start(self.sort_btn, True, True, 5)
        #sbox.pack_start(adjust, True, True, 5)

        # Create a box to contain all of the above
        box = Gtk.VBox()
        box.set_vexpand(True)
        box.pack_start(sbox, False, False, 0)
        box.pack_start(scroll, True, True, 0)

        self.content.add(box)

    def activate(self):
        self.reload_macros()

    def add_gcode_macro(self, macro):
        # Support for hiding macros by name
        if macro.startswith("_"):
            return

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (macro))
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
        self.labels['macros'].show_all()

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
        self.loaded_macros = []
        self.load_gcode_macros()
