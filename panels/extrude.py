import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return ExtrudePanel(*args)

class ExtrudePanel(ScreenPanel):
    distance = 5
    distances = ['5', '10', '15', '25']

    def initialize(self, panel_name):
        _ = self.lang.gettext

        self.load_filament = self.unload_filament = False
        self.find_gcode_macros()
        self.speed = 1
        self.speeds = ['1', '2', '5', '25']

        grid = Gtk.Grid()

        self.labels['extrude'] = self._gtk.ButtonImage("extrude", _("Extrude"), "color4")
        self.labels['extrude'].connect("clicked", self.extrude, "+")
        if not self.load_filament:
            self.labels['load'] = self._gtk.ButtonImage("arrow-down", _("Load"))
        else:
            self.labels['load'] = self._gtk.ButtonImage("arrow-down", _("Load"), "color3")
        self.labels['load'].connect("clicked", self.load_unload, "+", self.load_filament)
        if not self.unload_filament:
            self.labels['unload'] = self._gtk.ButtonImage("arrow-up", _("Unload"))
        else:
            self.labels['unload'] = self._gtk.ButtonImage("arrow-up", _("Unload"), "color2")
        self.labels['unload'].connect("clicked", self.load_unload, "-", self.unload_filament)
        self.labels['retract'] = self._gtk.ButtonImage("retract", _("Retract"), "color1")
        self.labels['retract'].connect("clicked", self.extrude, "-")
        self.labels['temperature'] = self._gtk.ButtonImage("heat-up", _("Temperature"), "color4")
        self.labels['temperature'].connect("clicked", self.menu_item_clicked, "temperature", {
            "name": "Temperature",
            "panel": "temperature"
        })

        extgrid = self._gtk.HomogeneousGrid()
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        limit = 5
        for i, extruder in enumerate(self._printer.get_tools()):
            if self._printer.extrudercount > 1:
                self.labels[extruder] = self._gtk.ButtonImage("extruder-%s" % i, _("Tool") + " %s" % str(i))
            else:
                self.labels[extruder] = self._gtk.ButtonImage("extruder", _("Tool"))
            self.labels[extruder].connect("clicked", self.change_extruder, extruder)
            if extruder == self.current_extruder:
                self.labels[extruder].get_style_context().add_class("button_active")
            if i < limit:
                extgrid.attach(self.labels[extruder], i, 0, 1, 1)
        if i < (limit - 1):
            extgrid.attach(self.labels['temperature'], i+1, 0, 1, 1)


        grid.attach(extgrid, 0, 0, 4, 1)
        if self._screen.vertical_mode:
            grid.attach(self.labels['extrude'], 0, 1, 2, 1)
            grid.attach(self.labels['retract'], 2, 1, 2, 1)
            grid.attach(self.labels['load'], 0, 2, 2, 1)
            grid.attach(self.labels['unload'], 2, 2, 2, 1)
        else:
            grid.attach(self.labels['extrude'], 0, 1, 1, 1)
            grid.attach(self.labels['load'], 1, 1, 1, 1)
            grid.attach(self.labels['unload'], 2, 1, 1, 1)
            grid.attach(self.labels['retract'], 3, 1, 1, 1)

        distgrid = Gtk.Grid()
        j = 0
        for i in self.distances:
            self.labels["dist"+str(i)] = self._gtk.ToggleButton(i)
            self.labels["dist"+str(i)].connect("clicked", self.change_distance, i)
            ctx = self.labels["dist"+str(i)].get_style_context()
            if ((self._screen.lang_ltr is True and j == 0) or
                    (self._screen.lang_ltr is False and j == len(self.distances)-1)):
                ctx.add_class("distbutton_top")
            elif ((self._screen.lang_ltr is False and j == 0) or
                    (self._screen.lang_ltr is True and j == len(self.distances)-1)):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "5":
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels["dist"+str(i)], j, 0, 1, 1)
            j += 1
        self.labels["dist5"].set_active(True)

        speedgrid = Gtk.Grid()
        j = 0
        for i in self.speeds:
            self.labels["speed"+str(i)] = self._gtk.ToggleButton(_(i))
            self.labels["speed"+str(i)].connect("clicked", self.change_speed, i)
            ctx = self.labels["speed"+str(i)].get_style_context()
            if ((self._screen.lang_ltr is True and j == 0) or
                    (self._screen.lang_ltr is False and j == len(self.speeds)-1)):
                ctx.add_class("distbutton_top")
            elif ((self._screen.lang_ltr is False and j == 0) or
                    (self._screen.lang_ltr is True and j == len(self.speeds)-1)):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "2":
                ctx.add_class("distbutton_active")
            speedgrid.attach(self.labels["speed" + str(i)], j, 0, 1, 1)
            j += 1
        self.labels["speed2"].set_active(True)

        distbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['extrude_dist'] = Gtk.Label(_("Distance (mm)"))
        distbox.pack_start(self.labels['extrude_dist'], True, True, 0)
        distbox.add(distgrid)
        speedbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['extrude_speed'] = Gtk.Label(_("Speed (mm/s)"))
        speedbox.pack_start(self.labels['extrude_speed'], True, True, 0)
        speedbox.add(speedgrid)

        grid.set_column_homogeneous(True)
        if self._screen.vertical_mode:
            grid.attach(distbox, 0, 3, 4, 1)
            grid.attach(speedbox, 0, 4, 4, 1)
        else:
            grid.attach(distbox, 0, 2, 2, 1)
            grid.attach(speedbox, 2, 2, 2, 1)

        self.content.add(grid)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for x in self._printer.get_tools():
            self.update_temp(
                x,
                self._printer.get_dev_stat(x, "temperature"),
                self._printer.get_dev_stat(x, "target")
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
        speed = str(int(self.speed) * 60)
        print(KlippyGcodes.extrude(dist, speed))

        self._screen._ws.klippy.gcode_script(KlippyGcodes.EXTRUDE_REL)
        self._screen._ws.klippy.gcode_script(KlippyGcodes.extrude(dist, speed))

    def load_unload(self, widget, dir, found):
        if dir == "-":
            if not found:
                self._screen.show_popup_message("Macro UNLOAD_FILAMENT not found")
            else:
                self._screen._ws.klippy.gcode_script("UNLOAD_FILAMENT SPEED=" + str(int(self.speed) * 60))
        if dir == "+":
            if not found:
                self._screen.show_popup_message("Macro LOAD_FILAMENT not found")
            else:
                self._screen._ws.klippy.gcode_script("LOAD_FILAMENT SPEED=" + str(int(self.speed) * 60))

    def find_gcode_macros(self):
        macros = self._screen.printer.get_gcode_macros()
        for x in macros:
            macro = x[12:].strip()
            macro = macro.upper()
            if macro == "LOAD_FILAMENT":
                logging.info("Found %s" % macro)
                self.load_filament = True
            if macro == "UNLOAD_FILAMENT":
                logging.info("Found %s" % macro)
                self.unload_filament = True
