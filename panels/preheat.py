import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return PreheatPanel(*args)

class PreheatPanel(ScreenPanel):
    active_heaters = []

    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.preheat_options = self._screen._config.get_preheat_options()
        logging.debug("Preheat options: %s" % self.preheat_options)

        grid = self._gtk.HomogeneousGrid()

        eq_grid = Gtk.Grid()
        eq_grid.set_hexpand(True)
        eq_grid.set_vexpand(True)

        self.heaters = []
        i = 0
        for x in self._printer.get_tools():
            if i == 0:
                primary_tool = x
            self.labels[x] = self._gtk.ToggleButtonImage("extruder-"+str(i), self._gtk.formatTemperatureString(0, 0))
            self.heaters.append(x)
            i += 1

        add_heaters = self._printer.get_heaters()
        for h in add_heaters:
            if h == "heater_bed":
                self.labels[h] = self._gtk.ButtonImage("bed", self._gtk.formatTemperatureString(0, 0))
            else:
                name = " ".join(h.split(" ")[1:])
                self.labels[h] = self._gtk.ButtonImage("heat-up", name)
            self.heaters.append(h)

        i = 0
        cols = 3 if len(self.heaters) > 4 else (1 if len(self.heaters) <= 2 else 2)
        for h in self.heaters:
            self.labels[h].connect('clicked', self.select_heater, h)
            eq_grid.attach(self.labels[h], i%cols, int(i/cols), 1, 1)
            i += 1


        self.labels["control_grid"] = self._gtk.HomogeneousGrid()

        i = 0
        for option in  self.preheat_options:
            self.labels[option] = self._gtk.Button(option, "color%d" % ((i%4)+1))
            self.labels[option].connect("clicked", self.set_temperature, option)
            self.labels['control_grid'].attach(
                self.labels[option],
                i%2, int(i/2), 1, 1)
            i += 1


        cooldown = self._gtk.ButtonImage('cool-down', _('Cooldown'))
        cooldown.connect("clicked", self.set_temperature, "cooldown")

        row = int(i/2) if i%2 == 0 else int(i/2)+1
        self.labels["control_grid"].attach(cooldown, i%2, int(i/2), 1, 1)


        grid.attach(eq_grid, 0, 0, 1, 1)
        grid.attach(self.labels["control_grid"], 1, 0, 1, 1)

        self.content.add(grid)

        self._screen.add_subscription(panel_name)

    def activate(self):
        for x in self._printer.get_tools():
            if x not in self.active_heaters:
                self.select_heater(None, x)

        for h in self._printer.get_heaters():
            if h not in self.active_heaters:
                self.select_heater(None, h)

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
                if heater.startswith('heater_generic '):
                    self._screen._ws.klippy.set_heater_temp(" ".join(heater.split(" ")[1:]), 0)
                elif heater.startswith('heater_bed'):
                    self._screen._ws.klippy.set_bed_temp(0)
                    self._printer.set_dev_stat(heater,"target", 0)
                else:
                    self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(heater), 0)
                    self._printer.set_dev_stat(heater,"target", 0)
            return

        for heater in self.active_heaters:
            if heater.startswith('heater_generic '):
                print ("Setting %s to %d" % (heater, self.preheat_options[setting]['heater_generic']))
                self._screen._ws.klippy.set_heater_temp(" ".join(heater.split(" ")[1:]),
                    self.preheat_options[setting]["heater_generic"])
            elif heater.startswith('heater_bed'):
                print ("Setting %s to %d" % (heater, self.preheat_options[setting]['bed']))
                self._screen._ws.klippy.set_bed_temp(self.preheat_options[setting]["bed"])
                self._printer.set_dev_stat(heater,"target", int(self.preheat_options[setting]["bed"]))
            else:
                print ("Setting %s to %d" % (heater, self.preheat_options[setting]['extruder']))
                self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(heater),
                    self.preheat_options[setting]["extruder"])
                self._printer.set_dev_stat(heater,"target", int(self.preheat_options[setting]["extruder"]))

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for x in self._printer.get_tools():
            self.update_temp(x,
                self._printer.get_dev_stat(x,"temperature"),
                self._printer.get_dev_stat(x,"target")
            )
        for h in self._printer.get_heaters():
            self.update_temp(h,
                self._printer.get_dev_stat(h,"temperature"),
                self._printer.get_dev_stat(h,"target"),
                None if h == "heater_bed" else " ".join(h.split(" ")[1:])
            )
