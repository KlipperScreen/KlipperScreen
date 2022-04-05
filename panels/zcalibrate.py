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
    distance = 1
    distances = ['.01', '.05', '.1', '.5', '1', '5']

    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, False)

    def initialize(self, panel_name):
        _ = self.lang.gettext
        grid = Gtk.Grid()

        pos_label = Gtk.Label(_("Z Position") + ": \n")
        self.widgets['zposition'] = Gtk.Label("?")
        pos = Gtk.VBox()
        pos.set_vexpand(False)
        pos.set_valign(Gtk.Align.CENTER)
        pos.add(pos_label)
        pos.add(self.widgets['zposition'])

        self.widgets['zpos'] = self._gtk.ButtonImage('z-farther', _("Raise Nozzle"), 'color4')
        self.widgets['zpos'].connect("clicked", self.move, "+")
        self.widgets['zneg'] = self._gtk.ButtonImage('z-closer', _("Lower Nozzle"), 'color1')
        self.widgets['zneg'].connect("clicked", self.move, "-")
        self.widgets['start'] = self._gtk.ButtonImage('resume', _("Start"), 'color3')
        self.widgets['complete'] = self._gtk.ButtonImage('complete', _('Accept'), 'color3')
        self.widgets['complete'].connect("clicked", self.accept)
        self.widgets['cancel'] = self._gtk.ButtonImage('cancel', _('Abort'), 'color2')
        self.widgets['cancel'].connect("clicked", self.abort)

        functions = ["endstop", "probe", "mesh", "delta", "delta_manual"]
        pobox = Gtk.VBox()
        if not self._screen.printer.get_config_section("stepper_z")['endstop_pin'].startswith("probe"):
            endstop = self._gtk.Button(label="Endstop")
            endstop.connect("clicked", self.start_calibration, "endstop")
            pobox.pack_start(endstop, True, True, 5)
        else:
            functions.remove("endstop")

        if (self._printer.config_section_exists("probe") or self._printer.config_section_exists("bltouch")):
            probe = self._gtk.Button(label="Probe")
            probe.connect("clicked", self.start_calibration, "probe")
            pobox.pack_start(probe, True, True, 5)
            functions.remove("mesh")
        else:
            functions.remove("probe")
            # This is used to do a manual bed mesh if there is no probe
            if self._printer.config_section_exists("bed_mesh"):
                mesh = self._gtk.Button(label="Bed mesh")
                mesh.connect("clicked", self.start_calibration, "mesh")
                pobox.pack_start(mesh, True, True, 5)
            else:
                functions.remove("mesh")

        if "delta" in self._screen.printer.get_config_section("printer")['kinematics']:
            if (self._printer.config_section_exists("probe") or self._printer.config_section_exists("bltouch")):
                delta = self._gtk.Button(label="Delta Automatic")
                delta.connect("clicked", self.start_calibration, "delta")
                pobox.pack_start(delta, True, True, 5)
            else:
                functions.remove("delta")
            delta_manual = self._gtk.Button(label="Delta Manual")
            delta_manual.connect("clicked", self.start_calibration, "delta_manual")
            pobox.pack_start(delta_manual, True, True, 5)
        else:
            functions.remove("delta")
            functions.remove("delta_manual")

        logging.info("Available functions: %s" % functions)

        self.labels['popover'] = Gtk.Popover()
        self.labels['popover'].add(pobox)
        self.labels['popover'].set_position(Gtk.PositionType.BOTTOM)

        if len(functions) > 1:
            self.widgets['start'].connect("clicked", self.on_popover_clicked)
        else:
            self.widgets['start'].connect("clicked", self.start_calibration, functions[0])

        distgrid = Gtk.Grid()
        j = 0
        for i in self.distances:
            self.widgets[i] = self._gtk.ToggleButton(i)
            self.widgets[i].set_direction(Gtk.TextDirection.LTR)
            self.widgets[i].connect("clicked", self.change_distance, i)
            ctx = self.widgets[i].get_style_context()
            if (self._screen.lang_ltr and j == 0) or (not self._screen.lang_ltr and j == len(self.distances)-1):
                ctx.add_class("distbutton_top")
            elif (not self._screen.lang_ltr and j == 0) or (self._screen.lang_ltr and j == len(self.distances)-1):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "1":
                ctx.add_class("distbutton_active")
            distgrid.attach(self.widgets[i], j, 0, 1, 1)
            j += 1

        self.widgets["1"].set_active(True)

        distances = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.widgets['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        distances.pack_start(self.widgets['move_dist'], True, True, 0)
        distances.pack_start(distgrid, True, True, 0)

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

    def on_popover_clicked(self, widget):
        self.labels['popover'].set_relative_to(widget)
        self.labels['popover'].show_all()

    def start_calibration(self, widget, method):
        x_position = y_position = 0
        self.labels['popover'].popdown()
        if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

        if method == "probe":
            # Get position from config
            printer = self._screen.connected_printer
            printer_cfg = self._config.get_printer_config(printer)
            logging.info(printer_cfg)
            if printer_cfg is not None:
                x_position = printer_cfg.getint("calibrate_x_position", 0)
                y_position = printer_cfg.getint("calibrate_y_position", 0)
            elif 'z_calibrate_position' in self._config.get_config():
                # OLD global way, this should be deprecated
                x_position = self._config.get_config()['z_calibrate_position'].getint("calibrate_x_position", 0)
                y_position = self._config.get_config()['z_calibrate_position'].getint("calibrate_y_position", 0)

            if x_position > 0 and y_position > 0:
                logging.debug("Configured probing position X: %.0f Y: %.0f", x_position, y_position)
                self._screen._ws.klippy.gcode_script('G0 X%d Y%d F3000' % (x_position, y_position))
            elif "delta" in self._screen.printer.get_config_section("printer")['kinematics']:
                logging.info("Detected delta kinematics calibrating at 0,0")
                self._screen._ws.klippy.gcode_script('G0 X%d Y%d F3000' % (0, 0))
            else:
                logging.debug("Position not configured, probing the middle of the bed")
                x_position = int(int(self._screen.printer.get_config_section("stepper_x")['position_max'])/2)
                y_position = int(int(self._screen.printer.get_config_section("stepper_y")['position_max'])/2)

                # Find probe offset
                klipper_cfg = self._screen.printer.get_config_section_list()
                x_offset = y_offset = 0
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
                if x_offset > 0 or y_offset > 0:
                    logging.debug("Substracting probe offset X: %.0f Y: %.0f", x_offset, y_offset)
                    x_position = self.apply_probe_offset(x_position, x_offset)
                    y_position = self.apply_probe_offset(y_position, y_offset)
                # Move
                self._screen._ws.klippy.gcode_script('G0 X%d Y%d F3000' % (x_position, y_position))

            self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_CALIBRATE)
        elif method == "mesh":
            self._screen._ws.klippy.gcode_script("BED_MESH_CALIBRATE")
        elif method == "delta":
            self._screen._ws.klippy.gcode_script("DELTA_CALIBRATE")
        elif method == "delta_manual":
            self._screen._ws.klippy.gcode_script("DELTA_CALIBRATE METHOD=manual")
        elif method == "endstop":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.Z_ENDSTOP_CALIBRATE)

    def apply_probe_offset(self, pos, offset):
        return max(0, int(float(pos) - offset))

    def process_update(self, action, data):
        _ = self.lang.gettext

        if action == "notify_status_update":
            if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
                self.widgets['zposition'].set_text("?")
            elif "toolhead" in data and "position" in data['toolhead']:
                self.updatePosition(data['toolhead']['position'])
        elif action == "notify_gcode_response":
            if "unknown" in data.lower():
                self.buttons_not_calibrating()
            elif "save_config" in data.lower():
                self.buttons_not_calibrating()
                self._screen.show_popup_message(_("Calibrated, save configuration to make it permanent"), level=1)
            elif "out of range" in data.lower():
                self._screen.show_popup_message("%s" % data)
                self.buttons_not_calibrating()
            elif "fail" in data.lower() and "use testz" in data.lower():
                self._screen.show_popup_message(_("Failed, adjust position first"))
                self.buttons_not_calibrating()
            elif "use testz" in data.lower() or "use abort" in data.lower() or "z position" in data.lower():
                self.buttons_calibrating()
        return

    def updatePosition(self, position):
        self.widgets['zposition'].set_text(str(round(position[2], 2)))

    def change_distance(self, widget, distance):
        if self.distance == distance:
            return

        ctx = self.widgets[str(self.distance)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.distance = distance
        ctx = self.widgets[self.distance].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.distances:
            if i == self.distance:
                continue
            self.widgets[str(i)].set_active(False)

    def move(self, widget, dir):
        dist = str(self.distance) if dir == "+" else "-" + str(self.distance)
        logging.info("# Moving %s", KlippyGcodes.testz_move(dist))
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
