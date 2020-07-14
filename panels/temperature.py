import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk

class TemperaturePanel:
    _screen = None
    labels = {}

    def __init__(self, screen):
        self._screen = screen


    def initialize(self):
        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)




        b = KlippyGtk.ButtonImage('back', 'Back')
        b.connect("clicked", self._screen._menu_go_back)
        grid.attach(b, 3, 2, 1, 1)

        self.grid = grid

    def get(self):
        # Return gtk item
        return self.grid
