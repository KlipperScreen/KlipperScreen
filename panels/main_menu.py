import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from panels.menu import MenuPanel

class MainPanel(MenuPanel):

    def initialize(self, panel_name, items, extrudercount):
        print("### Making MainMenu")
        grid = KlippyGtk.HomogeneousGrid()

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
        grid.attach(self.arrangeMenuItems(items, 2, True), 1, 0, 1, 1)
        self.grid = grid

        self.target_temps = {
            "heater_bed": 0,
            "extruder": 0
        }

        self._screen.add_subscription(panel_name)

    def get(self):
        return self.grid

    def update_temp(self, dev, temp, target):
        if dev in self.labels:
            self.labels[dev].set_label(KlippyGtk.formatTemperatureString(temp, target))

    def process_update(self, data):
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
