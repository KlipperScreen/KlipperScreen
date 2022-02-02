import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

AXIS_X = "X"
AXIS_Y = "Y"
AXIS_Z = "Z"

def create_panel(*args):
    return MovePanel(*args)

class MovePanel(ScreenPanel):
    distance = 1
    distances = ['.1', '.5', '1', '5', '10', '25', '50']


    def initialize(self, panel_name):
        _ = self.lang.gettext

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)

        self.labels['x+'] = self._gtk.ButtonImage("arrow-right", _("X+"), "color1")
        self.labels['x+'].connect("clicked", self.move, AXIS_X, "+")
        self.labels['x-'] = self._gtk.ButtonImage("arrow-left", _("X-"), "color1")
        self.labels['x-'].connect("clicked", self.move, AXIS_X, "-")

        self.labels['y+'] = self._gtk.ButtonImage("arrow-up", _("Y+"), "color2")
        self.labels['y+'].connect("clicked", self.move, AXIS_Y, "+")
        self.labels['y-'] = self._gtk.ButtonImage("arrow-down", _("Y-"), "color2")
        self.labels['y-'].connect("clicked", self.move, AXIS_Y, "-")

        self.labels['z+'] = self._gtk.ButtonImage("z-farther", _("Z+"), "color3")
        self.labels['z+'].connect("clicked", self.move, AXIS_Z, "+")
        self.labels['z-'] = self._gtk.ButtonImage("z-closer", _("Z-"), "color3")
        self.labels['z-'].connect("clicked", self.move, AXIS_Z, "-")

        self.labels['home'] = self._gtk.ButtonImage("home", _("Home All"), "color4")
        self.labels['home'].connect("clicked", self.home)

        self.labels['home-xy'] = self._gtk.ButtonImage("home", _("Home XY"), "color4")
        self.labels['home-xy'].connect("clicked", self.homexy)

        self.labels['z_tilt'] = self._gtk.ButtonImage("z-tilt", _("Z Tilt"), "color4")
        self.labels['z_tilt'].connect("clicked", self.z_tilt)

        self.labels['quad_gantry_level'] = self._gtk.ButtonImage("z-tilt", _("Quad Gantry Level"), "color4")
        self.labels['quad_gantry_level'].connect("clicked", self.quad_gantry_level)

        if self._screen.lang_ltr:
            grid.attach(self.labels['x+'], 2, 1, 1, 1)
            grid.attach(self.labels['x-'], 0, 1, 1, 1)
        else:
            grid.attach(self.labels['x+'], 0, 1, 1, 1)
            grid.attach(self.labels['x-'], 2, 1, 1, 1)
        grid.attach(self.labels['y+'], 1, 0, 1, 1)
        grid.attach(self.labels['y-'], 1, 1, 1, 1)
        grid.attach(self.labels['z+'], 3, 0, 1, 1)
        grid.attach(self.labels['z-'], 3, 1, 1, 1)

        grid.attach(self.labels['home'], 0, 0, 1, 1)

        if self._printer.config_section_exists("z_tilt"):
            grid.attach(self.labels['z_tilt'], 2, 0, 1, 1)
        elif self._printer.config_section_exists("quad_gantry_level"):
            grid.attach(self.labels['quad_gantry_level'], 2, 0, 1, 1)
        else:
            grid.attach(self.labels['home-xy'], 2, 0, 1, 1)

        distgrid = Gtk.Grid()
        j = 0
        for i in self.distances:
            self.labels[i] = self._gtk.ToggleButton(i)
            self.labels[i].set_direction(Gtk.TextDirection.LTR)
            self.labels[i].connect("clicked", self.change_distance, i)
            ctx = self.labels[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances)-1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances)-1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "1":
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[i], j, 0, 1, 1)
            j += 1

        self.labels["1"].set_active(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        bottomgrid = self._gtk.HomogeneousGrid()
        bottomgrid.set_direction(Gtk.TextDirection.LTR)
        self.labels['pos_x'] = Gtk.Label("X: 0")
        self.labels['pos_y'] = Gtk.Label("Y: 0")
        self.labels['pos_z'] = Gtk.Label("Z: 0")
        bottomgrid.attach(self.labels['pos_x'], 0, 0, 1, 1)
        bottomgrid.attach(self.labels['pos_y'], 1, 0, 1, 1)
        bottomgrid.attach(self.labels['pos_z'], 2, 0, 1, 1)
        box.pack_start(bottomgrid, True, True, 0)
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        box.pack_start(self.labels['move_dist'], True, True, 0)
        box.pack_start(distgrid, True, True, 0)

        grid.attach(box, 0, 2, 4, 1)

        self.content.add(grid)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        if "toolhead" in data and "position" in data["toolhead"]:
            self.labels['pos_x'].set_text("X: %.2f" % (data["toolhead"]["position"][0]))
            self.labels['pos_y'].set_text("Y: %.2f" % (data["toolhead"]["position"][1]))
            self.labels['pos_z'].set_text("Z: %.2f" % (data["toolhead"]["position"][2]))

    def change_distance(self, widget, distance):
        if self.distance == distance:
            return
        logging.info("### Distance " + str(distance))

        ctx = self.labels[str(self.distance)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.distance = distance
        ctx = self.labels[self.distance].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.distances:
            if i == self.distance:
                continue
            self.labels[str(i)].set_active(False)

    def move(self, widget, axis, dir):
        if self._config.get_config()['main'].getboolean("invert_%s" % axis.lower(), False):
            dir = "-" if dir == "+" else "+"

        dist = str(self.distance) if dir == "+" else "-" + str(self.distance)
        config_key = "move_speed_z" if axis == AXIS_Z else "move_speed_xy"

        speed = None
        printer_cfg = self._config.get_printer_config(self._screen.connected_printer)

        if printer_cfg is not None:
            speed = printer_cfg.getint(config_key, None)

        if speed is None:
            speed = self._config.get_config()['main'].getint(config_key, 20)

        speed = max(1, speed)

        self._screen._ws.klippy.gcode_script(
            "%s\n%s %s%s F%s%s" % (
                KlippyGcodes.MOVE_RELATIVE, KlippyGcodes.MOVE, axis, dist, speed*60,
                "\nG90" if self._printer.get_stat("gcode_move", "absolute_coordinates") is True else ""
            )
        )
