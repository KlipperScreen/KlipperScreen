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
    labels = {}
    distance = 1
    distances = ['.01', '.05', '.1', '.5', '1', '5']

    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, False)

    def initialize(self, panel_name):
        _ = self.lang.gettext
        grid = Gtk.Grid()

        label = Gtk.Label(_("Z Offset") + ": \n")
        self.labels['zposition'] = Gtk.Label(_("Homing"))
        pos = Gtk.VBox()
        pos.set_vexpand(False)
        pos.set_valign(Gtk.Align.CENTER)
        pos.add(label)
        pos.add(self.labels['zposition'])

        self.zpos = self._gtk.ButtonImage('z-farther', _("Raise Nozzle"))
        self.zpos.connect("clicked", self.move, "+")
        self.zpos.set_sensitive(False)
        self.zneg = self._gtk.ButtonImage('z-closer', _("Lower Nozzle"))
        self.zneg.connect("clicked", self.move, "-")
        self.zneg.set_sensitive(False)
        self.start = self._gtk.ButtonImage('resume', _("Start"), 'color3')
        self.start.connect("clicked", self.start_calibration)

        self.complete = self._gtk.ButtonImage('complete', _('Accept'))
        self.complete.connect("clicked", self.accept)
        self.complete.set_sensitive(False)
        cancel = self._gtk.ButtonImage('cancel', _('Abort'), 'color2')
        cancel.connect("clicked", self.abort)

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

        distances = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        distances.pack_start(self.labels['move_dist'], True, True, 0)
        distances.pack_start(distgrid, True, True, 0)

        grid.set_column_homogeneous(True)
        grid.attach(self.zpos, 0, 0, 1, 1)
        grid.attach(self.start, 1, 0, 1, 1)
        grid.attach(pos, 1, 1, 1, 1)
        grid.attach(self.zneg, 0, 1, 1, 1)
        grid.attach(self.complete, 2, 0, 1, 1)
        grid.attach(distances, 0, 2, 3, 1)
        grid.attach(cancel, 2, 1, 1, 1)

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

        self.start.get_style_context().remove_class('color3')
        self.zpos.set_sensitive(True)
        self.zpos.get_style_context().add_class('color4')
        self.zneg.set_sensitive(True)
        self.zneg.get_style_context().add_class('color1')
        self.complete.set_sensitive(True)
        self.complete.get_style_context().add_class('color3')

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        if "toolhead" in data and "position" in data['toolhead']:
            self.updatePosition(data['toolhead']['position'])

    def updatePosition(self, position):
        self.labels['zposition'].set_text(str(round(position[2], 2)))

    def change_distance(self, widget, distance):
        if self.distance == distance:
            return

        ctx = self.labels[str(self.distance)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.distance = distance
        ctx = self.labels[self.distance].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.distances:
            if i == self.distance:
                continue
            self.labels[str(i)].set_active(False)

    def move(self, widget, dir):
        dist = str(self.distance) if dir == "+" else "-" + str(self.distance)
        logging.info("# Moving %s", KlippyGcodes.probe_move(dist))
        self._screen._ws.klippy.gcode_script(KlippyGcodes.probe_move(dist))

    def abort(self, widget):
        logging.info("Aborting Z calibrate")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_ABORT)

        self.start.get_style_context().add_class('color3')
        self.zpos.set_sensitive(False)
        self.zpos.get_style_context().remove_class('color4')
        self.zneg.set_sensitive(False)
        self.zneg.get_style_context().remove_class('color1')
        self.complete.set_sensitive(False)
        self.complete.get_style_context().remove_class('color3')

        self.menu_return(widget)

    def accept(self, widget):
        logging.info("Accepting Z calibrate")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_ACCEPT)
        self.menu_return(widget)
