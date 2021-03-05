import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.PrinterSelect")

def create_panel(*args):
    return PrinterSelect(*args)

class PrinterSelect(ScreenPanel):
    def __init__(self, screen, title, back=True, action_bar=True, printer_name=True):
        super().__init__(screen, title, False, False, False)

    def initialize(self, panel_name):
        _ = self.lang.gettext

        printers = self._config.get_printers()

        box = Gtk.Box()
        self.content.add(box)

        i = 1
        for printer in printers:
            name = list(printer)[0]
            self.labels[name] = self._gtk.ButtonImage("extruder",name,"color%s" % (i%4))
            self.labels[name].connect("clicked", self._screen.connect_printer_widget, name)
            box.add(self.labels[name])
            i += 1
