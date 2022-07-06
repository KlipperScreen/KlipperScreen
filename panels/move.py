import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

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

        self.settings = {}
        self.menu = ['move_menu']

        grid = self._gtk.HomogeneousGrid()

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

        self.labels['motors-off'] = self._gtk.ButtonImage("motor-off", _("Disable Motors"), "color4")
        script = {"script": "M18"}
        self.labels['motors-off'].connect("clicked", self._screen._confirm_send_action,
                                          _("Are you sure you wish to disable motors?"),
                                          "printer.gcode.script", script)

        if self._screen.vertical_mode:
            if self._screen.lang_ltr:
                grid.attach(self.labels['x+'], 2, 1, 1, 1)
                grid.attach(self.labels['x-'], 0, 1, 1, 1)
                grid.attach(self.labels['z+'], 2, 2, 1, 1)
                grid.attach(self.labels['z-'], 0, 2, 1, 1)
            else:
                grid.attach(self.labels['x+'], 0, 1, 1, 1)
                grid.attach(self.labels['x-'], 2, 1, 1, 1)
                grid.attach(self.labels['z+'], 0, 2, 1, 1)
                grid.attach(self.labels['z-'], 2, 2, 1, 1)
            grid.attach(self.labels['y+'], 1, 0, 1, 1)
            grid.attach(self.labels['y-'], 1, 1, 1, 1)

        else:
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
            if "delta" in self._screen.printer.get_config_section("printer")['kinematics']:
                grid.attach(self.labels['motors-off'], 2, 0, 1, 1)
            else:
                grid.attach(self.labels['home-xy'], 2, 0, 1, 1)

        distgrid = Gtk.Grid()
        j = 0
        for i in self.distances:
            self.labels[i] = self._gtk.ToggleButton(i)
            self.labels[i].set_direction(Gtk.TextDirection.LTR)
            self.labels[i].connect("clicked", self.change_distance, i)
            ctx = self.labels[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "1":
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[i], j, 0, 1, 1)
            j += 1

        self.labels["1"].set_active(True)

        self.labels['pos_x'] = Gtk.Label("X: 0")
        self.labels['pos_y'] = Gtk.Label("Y: 0")
        self.labels['pos_z'] = Gtk.Label("Z: 0")
        adjust = self._gtk.ButtonImage("settings", None, "color2", 1, Gtk.PositionType.LEFT, False)
        adjust.connect("clicked", self.load_menu, 'options')
        adjust.set_hexpand(False)
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))

        bottomgrid = self._gtk.HomogeneousGrid()
        bottomgrid.set_direction(Gtk.TextDirection.LTR)
        bottomgrid.attach(self.labels['pos_x'], 0, 0, 1, 1)
        bottomgrid.attach(self.labels['pos_y'], 1, 0, 1, 1)
        bottomgrid.attach(self.labels['pos_z'], 2, 0, 1, 1)
        bottomgrid.attach(self.labels['move_dist'], 0, 1, 3, 1)
        bottomgrid.attach(adjust, 3, 0, 1, 2)

        self.labels['move_menu'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['move_menu'].set_vexpand(True)
        self.labels['move_menu'].pack_start(grid, True, True, 0)
        self.labels['move_menu'].pack_start(bottomgrid, True, True, 0)
        self.labels['move_menu'].pack_start(distgrid, True, True, 0)

        self.content.add(self.labels['move_menu'])

        printer_cfg = self._printer.get_config_section("printer")
        max_velocity = int(float(printer_cfg["max_velocity"]))
        if "max_z_velocity" in printer_cfg:
            max_z_velocity = int(float(printer_cfg["max_z_velocity"]))
        else:
            max_z_velocity = max_velocity

        configurable_options = [
            {"invert_x": {"section": "main", "name": _("Invert X"), "type": "binary", "value": "False"}},
            {"invert_y": {"section": "main", "name": _("Invert Y"), "type": "binary", "value": "False"}},
            {"invert_z": {"section": "main", "name": _("Invert Z"), "type": "binary", "value": "False"}},
            {"move_speed_xy": {
                "section": "main", "name": _("XY Speed (mm/s)"), "type": "scale", "value": "50",
                "range": [1, max_velocity], "step": 1}},
            {"move_speed_z": {
                "section": "main", "name": _("Z Speed (mm/s)"), "type": "scale", "value": "10",
                "range": [1, max_z_velocity], "step": 1}}
        ]

        self.labels['options_menu'] = self._gtk.ScrolledWindow()
        self.labels['options'] = Gtk.Grid()
        self.labels['options_menu'].add(self.labels['options'])
        for option in configurable_options:
            name = list(option)[0]
            self.add_option('options', self.settings, name, option[name])

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        homed_axes = self._screen.printer.get_stat("toolhead", "homed_axes")
        if homed_axes == "xyz":
            if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                self.labels['pos_x'].set_text("X: %.2f" % (data["gcode_move"]["gcode_position"][0]))
                self.labels['pos_y'].set_text("Y: %.2f" % (data["gcode_move"]["gcode_position"][1]))
                self.labels['pos_z'].set_text("Z: %.2f" % (data["gcode_move"]["gcode_position"][2]))
        else:
            if "x" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_x'].set_text("X: %.2f" % (data["gcode_move"]["gcode_position"][0]))
            else:
                self.labels['pos_x'].set_text("X: ?")
            if "y" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_y'].set_text("Y: %.2f" % (data["gcode_move"]["gcode_position"][1]))
            else:
                self.labels['pos_y'].set_text("Y: ?")
            if "z" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_z'].set_text("Z: %.2f" % (data["gcode_move"]["gcode_position"][2]))
            else:
                self.labels['pos_z'].set_text("Z: ?")

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
                KlippyGcodes.MOVE_RELATIVE, KlippyGcodes.MOVE, axis, dist, speed * 60,
                "\nG90" if self._printer.get_stat("gcode_move", "absolute_coordinates") is True else ""
            )
        )

    def add_option(self, boxname, opt_array, opt_name, option):
        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (option['name']))
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.set_valign(Gtk.Align.CENTER)
        dev.add(name)

        if option['type'] == "binary":
            box = Gtk.Box()
            box.set_vexpand(False)
            switch = Gtk.Switch()
            switch.set_hexpand(False)
            switch.set_vexpand(False)
            switch.set_active(self._config.get_config().getboolean(option['section'], opt_name))
            switch.connect("notify::active", self.switch_config_option, option['section'], opt_name)
            switch.set_property("width-request", round(self._gtk.get_font_size() * 7))
            switch.set_property("height-request", round(self._gtk.get_font_size() * 3.5))
            box.add(switch)
            dev.add(box)
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            val = int(self._config.get_config().get(option['section'], opt_name, fallback=option['value']))
            adj = Gtk.Adjustment(val, option['range'][0], option['range'][1], option['step'], option['step'] * 5)
            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
            scale.set_hexpand(True)
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            dev.add(scale)

        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")
        frame.add(dev)
        frame.show_all()

        opt_array[opt_name] = {
            "name": option['name'],
            "row": frame
        }

        opts = sorted(opt_array)
        opts = sorted(list(opt_array), key=lambda x: opt_array[x]['name'])
        pos = opts.index(opt_name)

        self.labels[boxname].insert_row(pos)
        self.labels[boxname].attach(opt_array[opt_name]['row'], 0, pos, 1, 1)
        self.labels[boxname].show_all()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            return True
        return False
