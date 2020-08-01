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

        for i in range(extrudercount):
            if i > 3:
                break
            self.labels["tool" + str(i)] = KlippyGtk.ButtonImage("extruder-"+str(i+1), KlippyGtk.formatTemperatureString(0, 0))
            eq_grid.attach(self.labels["tool" + str(i)], i%2, i/2, 1, 1)

        self.labels['bed'] = KlippyGtk.ButtonImage("bed", KlippyGtk.formatTemperatureString(0, 0))

        width = 2 if i > 0 else 1
        eq_grid.attach(self.labels['bed'], 0, i/2+1, width, 1)

        grid.attach(eq_grid, 0, 0, 1, 1)
        grid.attach(self.arrangeMenuItems(items, 2, True), 1, 0, 1, 1)
        self.grid = grid

        self._screen.add_subscription(panel_name)

    def get(self):
        return self.grid

    def update_temp(self, dev, temp, target):
        if dev in self.labels:
            self.labels[dev].set_label(KlippyGtk.formatTemperatureString(temp, target))

    def process_update(self, data):
        if "heater_bed" in data:
            self.update_temp(
                "bed",
                round(data['heater_bed']['temperature'],1),
                round(data['heater_bed']['target'],1)
            )
        if "extruder" in data:
            self.update_temp(
                "tool0",
                round(data['extruder']['temperature'],1),
                round(data['extruder']['target'],1)
            )
