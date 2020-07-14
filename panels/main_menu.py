import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from menu import MenuPanel

class MainPanel(MenuPanel):

    def initialize(self, items):
        print "### Making MainMenu"
        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)

        # Create Extruders and bed icons
        eq_grid = Gtk.Grid()
        eq_grid.set_row_homogeneous(True)
        eq_grid.set_column_homogeneous(True)

        for i in range(self._screen.number_tools):
            self.labels["tool" + str(i)] = KlippyGtk.ButtonImage("extruder-"+str(i+1), KlippyGtk.formatTemperatureString(0, 0))
            eq_grid.attach(self.labels["tool" + str(i)], 0, 0, 1, 1)

        self.labels['bed'] = KlippyGtk.ButtonImage("bed", KlippyGtk.formatTemperatureString(0, 0))
        eq_grid.attach(self.labels['bed'], 0, 1, 1, 1)

        grid.attach(eq_grid, 0, 0, 1, 1)
        grid.attach(self.arrangeMenuItems(items, 2, True), 1, 0, 1, 1)
        self.grid = grid

    #def get(self):
    #    return self.grid
