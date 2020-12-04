import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.FineTunePanel")

def create_panel(*args):
    return FineTunePanel(*args)

class FineTunePanel(ScreenPanel):
    user_selecting = False

    bs = 0
    bs_delta = "0.05"
    bs_deltas = ["0.01","0.05"]
    percent_delta = 1
    percent_deltas = ['1','5','10','25']
    fan = 100

    extrusion = 0
    speed = 0

    def initialize(self, panel_name):
        _ = self.lang.gettext

        grid = KlippyGtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        logger.debug("FineTunePanel")


        self.labels['z+'] = KlippyGtk.ButtonImage("move-z-", _("Z+"), "color1")
        self.labels['z+'].connect("clicked", self.change_babystepping, "+")
        self.labels['zoffset'] = Gtk.Label("0.00" + _("mm"))
        self.labels['zoffset'].get_style_context().add_class('temperature_entry')
        self.labels['z-'] = KlippyGtk.ButtonImage("move-z+", _("Z-"), "color1")
        self.labels['z-'].connect("clicked", self.change_babystepping, "-")

        grid.attach(self.labels['z+'], 0, 0, 1, 1)
        grid.attach(self.labels['zoffset'], 0, 1, 1, 1)
        grid.attach(self.labels['z-'], 0, 2, 1, 1)

        self.labels['fan+'] = KlippyGtk.ButtonImage("fan-on", _("Fan +"), "color2")
        self.labels['fan+'].connect("clicked", self.change_fan, "+")
        self.labels['fanspeed'] = Gtk.Label("100%")
        self.labels['fanspeed'].get_style_context().add_class('temperature_entry')
        self.labels['fan-'] = KlippyGtk.ButtonImage("fan-off", _("Fan -"), "color2")
        self.labels['fan-'].connect("clicked", self.change_fan, "-")
        grid.attach(self.labels['fan+'], 1, 0, 1, 1)
        grid.attach(self.labels['fanspeed'], 1, 1, 1, 1)
        grid.attach(self.labels['fan-'], 1, 2, 1, 1)

        self.labels['speed+'] = KlippyGtk.ButtonImage("speed-step", _("Speed +"), "color3")
        self.labels['speed+'].connect("clicked", self.change_speed, "+")
        self.labels['speedfactor'] = Gtk.Label("100%")
        self.labels['speedfactor'].get_style_context().add_class('temperature_entry')
        self.labels['speed-'] = KlippyGtk.ButtonImage("speed-step", _("Speed -"), "color3")
        self.labels['speed-'].connect("clicked", self.change_speed, "-")
        grid.attach(self.labels['speed+'], 2, 0, 1, 1)
        grid.attach(self.labels['speedfactor'], 2, 1, 1, 1)
        grid.attach(self.labels['speed-'], 2, 2, 1, 1)

        self.labels['extrude+'] = KlippyGtk.ButtonImage("extrude", _("Extrusion +"), "color4")
        self.labels['extrude+'].connect("clicked", self.change_extrusion, "+")
        self.labels['extrudefactor'] = Gtk.Label("100%")
        self.labels['extrudefactor'].get_style_context().add_class('temperature_entry')
        self.labels['extrude-'] = KlippyGtk.ButtonImage("retract", _("Extrusion -"), "color4")
        self.labels['extrude-'].connect("clicked", self.change_extrusion, "-")
        grid.attach(self.labels['extrude+'], 3, 0, 1, 1)
        grid.attach(self.labels['extrudefactor'], 3, 1, 1, 1)
        grid.attach(self.labels['extrude-'], 3, 2, 1, 1)


        # babystepping grid
        bsgrid = Gtk.Grid()
        j = 0;
        for i in self.bs_deltas:
            self.labels[i] = KlippyGtk.ToggleButton(i)
            self.labels[i].connect("clicked", self.change_bs_delta, i)
            ctx = self.labels[i].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.bs_deltas)-1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "0.05":
                ctx.add_class("distbutton_active")
            bsgrid.attach(self.labels[i], j, 0, 1, 1)
            j += 1
        grid.attach(bsgrid, 0, 3, 1, 1)

        # Grid for percentage
        deltgrid = Gtk.Grid()
        j = 0;
        for i in self.percent_deltas:
            self.labels[i] = KlippyGtk.ToggleButton("%s%%" % i)
            self.labels[i].connect("clicked", self.change_percent_delta, i)
            ctx = self.labels[i].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.percent_deltas)-1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "1":
                ctx.add_class("distbutton_active")
            deltgrid.attach(self.labels[i], j, 0, 1, 1)
            j += 1

        self.labels["1"].set_active(True)

        grid.attach(deltgrid, 1, 3, 3, 1)

        #self.panel = grid
        self.content.add(grid)
        self._screen.add_subscription(panel_name)

    def process_update(self, action, data):
        _ = self.lang.gettext

        if action != "notify_status_update":
            return

        if "gcode_move" in data:
            if "homing_origin" in data["gcode_move"]:
                self.labels['zoffset'].set_text("%.2fmm" % data["gcode_move"]["homing_origin"][2])
            if "extrude_factor" in data["gcode_move"]:
                self.extrusion = int(data["gcode_move"]["extrude_factor"]*100)
                self.labels['extrudefactor'].set_text("%3d%%" % self.extrusion)
            if "speed_factor" in data["gcode_move"]:
                self.speed = int(data["gcode_move"]["speed_factor"]*100)
                self.labels['speedfactor'].set_text("%3d%%" % self.speed)

        if "fan" in data and "speed" in data['fan']:
            self.fan = int(round(data['fan']['speed'],2)*100)
            self.labels['fanspeed'].set_text("%3d%%" % self.fan)

    def change_babystepping(self, widget, dir):
        if dir == "+":
            gcode = "SET_GCODE_OFFSET Z_ADJUST=%s MOVE=1" % self.bs_delta
        else:
            gcode = "SET_GCODE_OFFSET Z_ADJUST=-%s MOVE=1" % self.bs_delta

        self._screen._ws.klippy.gcode_script(gcode)



    def change_bs_delta(self, widget, bs):
        if self.bs_delta == bs:
            return
        logging.info("### BabyStepping " + str(bs))

        ctx = self.labels[str(self.bs_delta)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.bs_delta = bs
        ctx = self.labels[self.bs_delta].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.bs_deltas:
            if i == self.bs_delta:
                continue
            self.labels[i].set_active(False)

    def change_extrusion(self, widget, dir):
        if dir == "+":
            self.extrusion += int(self.percent_delta)
        else:
            self.extrusion -= int(self.percent_delta)

        if self.extrusion < 0:
            self.extrusion = 0

        self._screen._ws.klippy.gcode_script(KlippyGcodes.set_extrusion_rate(self.extrusion))

    def change_fan(self, widget, dir):
        if dir == "+":
            self.fan += int(self.percent_delta)
        else:
            self.fan -= int(self.percent_delta)

        if self.fan < 0:
            self.fan = 0
        elif self.fan > 100:
            self.fan = 100

        self._screen._ws.klippy.gcode_script(KlippyGcodes.set_fan_speed(self.fan))

    def change_speed(self, widget, dir):
        if dir == "+":
            self.speed += int(self.percent_delta)
        else:
            self.speed -= int(self.percent_delta)

        if self.speed < 0:
            self.speed = 0

        self._screen._ws.klippy.gcode_script(KlippyGcodes.set_speed_rate(self.speed))

    def change_percent_delta(self, widget, delta):
        if self.percent_delta == delta:
            return
        logging.info("### Delta " + str(delta))

        ctx = self.labels[str(self.percent_delta)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.percent_delta = delta
        ctx = self.labels[self.percent_delta].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.percent_deltas:
            if i == self.percent_delta:
                continue
            self.labels[str(i)].set_active(False)
