import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGtk import KlippyGtk
from panels.menu import MenuPanel

logger = logging.getLogger("KlipperScreen.MainMenu")

def create_panel(*args):
    return MainPanel(*args)

class MainPanel(MenuPanel):

    def initialize(self, panel_name, items, extrudercount):
        print("### Making MainMenu")

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)
        grid = KlippyGtk.HomogeneousGrid()
        grid.set_size_request(self._screen.width, self._screen.height)

        # Create Extruders and bed icons
        eq_grid = KlippyGtk.HomogeneousGrid()


        i = 0
        for x in self._printer.get_tools():
            if i > 3:
                break
            self.labels[x] = KlippyGtk.ButtonImage("extruder-"+str(i+1), KlippyGtk.formatTemperatureString(0, 0))
            eq_grid.attach(self.labels[x], i%2, i/2, 1, 1)
            i += 1

        self.labels['heater_bed'] = KlippyGtk.ButtonImage("bed", KlippyGtk.formatTemperatureString(0, 0))

        width = 2 if i > 1 else 1
        eq_grid.attach(self.labels['heater_bed'], 0, i/2+1, width, 1)

        grid.attach(eq_grid, 0, 0, 1, 1)

        self.items = items
        self.create_menu_items()

        self.grid = Gtk.Grid()
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(True)

        grid.attach(self.arrangeMenuItems(items, 2, True), 1, 0, 1, 1)
        self.grid = grid

        self.target_temps = {
            "heater_bed": 0,
            "extruder": 0
        }
        self.layout.put(grid, 0, 0)

        self._screen.add_subscription(panel_name)

    def activate(self):
        return

    def update_temp(self, dev, temp, target):
        if dev in self.labels:
            self.labels[dev].set_label(KlippyGtk.formatTemperatureString(temp, target))

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        self.update_temp("heater_bed",
            self._printer.get_dev_stat("heater_bed","temperature"),
            self._printer.get_dev_stat("heater_bed","target")
        )
        for x in self._printer.get_tools():
            self.update_temp(x,
                self._printer.get_dev_stat(x,"temperature"),
                self._printer.get_dev_stat(x,"target")
            )
        return
