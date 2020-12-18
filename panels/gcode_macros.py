import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.Macro")

def create_panel(*args):
    return MacroPanel(*args)

class MacroPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.macros = {}

        # Create a scroll window for the macros
        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)

        # Create a grid for all macros
        self.labels['macros'] = Gtk.Grid()
        scroll.add(self.labels['macros'])

        # Create a box to contain all of the above
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.pack_start(scroll, True, True, 0)

        self.load_gcode_macros()

        self.content.add(box)

    def add_gcode_macro(self, macro):

        frame = Gtk.Frame()
        frame.set_property("shadow-type",Gtk.ShadowType.NONE)

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (macro))
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        open = self._gtk.ButtonImage("open",None,"color3")
        open.connect("clicked", self.run_gcode_macro, macro)
        open.set_hexpand(False)
        open.set_halign(Gtk.Align.END)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_margin_top(10)
        dev.set_margin_end(15)
        dev.set_margin_start(15)
        dev.set_margin_bottom(10)
        dev.set_hexpand(True)
        dev.set_vexpand(False)

        dev.add(labels)
        dev.add(open)
        frame.add(dev)

        self.macros[macro] = {
            "row": frame
        }

        macros = sorted(self.macros)
        pos = macros.index(macro)

        self.labels['macros'].insert_row(pos)
        self.labels['macros'].attach(self.macros[macro]['row'], 0, pos, 1, 1)
        self.labels['macros'].show_all()

    def load_gcode_macros(self):
        macros = self._screen.printer.get_gcode_macros()
        for x in macros:
            self.add_gcode_macro(x[12:])

    def run_gcode_macro(self, widget, macro):
        self._screen._ws.klippy.gcode_script(macro)
