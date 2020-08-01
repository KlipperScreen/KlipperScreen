import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from panels.screen_panel import ScreenPanel


class PreheatPanel(ScreenPanel):
    active_heaters = []

    def initialize(self, panel_name):
        self.preheat_options = self._screen._config['preheat_options']

        grid = KlippyGtk.HomogeneousGrid()

        eq_grid = KlippyGtk.HomogeneousGrid()
        for i in range(self._screen.extrudercount):
            if i > 3:
                break
            self.labels["tool" + str(i)] = KlippyGtk.ToggleButtonImage("extruder-"+str(i+1), KlippyGtk.formatTemperatureString(0, 0))
            self.labels["tool" + str(i)].connect('clicked', self.select_heater, "tool"+str(i))
            eq_grid.attach(self.labels["tool" + str(i)], i%2, i/2, 1, 1)

        self.labels['bed'] = KlippyGtk.ToggleButtonImage("bed", KlippyGtk.formatTemperatureString(0, 0))
        self.labels['bed'].connect('clicked', self.select_heater, "bed")
        width = 2 if i > 0 else 1
        eq_grid.attach(self.labels['bed'], 0, i/2+1, width, 1)

        self.labels["control_grid"] = KlippyGtk.HomogeneousGrid()

        i = 0
        for option in  self.preheat_options:
            self.labels[option] = KlippyGtk.Button(option, "color%d" % ((i%4)+1))
            self.labels[option].connect("clicked", self.set_temperature, option)
            self.labels['control_grid'].attach(
                self.labels[option],
                i%2, int(i/2), 1, 1)
            i += 1


        cooldown = KlippyGtk.ButtonImage('cool-down', 'Cooldown')
        cooldown.connect("clicked", self.set_temperature, "cooldown")

        b = KlippyGtk.ButtonImage('back', 'Back')
        b.connect("clicked", self._screen._menu_go_back)

        row = int(i/2) if i%2 == 0 else int(i/2)+1
        self.labels["control_grid"].attach(cooldown, 0, row, 1, 1)
        self.labels["control_grid"].attach(b, 1, row, 1, 1)


        grid.attach(eq_grid, 0, 0, 1, 1)
        grid.attach(self.labels["control_grid"], 1, 0, 1, 1)

        self.panel = grid

        self._screen.add_subscription(panel_name)

    def select_heater(self, widget, heater):
        if heater in self.active_heaters:
            self.active_heaters.pop(self.active_heaters.index(heater))
            self.labels[heater].get_style_context().remove_class('button_active')
            return

        self.active_heaters.append(heater)
        self.labels[heater].get_style_context().add_class('button_active')

    def set_temperature(self, widget, setting):
        if setting == "cooldown":
            for heater in self.active_heaters:
                print ("Setting %s to %d" % (heater, 0))
                self._screen._ws.klippy.temperature_set(heater, 0)
            return

        for heater in self.active_heaters:
            print ("Setting %s to %d" % (heater, self.preheat_options[setting][heater[0:4]]))
            self._screen._ws.klippy.temperature_set(heater, self.preheat_options[setting][heater[0:4]])

    def process_update(self, data):
        if "heater_bed" in data:
            self.update_temp(
                "bed",
                round(data['heater_bed']['temperature'],1),
                round(data['heater_bed']['target'],1)
                )
        if "extruder" in data and data['extruder'] != "extruder":
            self.update_temp(
                "tool0",
                round(data['extruder']['temperature'],1),
                round(data['extruder']['target'],1)
            )
