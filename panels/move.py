import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return MovePanel(*args)


class MovePanel(ScreenPanel):
    distances = ['.1', '.5', '1', '5', '10', '25', '50']
    distance = distances[-2]

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.settings = {}
        self.menu = ['move_menu']
        self.buttons = {
            'x+': self._gtk.Button("arrow-right", "X+", "color1"),
            'x-': self._gtk.Button("arrow-left", "X-", "color1"),
            'y+': self._gtk.Button("arrow-up", "Y+", "color2"),
            'y-': self._gtk.Button("arrow-down", "Y-", "color2"),
            'z+': self._gtk.Button("z-farther", "Z+", "color3"),
            'z-': self._gtk.Button("z-closer", "Z-", "color3"),
            'home': self._gtk.Button("home", _("Home All"), "color4"),
            'home_xy': self._gtk.Button("home", _("Home XY"), "color4"),
            'z_tilt': self._gtk.Button("z-tilt", _("Z Tilt"), "color4"),
            'quad_gantry_level': self._gtk.Button("z-tilt", _("Quad Gantry Level"), "color4"),
            'motors_off': self._gtk.Button("motor-off", _("Disable Motors"), "color4"),
        }
        self.buttons['x+'].connect("clicked", self.move, "X", "+")
        self.buttons['x-'].connect("clicked", self.move, "X", "-")
        self.buttons['y+'].connect("clicked", self.move, "Y", "+")
        self.buttons['y-'].connect("clicked", self.move, "Y", "-")
        self.buttons['z+'].connect("clicked", self.move, "Z", "+")
        self.buttons['z-'].connect("clicked", self.move, "Z", "-")
        self.buttons['home'].connect("clicked", self.home)
        self.buttons['home_xy'].connect("clicked", self.homexy)
        self.buttons['z_tilt'].connect("clicked", self.z_tilt)
        self.buttons['quad_gantry_level'].connect("clicked", self.quad_gantry_level)
        script = {"script": "M18"}
        self.buttons['motors_off'].connect("clicked", self._screen._confirm_send_action,
                                           _("Are you sure you wish to disable motors?"),
                                           "printer.gcode.script", script)

        grid = self._gtk.HomogeneousGrid()
        if self._screen.vertical_mode:
            if self._screen.lang_ltr:
                grid.attach(self.buttons['x+'], 2, 1, 1, 1)
                grid.attach(self.buttons['x-'], 0, 1, 1, 1)
                grid.attach(self.buttons['z+'], 2, 2, 1, 1)
                grid.attach(self.buttons['z-'], 0, 2, 1, 1)
            else:
                grid.attach(self.buttons['x+'], 0, 1, 1, 1)
                grid.attach(self.buttons['x-'], 2, 1, 1, 1)
                grid.attach(self.buttons['z+'], 0, 2, 1, 1)
                grid.attach(self.buttons['z-'], 2, 2, 1, 1)
            grid.attach(self.buttons['y+'], 1, 0, 1, 1)
            grid.attach(self.buttons['y-'], 1, 1, 1, 1)

        else:
            if self._screen.lang_ltr:
                grid.attach(self.buttons['x+'], 2, 1, 1, 1)
                grid.attach(self.buttons['x-'], 0, 1, 1, 1)
            else:
                grid.attach(self.buttons['x+'], 0, 1, 1, 1)
                grid.attach(self.buttons['x-'], 2, 1, 1, 1)
            grid.attach(self.buttons['y+'], 1, 0, 1, 1)
            grid.attach(self.buttons['y-'], 1, 1, 1, 1)
            grid.attach(self.buttons['z+'], 3, 0, 1, 1)
            grid.attach(self.buttons['z-'], 3, 1, 1, 1)

        grid.attach(self.buttons['home'], 0, 0, 1, 1)

        if self._printer.config_section_exists("z_tilt"):
            grid.attach(self.buttons['z_tilt'], 2, 0, 1, 1)
        elif self._printer.config_section_exists("quad_gantry_level"):
            grid.attach(self.buttons['quad_gantry_level'], 2, 0, 1, 1)
        elif "delta" in self._printer.get_config_section("printer")['kinematics']:
            grid.attach(self.buttons['motors_off'], 2, 0, 1, 1)
        else:
            grid.attach(self.buttons['home_xy'], 2, 0, 1, 1)

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.labels[i] = self._gtk.Button(label=i)
            self.labels[i].set_direction(Gtk.TextDirection.LTR)
            self.labels[i].connect("clicked", self.change_distance, i)
            ctx = self.labels[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[i], j, 0, 1, 1)

        for p in ('pos_x', 'pos_y', 'pos_z'):
            self.labels[p] = Gtk.Label()
        adjust = self._gtk.Button("settings", None, "color2", 1, Gtk.PositionType.LEFT, 1)
        adjust.connect("clicked", self.load_menu, 'options', _('Settings'))
        adjust.set_hexpand(False)
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))

        bottomgrid = self._gtk.HomogeneousGrid()
        bottomgrid.set_direction(Gtk.TextDirection.LTR)
        bottomgrid.attach(self.labels['pos_x'], 0, 0, 1, 1)
        bottomgrid.attach(self.labels['pos_y'], 1, 0, 1, 1)
        bottomgrid.attach(self.labels['pos_z'], 2, 0, 1, 1)
        bottomgrid.attach(self.labels['move_dist'], 0, 1, 3, 1)
        bottomgrid.attach(adjust, 3, 0, 1, 2)

        self.labels['move_menu'] = self._gtk.HomogeneousGrid()
        self.labels['move_menu'].attach(grid, 0, 0, 1, 3)
        self.labels['move_menu'].attach(bottomgrid, 0, 3, 1, 1)
        self.labels['move_menu'].attach(distgrid, 0, 4, 1, 1)

        self.content.add(self.labels['move_menu'])

        printer_cfg = self._printer.get_config_section("printer")
        # The max_velocity parameter is not optional in klipper config.
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

    def process_busy(self, busy):
        buttons = ("home", "home_xy", "z_tilt", "quad_gantry_level")
        for button in buttons:
            if button in self.buttons:
                self.buttons[button].set_sensitive(not busy)

    def process_update(self, action, data):
        if action == "notify_busy":
            self.process_busy(data)
            return
        if action != "notify_status_update":
            return
        homed_axes = self._printer.get_stat("toolhead", "homed_axes")
        if homed_axes == "xyz":
            if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                self.labels['pos_x'].set_text(f"X: {data['gcode_move']['gcode_position'][0]:.2f}")
                self.labels['pos_y'].set_text(f"Y: {data['gcode_move']['gcode_position'][1]:.2f}")
                self.labels['pos_z'].set_text(f"Z: {data['gcode_move']['gcode_position'][2]:.2f}")
        else:
            if "x" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_x'].set_text(f"X: {data['gcode_move']['gcode_position'][0]:.2f}")
            else:
                self.labels['pos_x'].set_text("X: ?")
            if "y" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_y'].set_text(f"Y: {data['gcode_move']['gcode_position'][1]:.2f}")
            else:
                self.labels['pos_y'].set_text("Y: ?")
            if "z" in homed_axes:
                if "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.labels['pos_z'].set_text(f"Z: {data['gcode_move']['gcode_position'][2]:.2f}")
            else:
                self.labels['pos_z'].set_text("Z: ?")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def move(self, widget, axis, direction):
        if self._config.get_config()['main'].getboolean(f"invert_{axis.lower()}", False):
            direction = "-" if direction == "+" else "+"

        dist = f"{direction}{self.distance}"
        config_key = "move_speed_z" if axis == "Z" else "move_speed_xy"
        speed = None if self.ks_printer_cfg is None else self.ks_printer_cfg.getint(config_key, None)
        if speed is None:
            speed = self._config.get_config()['main'].getint(config_key, 20)
        speed = 60 * max(1, speed)

        self._screen._ws.klippy.gcode_script(f"{KlippyGcodes.MOVE_RELATIVE}\n{KlippyGcodes.MOVE} {axis}{dist} F{speed}")
        if self._printer.get_stat("gcode_move", "absolute_coordinates"):
            self._screen._ws.klippy.gcode_script("G90")

    def add_option(self, boxname, opt_array, opt_name, option):
        name = Gtk.Label()
        name.set_markup(f"<big><b>{option['name']}</b></big>")
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.get_style_context().add_class("frame-item")
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
            switch.set_property("width-request", round(self._gtk.font_size * 7))
            switch.set_property("height-request", round(self._gtk.font_size * 3.5))
            box.add(switch)
            dev.add(box)
        elif option['type'] == "scale":
            dev.set_orientation(Gtk.Orientation.VERTICAL)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL,
                                             min=option['range'][0], max=option['range'][1], step=option['step'])
            scale.set_hexpand(True)
            scale.set_value(int(self._config.get_config().get(option['section'], opt_name, fallback=option['value'])))
            scale.set_digits(0)
            scale.connect("button-release-event", self.scale_moved, option['section'], opt_name)
            dev.add(scale)

        opt_array[opt_name] = {
            "name": option['name'],
            "row": dev
        }

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

    def home(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

    def homexy(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME_XY)

    def z_tilt(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.Z_TILT)

    def quad_gantry_level(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.QUAD_GANTRY_LEVEL)
