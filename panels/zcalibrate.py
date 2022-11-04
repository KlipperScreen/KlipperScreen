import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

import logging


def create_panel(*args):
    return ZCalibratePanel(*args)


class ZCalibratePanel(ScreenPanel):
    _screen = None
    widgets = {}
    distances = ['.01', '.05', '.1', '.5', '1', '5']
    distance = distances[-2]

    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, False)
        self.z_offset = None

    def initialize(self, panel_name):

        if self._printer.config_section_exists("probe"):
            self.z_offset = float(self._screen.printer.get_config_section("probe")['z_offset'])
        elif self._printer.config_section_exists("bltouch"):
            self.z_offset = float(self._screen.printer.get_config_section("bltouch")['z_offset'])
        elif self._printer.config_section_exists("smart_effector"):
            self.z_offset = float(self._screen.printer.get_config_section("smart_effector")['z_offset'])
        else:
            self.z_offset = None

        self.widgets['zposition'] = Gtk.Label("Z: ?")

        pos = self._gtk.HomogeneousGrid()
        pos.attach(self.widgets['zposition'], 0, 1, 2, 1)
        if self.z_offset is not None:
            self.widgets['zoffset'] = Gtk.Label("?")
            pos.attach(Gtk.Label(_("Probe Offset") + ": "), 0, 2, 2, 1)
            pos.attach(Gtk.Label(_("Saved")), 0, 3, 1, 1)
            pos.attach(Gtk.Label(_("New")), 1, 3, 1, 1)
            pos.attach(Gtk.Label(f"{self.z_offset:.2f}"), 0, 4, 1, 1)
            pos.attach(self.widgets['zoffset'], 1, 4, 1, 1)

        self.widgets['zpos'] = self._gtk.ButtonImage('z-farther', _("Raise Nozzle"), 'color4')
        self.widgets['zpos'].connect("clicked", self.move, "+")
        self.widgets['zneg'] = self._gtk.ButtonImage('z-closer', _("Lower Nozzle"), 'color1')
        self.widgets['zneg'].connect("clicked", self.move, "-")
        self.widgets['start'] = self._gtk.ButtonImage('resume', _("Start"), 'color3')
        self.widgets['complete'] = self._gtk.ButtonImage('complete', _('Accept'), 'color3')
        self.widgets['complete'].connect("clicked", self.accept)
        self.widgets['cancel'] = self._gtk.ButtonImage('cancel', _('Abort'), 'color2')
        self.widgets['cancel'].connect("clicked", self.abort)

        functions = []
        pobox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        if self._printer.config_section_exists("stepper_z") \
                and not self._screen.printer.get_config_section("stepper_z")['endstop_pin'].startswith("probe"):
            self._add_button("Endstop", "endstop", pobox)
            functions.append("endstop")
        if self._printer.config_section_exists("probe") or self._printer.config_section_exists("bltouch"):
            self._add_button("Probe", "probe", pobox)
            functions.append("probe")
        if self._printer.config_section_exists("bed_mesh") and "probe" not in functions:
            # This is used to do a manual bed mesh if there is no probe
            self._add_button("Bed mesh", "mesh", pobox)
            functions.append("mesh")
        if "delta" in self._screen.printer.get_config_section("printer")['kinematics']:
            if "probe" in functions:
                self._add_button("Delta Automatic", "delta", pobox)
                functions.append("delta")
            # Since probes may not be accturate enough for deltas, always show the manual method
            self._add_button("Delta Manual", "delta_manual", pobox)
            functions.append("delta_manual")

        logging.info(f"Available functions for calibration: {functions}")

        self.labels['popover'] = Gtk.Popover()
        self.labels['popover'].add(pobox)
        self.labels['popover'].set_position(Gtk.PositionType.BOTTOM)

        if len(functions) > 1:
            self.widgets['start'].connect("clicked", self.on_popover_clicked)
        else:
            self.widgets['start'].connect("clicked", self.start_calibration, functions[0])

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.widgets[i] = self._gtk.Button(i)
            self.widgets[i].set_direction(Gtk.TextDirection.LTR)
            self.widgets[i].connect("clicked", self.change_distance, i)
            ctx = self.widgets[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances) - 1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.widgets[i], j, 0, 1, 1)

        self.widgets['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        distances = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        distances.pack_start(self.widgets['move_dist'], True, True, 0)
        distances.pack_start(distgrid, True, True, 0)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        if self._screen.vertical_mode:
            grid.attach(self.widgets['zpos'], 0, 1, 1, 1)
            grid.attach(self.widgets['zneg'], 0, 2, 1, 1)
            grid.attach(self.widgets['start'], 0, 0, 1, 1)
            grid.attach(pos, 1, 0, 1, 1)
            grid.attach(self.widgets['complete'], 1, 1, 1, 1)
            grid.attach(self.widgets['cancel'], 1, 2, 1, 1)
            grid.attach(distances, 0, 3, 2, 1)
        else:
            grid.attach(self.widgets['zpos'], 0, 0, 1, 1)
            grid.attach(self.widgets['zneg'], 0, 1, 1, 1)
            grid.attach(self.widgets['start'], 1, 0, 1, 1)
            grid.attach(pos, 1, 1, 1, 1)
            grid.attach(self.widgets['complete'], 2, 0, 1, 1)
            grid.attach(self.widgets['cancel'], 2, 1, 1, 1)
            grid.attach(distances, 0, 2, 3, 1)
        self.buttons_not_calibrating()
        self.content.add(grid)

    def _add_button(self, label, method, pobox):
        popover_button = self._gtk.Button(label=label)
        popover_button.connect("clicked", self.start_calibration, method)
        pobox.pack_start(popover_button, True, True, 5)

    def on_popover_clicked(self, widget):
        self.labels['popover'].set_relative_to(widget)
        self.labels['popover'].show_all()

    def start_calibration(self, widget, method):
        self.labels['popover'].popdown()
        if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

        if method == "probe":
            self._move_to_position()
            self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_CALIBRATE)
        elif method == "mesh":
            self._screen._ws.klippy.gcode_script("BED_MESH_CALIBRATE")
        elif method == "delta":
            self._screen._ws.klippy.gcode_script("DELTA_CALIBRATE")
        elif method == "delta_manual":
            self._screen._ws.klippy.gcode_script("DELTA_CALIBRATE METHOD=manual")
        elif method == "endstop":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.Z_ENDSTOP_CALIBRATE)

    def _move_to_position(self):
        x_position = y_position = None
        # Get position from config
        printer_cfg = self._config.get_printer_config(self._screen.connected_printer)
        logging.info(printer_cfg)
        if printer_cfg is not None:
            x_position = printer_cfg.getfloat("calibrate_x_position", None)
            y_position = printer_cfg.getfloat("calibrate_y_position", None)
        elif 'z_calibrate_position' in self._config.get_config():
            # OLD global way, this should be deprecated
            x_position = self._config.get_config()['z_calibrate_position'].getfloat("calibrate_x_position", None)
            y_position = self._config.get_config()['z_calibrate_position'].getfloat("calibrate_y_position", None)

        # Use safe_z_home position
        if "safe_z_home" in self._screen.printer.get_config_section_list():
            safe_z = self._screen.printer.get_config_section("safe_z_home")['home_xy_position']
            safe_z = [str(i.strip()) for i in safe_z.split(',')]
            if x_position is None:
                x_position = float(safe_z[0])
                logging.debug(f"Using safe_z x:{x_position}")
            if y_position is None:
                y_position = float(safe_z[1])
                logging.debug(f"Using safe_z y:{y_position}")

        if x_position is not None and y_position is not None:
            logging.debug(f"Configured probing position X: {x_position} Y: {y_position}")
            self._screen._ws.klippy.gcode_script(f'G0 X{x_position} Y{y_position} F3000')
        elif "delta" in self._screen.printer.get_config_section("printer")['kinematics']:
            logging.info("Detected delta kinematics calibrating at 0,0")
            self._screen._ws.klippy.gcode_script('G0 X0 Y0 F3000')
        else:
            self._calculate_position()

    def _calculate_position(self):
        logging.debug("Position not configured, probing the middle of the bed")
        try:
            xmax = float(self._screen.printer.get_config_section("stepper_x")['position_max'])
            ymax = float(self._screen.printer.get_config_section("stepper_y")['position_max'])
        except KeyError:
            logging.error("Couldn't get max position from stepper_x and stepper_y")
            return
        x_position = xmax / 2
        y_position = ymax / 2
        logging.info(f"Center position X:{x_position} Y:{y_position}")

        # Find probe offset
        klipper_cfg = self._screen.printer.get_config_section_list()
        x_offset = y_offset = None
        if "bltouch" in klipper_cfg:
            bltouch = self._screen.printer.get_config_section("bltouch")
            if "x_offset" in bltouch:
                x_offset = float(bltouch['x_offset'])
            if "y_offset" in bltouch:
                y_offset = float(bltouch['y_offset'])
        elif "probe" in klipper_cfg:
            probe = self._screen.printer.get_config_section("probe")
            if "x_offset" in probe:
                x_offset = float(probe['x_offset'])
            if "y_offset" in probe:
                y_offset = float(probe['y_offset'])
        logging.info(f"Offset X:{x_offset} Y:{y_offset}")
        if x_offset is not None:
            x_position = x_position - x_offset
        if y_offset is not None:
            y_position = y_position - y_offset

        logging.info(f"Moving to X:{x_position} Y:{y_position}")
        self._screen._ws.klippy.gcode_script(f'G0 X{x_position} Y{y_position} F3000')

    def process_update(self, action, data):

        if action == "notify_status_update":
            if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
                self.widgets['zposition'].set_text("Z: ?")
            elif "toolhead" in data and "position" in data['toolhead']:
                self.update_position(data['toolhead']['position'])
        elif action == "notify_gcode_response":
            data = data.lower()
            if "unknown" in data:
                self.buttons_not_calibrating()
                logging.info(data)
            elif "save_config" in data:
                self.buttons_not_calibrating()
                self._screen.show_popup_message(_("Calibrated, save configuration to make it permanent"), level=1)
            elif "out of range" in data:
                self._screen.show_popup_message(data)
                self.buttons_not_calibrating()
                logging.info(data)
            elif "fail" in data and "use testz" in data:
                self._screen.show_popup_message(_("Failed, adjust position first"))
                self.buttons_not_calibrating()
                logging.info(data)
            elif "use testz" in data or "use abort" in data or "z position" in data:
                self.buttons_calibrating()
        return

    def update_position(self, position):
        self.widgets['zposition'].set_text(f"Z: {position[2]:.2f}")
        if self.z_offset is not None:
            self.widgets['zoffset'].set_text(f"{-position[2] + self.z_offset:.2f}")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.widgets[f"{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.widgets[f"{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def move(self, widget, direction):
        dist = f"{direction}{self.distance}"
        logging.info(f"# Moving {KlippyGcodes.testz_move(dist)}")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.testz_move(dist))

    def abort(self, widget):
        logging.info("Aborting calibration")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.ABORT)
        self.buttons_not_calibrating()
        self.menu_return(widget)

    def accept(self, widget):
        logging.info("Accepting Z position")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.ACCEPT)

    def buttons_calibrating(self):
        self.widgets['start'].get_style_context().remove_class('color3')
        self.widgets['start'].set_sensitive(False)

        self.widgets['zpos'].set_sensitive(True)
        self.widgets['zpos'].get_style_context().add_class('color4')
        self.widgets['zneg'].set_sensitive(True)
        self.widgets['zneg'].get_style_context().add_class('color1')
        self.widgets['complete'].set_sensitive(True)
        self.widgets['complete'].get_style_context().add_class('color3')
        self.widgets['cancel'].set_sensitive(True)
        self.widgets['cancel'].get_style_context().add_class('color2')

    def buttons_not_calibrating(self):
        self.widgets['start'].get_style_context().add_class('color3')
        self.widgets['start'].set_sensitive(True)

        self.widgets['zpos'].set_sensitive(False)
        self.widgets['zpos'].get_style_context().remove_class('color4')
        self.widgets['zneg'].set_sensitive(False)
        self.widgets['zneg'].get_style_context().remove_class('color1')
        self.widgets['complete'].set_sensitive(False)
        self.widgets['complete'].get_style_context().remove_class('color3')
        self.widgets['cancel'].set_sensitive(False)
        self.widgets['cancel'].get_style_context().remove_class('color2')
