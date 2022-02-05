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

        grid = self._gtk.HomogeneousGrid()
        self.content.add(grid)

        length = len(printers)
        if length == 4:
            # Arrange 2 x 2
            columns = 2
        elif length > 4 and length <= 6:
            # Arrange 3 x 2
            columns = 3
        else:
            columns = 4

        for i, printer in enumerate(printers):
            name = list(printer)[0]
            self.labels[name] = self._gtk.ButtonImage("extruder", name, "color%s" % (1 + i % 4))
            self.labels[name].connect("clicked", self._screen.connect_printer_widget, name)
            col = i % columns
            row = int(i/columns)
            grid.attach(self.labels[name], col, row, 1, 1)
