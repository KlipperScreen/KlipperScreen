import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return ExtrudePanel(*args)

class ExtrudePanel(ScreenPanel):
    distance = 1
    distances = ['1','5','10','25']

    def initialize(self, panel_name):
        _ = self.lang.gettext

        self.speed = "Medium"
        self.speeds = ["Slow", "Medium", "Fast"]
        self.speed_trans = {
            "Slow": "300",
            "Medium": "800",
            "Fast": "1400"
        }

        # This line for translations only
        speed_translations = [_("Slow"), _("Medium"), _("Fast")]

        grid = self._gtk.HomogeneousGrid()

        i = 0
        self.current_extruder = self._printer.get_stat("toolhead","extruder")
        for extruder in self._printer.get_tools():
            self.labels[extruder] = self._gtk.ButtonImage("extruder-%s" % i,_("Tool") + " %s" %str(i),"color1")
            self.labels[extruder].connect("clicked", self.change_extruder, extruder)
            if extruder == self.current_extruder:
                self.labels[extruder].get_style_context().add_class("button_active")
            if i <= 3:
                grid.attach(self.labels[extruder], i, 0, 1, 1)
            i += 1

        self.labels['extrude'] = self._gtk.ButtonImage("extrude",_("Extrude"),"color3")
        self.labels['extrude'].connect("clicked", self.extrude, "+")
        self.labels['retract'] = self._gtk.ButtonImage("retract",_("Retract"),"color2")
        self.labels['retract'].connect("clicked", self.extrude, "-")
        self.labels['temperature'] = self._gtk.ButtonImage("heat-up",_("Temperature"),"color4")
        self.labels['temperature'].connect("clicked", self.menu_item_clicked, "temperature", {
            "name": "Temperature",
            "panel": "temperature"
        })

        grid.attach(self.labels['extrude'], 0, 1, 1, 1)
        grid.attach(self.labels['retract'], 3, 1, 1, 1)
        grid.attach(self.labels['temperature'], 0, 2, 1, 1)


        distgrid = Gtk.Grid()
        j = 0;
        for i in self.distances:
            self.labels["dist"+str(i)] = self._gtk.ToggleButton(i)
            self.labels["dist"+str(i)].connect("clicked", self.change_distance, i)
            ctx = self.labels["dist"+str(i)].get_style_context()
            if ((self._screen.lang_ltr == True and j == 0) or
                    (self._screen.lang_ltr == False and j == len(self.distances)-1)):
                ctx.add_class("distbutton_top")
            elif ((self._screen.lang_ltr == False and j == 0) or
                    (self._screen.lang_ltr == True and j == len(self.distances)-1)):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "1":
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels["dist"+str(i)], j, 0, 1, 1)
            j += 1
        self.labels["dist1"].set_active(True)

        speedgrid = Gtk.Grid()
        j = 0;
        for i in self.speeds:
            self.labels["speed"+str(i)] = self._gtk.ToggleButton(_(i))
            self.labels["speed"+str(i)].connect("clicked", self.change_speed, i)
            ctx = self.labels["speed"+str(i)].get_style_context()
            if ((self._screen.lang_ltr == True and j == 0) or
                    (self._screen.lang_ltr == False and j == len(self.speeds)-1)):
                ctx.add_class("distbutton_top")
            elif ((self._screen.lang_ltr == False and j == 0) or
                    (self._screen.lang_ltr == True and j == len(self.speeds)-1)):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "Medium":
                ctx.add_class("distbutton_active")
            speedgrid.attach(self.labels["speed"+str(i)], j, 0, 1, 1)
            j += 1
        self.labels["speedMedium"].set_active(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(distgrid)
        box.add(speedgrid)

        grid.attach(box, 1, 2, 2, 1)

        self.content.add(grid)
        self._screen.add_subscription(panel_name)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for x in self._printer.get_tools():
            self.update_temp(x,
                self._printer.get_dev_stat(x,"temperature"),
                self._printer.get_dev_stat(x,"target")
            )

        if ("toolhead" in data and "extruder" in data["toolhead"] and
                data["toolhead"]["extruder"] != self.current_extruder):
            for extruder in self._printer.get_tools():
                self.labels[extruder].get_style_context().remove_class("button_active")
            self.current_extruder = data["toolhead"]["extruder"]
            self.labels[self.current_extruder].get_style_context().add_class("button_active")

    def change_distance(self, widget, distance):
        if self.distance == distance:
            return
        logging.info("### Distance " + str(distance))

        ctx = self.labels["dist"+str(self.distance)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.distance = distance
        ctx = self.labels["dist"+self.distance].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.distances:
            if i == self.distance:
                continue
            self.labels["dist"+str(i)].set_active(False)

    def change_extruder(self, widget, extruder):
        if extruder == self.current_extruder:
            return

        self._screen._ws.klippy.gcode_script("T%s" % self._printer.get_tool_number(extruder))

    def change_speed(self, widget, speed):
        if self.speed == speed:
            return
        logging.info("### Speed " + str(speed))

        self.labels["speed" + str(self.speed)].get_style_context().remove_class("distbutton_active")

        self.speed = speed
        self.labels["speed" + self.speed].get_style_context().add_class("distbutton_active")
        for i in self.speeds:
            if i == self.speed:
                continue
            self.labels["speed" + str(i)].set_active(False)

    def extrude(self, widget, dir):
        dist = str(self.distance) if dir == "+" else "-" + str(self.distance)
        speed = self.speed_trans[self.speed]
        print(KlippyGcodes.extrude(dist, speed))

        self._screen._ws.klippy.gcode_script(KlippyGcodes.EXTRUDE_REL)
        self._screen._ws.klippy.gcode_script(KlippyGcodes.extrude(dist, speed))
