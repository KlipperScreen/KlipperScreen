import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from panels.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.PreheatPanel")

class PreheatPanel(ScreenPanel):
    active_heaters = []

    def initialize(self, panel_name):
        self.preheat_options = self._screen._config['preheat_options']

        grid = KlippyGtk.HomogeneousGrid()

        eq_grid = KlippyGtk.HomogeneousGrid()
        i = 0
        for x in self._printer.get_tools():
            if i > 3:
                break
            elif i == 0:
                primary_tool = x
            self.labels[x] = KlippyGtk.ToggleButtonImage("extruder-"+str(i+1), KlippyGtk.formatTemperatureString(0, 0))
            self.labels[x].connect('clicked', self.select_heater, x)
            eq_grid.attach(self.labels[x], i%2, i/2, 1, 1)
            i += 1

        self.labels["heater_bed"] = KlippyGtk.ToggleButtonImage("bed", KlippyGtk.formatTemperatureString(0, 0))
        self.labels["heater_bed"].connect('clicked', self.select_heater, "heater_bed")
        width = 2 if i > 1 else 1
        eq_grid.attach(self.labels["heater_bed"], 0, i/2+1, width, 1)

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

    def activate(self):
        for x in self._printer.get_tools():
            if x not in self.active_heaters:
                self.select_heater(None, x)

        if "heater_bed" not in self.active_heaters:
            self.select_heater(None, "heater_bed")

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
                if heater.startswith('heater_bed'):
                    self._screen._ws.klippy.set_bed_temp(0)
                    self._printer.set_dev_stat(heater,"target", 0)
                else:
                    self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(heater), 0)
                    self._printer.set_dev_stat(heater,"target", 0)
            return

        for heater in self.active_heaters:
            if heater.startswith('heater_bed'):
                print ("Setting %s to %d" % (heater, self.preheat_options[setting]['bed']))
                self._screen._ws.klippy.set_bed_temp(self.preheat_options[setting]["bed"])
                self._printer.set_dev_stat(heater,"target", int(self.preheat_options[setting]["bed"]))
            else:
                print ("Setting %s to %d" % (heater, self.preheat_options[setting]['tool']))
                self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(heater),
                    self.preheat_options[setting]["tool"])
                self._printer.set_dev_stat(heater,"target", int(self.preheat_options[setting]["tool"]))

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
