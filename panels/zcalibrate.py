import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    widgets = {}
    distances = ['.01', '.05', '.1', '.5', '1', '5']
    distance = distances[-2]

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.mesh_min = []
        self.mesh_max = []
        self.mesh_radius = None
        self.mesh_origin = [0, 0]
        self.zero_ref = []
        self.z_hop_speed = 15.0
        self.z_hop = 5.0
        self.probe = self._printer.get_probe()
        if self.probe:
            self.x_offset = float(self.probe['x_offset']) if "x_offset" in self.probe else 0.0
            self.y_offset = float(self.probe['y_offset']) if "y_offset" in self.probe else 0.0
            self.z_offset = float(self.probe['z_offset'])
            if "sample_retract_dist" in self.probe:
                self.z_hop = float(self.probe['sample_retract_dist'])
            if "speed" in self.probe:
                self.z_hop_speed = float(self.probe['speed'])
        else:
            self.x_offset = 0.0
            self.y_offset = 0.0
            self.z_offset = 0.0
        logging.info(f"Offset X:{self.x_offset} Y:{self.y_offset} Z:{self.z_offset}")
        self.widgets['zposition'] = Gtk.Label(label="Z: ?")

        self.widgets['zoffset'] = Gtk.Label(label="?")
        pos = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        pos.attach(self.widgets['zposition'], 0, 1, 2, 1)
        if self.probe:
            pos.attach(Gtk.Label(label=_("Probe Offset") + ": "), 0, 2, 2, 1)
            pos.attach(Gtk.Label(label=_("Saved")), 0, 3, 1, 1)
            pos.attach(Gtk.Label(label=_("New")), 1, 3, 1, 1)
            pos.attach(Gtk.Label(label=f"{self.z_offset:.3f}"), 0, 4, 1, 1)
            pos.attach(self.widgets['zoffset'], 1, 4, 1, 1)
        for label in pos.get_children():
            if isinstance(label, Gtk.Label):
                label.set_ellipsize(Pango.EllipsizeMode.END)
        self.buttons = {
            'zpos': self._gtk.Button('z-farther', _("Raise Nozzle"), 'color4'),
            'zneg': self._gtk.Button('z-closer', _("Lower Nozzle"), 'color1'),
            'start': self._gtk.Button('resume', _("Start"), 'color3'),
            'complete': self._gtk.Button('complete', _('Accept'), 'color3'),
            'cancel': self._gtk.Button('cancel', _('Abort'), 'color2'),
        }
        self.buttons['zpos'].connect("clicked", self.move, "+")
        self.buttons['zneg'].connect("clicked", self.move, "-")
        self.buttons['complete'].connect("clicked", self.accept)
        script = {"script": "ABORT"}
        self.buttons['cancel'].connect("clicked", self._screen._confirm_send_action,
                                       _("Are you sure you want to stop the calibration?"),
                                       "printer.gcode.script", script)

        self.popover = Gtk.Popover(position=Gtk.PositionType.BOTTOM)

        self.set_functions()

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.widgets[i] = self._gtk.Button(label=i)
            self.widgets[i].set_direction(Gtk.TextDirection.LTR)
            self.widgets[i].connect("clicked", self.change_distance, i)
            ctx = self.widgets[i].get_style_context()
            ctx.add_class("horizontal_togglebuttons")
            if i == self.distance:
                ctx.add_class("horizontal_togglebuttons_active")
            distgrid.attach(self.widgets[i], j, 0, 1, 1)

        self.widgets['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        distances = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        distances.pack_start(self.widgets['move_dist'], True, True, 0)
        distances.pack_start(distgrid, True, True, 0)

        grid = Gtk.Grid(column_homogeneous=True)
        if self._screen.vertical_mode:
            if self._config.get_config()["main"].getboolean("invert_z", False):
                grid.attach(self.buttons['zpos'], 0, 2, 1, 1)
                grid.attach(self.buttons['zneg'], 0, 1, 1, 1)
            else:
                grid.attach(self.buttons['zpos'], 0, 1, 1, 1)
                grid.attach(self.buttons['zneg'], 0, 2, 1, 1)
            grid.attach(self.buttons['start'], 0, 0, 1, 1)
            grid.attach(pos, 1, 0, 1, 1)
            grid.attach(self.buttons['complete'], 1, 1, 1, 1)
            grid.attach(self.buttons['cancel'], 1, 2, 1, 1)
            grid.attach(distances, 0, 3, 2, 1)
        else:
            if self._config.get_config()["main"].getboolean("invert_z", False):
                grid.attach(self.buttons['zpos'], 0, 1, 1, 1)
                grid.attach(self.buttons['zneg'], 0, 0, 1, 1)
            else:
                grid.attach(self.buttons['zpos'], 0, 0, 1, 1)
                grid.attach(self.buttons['zneg'], 0, 1, 1, 1)
            grid.attach(self.buttons['start'], 1, 0, 1, 1)
            grid.attach(pos, 1, 1, 1, 1)
            grid.attach(self.buttons['complete'], 2, 0, 1, 1)
            grid.attach(self.buttons['cancel'], 2, 1, 1, 1)
            grid.attach(distances, 0, 2, 3, 1)
        self.content.add(grid)

    def set_functions(self):
        functions = []
        pobox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        if "Z_ENDSTOP_CALIBRATE" in self._printer.available_commands:
            self._add_button("Endstop", "endstop", pobox)
            functions.append("endstop")
        if "PROBE_CALIBRATE" in self._printer.available_commands:
            self._add_button("Probe", "probe", pobox)
            functions.append("probe")
        if "BED_MESH_CALIBRATE" in self._printer.available_commands:
            mesh = self._printer.get_config_section("bed_mesh")
            logging.info(f"Mesh: {mesh}")
            if 'mesh_radius' in mesh:
                self.mesh_radius = float(mesh['mesh_radius'])
                if 'mesh_origin' in mesh:
                    self.mesh_origin = self._csv_to_array(mesh['mesh_origin'])
                logging.info(f"Mesh Radius: {self.mesh_radius} Origin: {self.mesh_origin}")
            elif 'mesh_min' in mesh and 'mesh_max' in mesh:
                self.mesh_min = self._csv_to_array(mesh['mesh_min'])
                self.mesh_max = self._csv_to_array(mesh['mesh_max'])
            elif 'min_x' in mesh and 'min_y' in mesh and 'max_x' in mesh and 'max_y' in mesh:
                self.mesh_min = [float(mesh['min_x']), float(mesh['min_y'])]
                self.mesh_max = [float(mesh['max_x']), float(mesh['max_y'])]
            if 'zero_reference_position' in self._printer.get_config_section("bed_mesh"):
                self.zero_ref = self._csv_to_array(mesh['zero_reference_position'])
            if "probe" not in functions:
                # This is used to do a manual bed mesh if there is no probe
                self._add_button("Bed mesh", "mesh", pobox)
                functions.append("mesh")
        if "DELTA_CALIBRATE" in self._printer.available_commands:
            if "probe" in functions:
                self._add_button("Delta Automatic", "delta", pobox)
                functions.append("delta")
            # Since probes may not be accturate enough for deltas, always show the manual method
            self._add_button("Delta Manual", "delta_manual", pobox)
            functions.append("delta_manual")
        if "AXIS_TWIST_COMPENSATION_CALIBRATE" in self._printer.available_commands:
            self._add_button("Axis Twist Compensation", "axis_twist", pobox)
            functions.append("axis_twist")

        self.popover.add(pobox)
        if len(functions) > 1:
            self.buttons['start'].connect("clicked", self.on_popover_clicked)
        else:
            self.buttons['start'].connect("clicked", self.start_calibration, functions[0])
        logging.info(f"Available functions for calibration: {functions}")

    @staticmethod
    def _csv_to_array(string):
        return [float(i.strip()) for i in string.split(',')]

    def _add_button(self, label, method, pobox):
        popover_button = self._gtk.Button(label=label)
        popover_button.connect("clicked", self.start_calibration, method)
        pobox.pack_start(popover_button, True, True, 5)

    def on_popover_clicked(self, widget):
        self.popover.set_relative_to(widget)
        self.popover.show_all()

    def start_calibration(self, widget, method):
        self.popover.popdown()
        self.buttons['start'].set_sensitive(False)
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script("G28")
        self._screen._ws.klippy.gcode_script("SET_GCODE_OFFSET Z=0")
        if method == "mesh":
            self._screen._ws.klippy.gcode_script("BED_MESH_CALIBRATE")
        else:
            self._screen._ws.klippy.gcode_script("BED_MESH_CLEAR")
            if method == "probe":
                self._move_to_position(*self._get_probe_location())
                self._screen._ws.klippy.gcode_script("PROBE_CALIBRATE")
            elif method == "delta":
                self._screen._ws.klippy.gcode_script("DELTA_CALIBRATE")
            elif method == "delta_manual":
                self._screen._ws.klippy.gcode_script("DELTA_CALIBRATE METHOD=manual")
            elif method == "endstop":
                self._screen._ws.klippy.gcode_script("Z_ENDSTOP_CALIBRATE")
            elif method == "axis_twist":
                self._screen._ws.klippy.gcode_script("AXIS_TWIST_COMPENSATION_CALIBRATE")

    def _move_to_position(self, x, y):
        if not x or not y:
            self._screen.show_popup_message(_("Error: Couldn't get a position to probe"))
            return
        logging.info(f"Lifting Z: {self.z_hop}mm {self.z_hop_speed}mm/s")
        self._screen._ws.klippy.gcode_script(f"G91\nG0 Z{self.z_hop} F{self.z_hop_speed * 60}")
        logging.info(f"Moving to X:{x} Y:{y}")
        self._screen._ws.klippy.gcode_script(f'G90\nG0 X{x} Y{y} F3000')

    def _get_probe_location(self):
        if self.ks_printer_cfg is not None:
            x = self.ks_printer_cfg.getfloat("calibrate_x_position", None)
            y = self.ks_printer_cfg.getfloat("calibrate_y_position", None)
            if x and y:
                logging.debug(f"Using KS configured position: {x}, {y}")
                return x, y

        if self.zero_ref:
            logging.debug(f"Using zero reference position: {self.zero_ref}")
            return self.zero_ref[0] - self.x_offset, self.zero_ref[1] - self.y_offset

        if ("safe_z_home" in self._printer.get_config_section_list() and
                "Z_ENDSTOP_CALIBRATE" not in self._printer.available_commands):
            return self._get_safe_z()
        if self.mesh_radius or "delta" in self._printer.get_config_section("printer")['kinematics']:
            logging.info(f"Round bed calibrating at {self.mesh_origin}")
            return self.mesh_origin[0] - self.x_offset, self.mesh_origin[1] - self.y_offset

        x, y = self._calculate_position()
        return x, y

    def _get_safe_z(self):
        safe_z = self._printer.get_config_section("safe_z_home")
        safe_z_xy = self._csv_to_array(safe_z['home_xy_position'])
        logging.debug(f"Using safe_z {safe_z_xy[0]}, {safe_z_xy[1]}")
        if 'z_hop' in safe_z:
            self.z_hop = float(safe_z['z_hop'])
        if 'z_hop_speed' in safe_z:
            self.z_hop_speed = float(safe_z['z_hop_speed'])
        return safe_z_xy[0], safe_z_xy[1]

    def _calculate_position(self):
        if self.mesh_max and self.mesh_min:
            mesh_mid_x = (self.mesh_min[0] + self.mesh_max[0]) / 2
            mesh_mid_y = (self.mesh_min[1] + self.mesh_max[1]) / 2
            logging.debug(f"Probe in the mesh center X:{mesh_mid_x} Y:{mesh_mid_y}")
            return mesh_mid_x - self.x_offset, mesh_mid_y - self.y_offset
        try:
            mid_x = float(self._printer.get_config_section("stepper_x")['position_max']) / 2
            mid_y = float(self._printer.get_config_section("stepper_y")['position_max']) / 2
        except KeyError:
            logging.error("Couldn't get max position from stepper_x and stepper_y")
            return None, None
        logging.debug(f"Probe in the center X:{mid_x} Y:{mid_y}")
        return mid_x - self.x_offset, mid_y - self.y_offset

    def activate(self):
        if self._printer.get_stat("manual_probe", "is_active"):
            self.buttons_calibrating()
        else:
            self.buttons_not_calibrating()

    def process_update(self, action, data):
        if action == "notify_status_update":
            if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
                self.widgets['zposition'].set_text("Z: ?")
            elif "gcode_move" in data and "gcode_position" in data['gcode_move']:
                self.update_position(data['gcode_move']['gcode_position'])
            if "manual_probe" in data:
                if data["manual_probe"]["is_active"]:
                    self.buttons_calibrating()
                else:
                    self.buttons_not_calibrating()
        elif action == "notify_gcode_response":
            if "out of range" in data.lower():
                self._screen.show_popup_message(data)
                logging.info(data)
            elif "fail" in data.lower() and "use testz" in data.lower():
                self._screen.show_popup_message(_("Failed, adjust position first"))
                logging.info(data)
        return

    def update_position(self, position):
        self.widgets['zposition'].set_text(f"Z: {position[2]:.3f}")
        self.widgets['zoffset'].set_text(f"{abs(position[2] - self.z_offset):.3f}")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.widgets[f"{self.distance}"].get_style_context().remove_class("horizontal_togglebuttons_active")
        self.widgets[f"{distance}"].get_style_context().add_class("horizontal_togglebuttons_active")
        self.distance = distance

    def move(self, widget, direction):
        self._screen._ws.klippy.gcode_script(f"TESTZ Z={direction}{self.distance}")

    def accept(self, widget):
        logging.info("Accepting Z position")
        self._screen._ws.klippy.gcode_script("ACCEPT")

    def buttons_calibrating(self):
        self.buttons['start'].get_style_context().remove_class('color3')
        self.buttons['start'].set_sensitive(False)

        self.buttons['zpos'].set_sensitive(True)
        self.buttons['zpos'].get_style_context().add_class('color4')
        self.buttons['zneg'].set_sensitive(True)
        self.buttons['zneg'].get_style_context().add_class('color1')
        self.buttons['complete'].set_sensitive(True)
        self.buttons['complete'].get_style_context().add_class('color3')
        self.buttons['cancel'].set_sensitive(True)
        self.buttons['cancel'].get_style_context().add_class('color2')

    def buttons_not_calibrating(self):
        self.buttons['start'].get_style_context().add_class('color3')
        self.buttons['start'].set_sensitive(True)

        self.buttons['zpos'].set_sensitive(False)
        self.buttons['zpos'].get_style_context().remove_class('color4')
        self.buttons['zneg'].set_sensitive(False)
        self.buttons['zneg'].get_style_context().remove_class('color1')
        self.buttons['complete'].set_sensitive(False)
        self.buttons['complete'].get_style_context().remove_class('color3')
        self.buttons['cancel'].set_sensitive(False)
        self.buttons['cancel'].get_style_context().remove_class('color2')
