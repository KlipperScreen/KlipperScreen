import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

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

        label = Gtk.Label(_("Z Offset") + ": \n")
        self.widgets['zposition'] = Gtk.Label(_("Homing"))
        pos = Gtk.VBox()
        pos.set_vexpand(False)
        pos.set_valign(Gtk.Align.CENTER)
        pos.add(label)
        pos.add(self.widgets['zposition'])

        self.widgets['zpos'] = self._gtk.ButtonImage('z-farther', _("Raise Nozzle"), 'color4')
        self.widgets['zpos'].connect("clicked", self.move, "+")
        self.widgets['zneg'] = self._gtk.ButtonImage('z-closer', _("Lower Nozzle"), 'color1')
        self.widgets['zneg'].connect("clicked", self.move, "-")
        self.widgets['start'] = self._gtk.ButtonImage('resume', _("Start"), 'color3')
        self.widgets['start'].connect("clicked", self.start_calibration)

        self.widgets['complete'] = self._gtk.ButtonImage('complete', _('Accept'), 'color3')
        self.widgets['complete'].connect("clicked", self.accept)
        self.widgets['cancel'] = self._gtk.ButtonImage('cancel', _('Abort'), 'color2')
        self.widgets['cancel'].connect("clicked", self.abort)

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
        grid.attach(self.widgets['zpos'], 0, 0, 1, 1)
        grid.attach(self.widgets['start'], 1, 0, 1, 1)
        grid.attach(pos, 1, 1, 1, 1)
        grid.attach(self.widgets['zneg'], 0, 1, 1, 1)
        grid.attach(self.widgets['complete'], 2, 0, 1, 1)
        grid.attach(distances, 0, 2, 3, 1)
        grid.attach(self.widgets['cancel'], 2, 1, 1, 1)

        self.content.add(grid)

    def start_calibration(self, widget):
        if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

        if 'z_calibrate_position' in self._config.get_config():
            x_position = self._config.get_config()['z_calibrate_position'].getint("calibrate_x_position", 0)
            y_position = self._config.get_config()['z_calibrate_position'].getint("calibrate_y_position", 0)
            if x_position > 0 and y_position > 0:
                self._screen._ws.klippy.gcode_script('G0 X%d Y%d F3000' % (x_position, y_position))

        if (self._printer.config_section_exists("probe") or self._printer.config_section_exists("bltouch")):
            self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_CALIBRATE)
        else:
            self._screen._ws.klippy.gcode_script(KlippyGcodes.Z_ENDSTOP_CALIBRATE)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        if "toolhead" in data and "position" in data['toolhead']:
            self.updatePosition(data['toolhead']['position'])

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
        logging.info("Aborting Z calibrate")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.ABORT)
        self.menu_return(widget)

    def accept(self, widget):
        logging.info("Accepting Z calibrate")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.ACCEPT)

    # We need to track if the machine is calibrating or not to activate the appropriate buttons
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
