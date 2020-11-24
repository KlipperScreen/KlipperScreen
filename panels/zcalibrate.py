import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

import logging
logger = logging.getLogger("KlipperScreen.ZCalibratePanel")

def create_panel(*args):
    return ZCalibratePanel(*args)

class ZCalibratePanel(ScreenPanel):
    _screen = None
    labels = {}
    distance = 1
    distances = ['.01','.05','.1','.5','1','5']

    def initialize(self, panel_name):
        _ = self.lang.gettext
        grid = KlippyGtk.HomogeneousGrid()

        label = Gtk.Label(_("Z Offset") + ": ")
        label.get_style_context().add_class('temperature_entry')
        self.labels['zpos'] = Gtk.Label(_("Homing"))
        self.labels['zpos'].get_style_context().add_class('temperature_entry')
        box = Gtk.Box()

        box.add(label)
        box.add(self.labels['zpos'])

        zpos = KlippyGtk.ButtonImage('z-offset-decrease',_("Raise Nozzle"))
        zpos.connect("clicked", self.move, "+")
        zneg = KlippyGtk.ButtonImage('z-offset-increase',_("Lower Nozzle"))
        zneg.connect("clicked", self.move, "-")

        distgrid = Gtk.Grid()
        j = 0;
        for i in self.distances:
            self.labels[i] = KlippyGtk.ToggleButton(i)
            self.labels[i].connect("clicked", self.change_distance, i)
            ctx = self.labels[i].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.distances)-1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "1":
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[i], j, 0, 1, 1)
            j += 1

        self.labels["1"].set_active(True)

        space_grid = KlippyGtk.HomogeneousGrid()
        space_grid.attach(Gtk.Label(_("Distance (mm)") + ":"),0,0,1,1)
        space_grid.attach(distgrid,0,1,1,1)
        space_grid.attach(Gtk.Label(" "),0,2,1,1)

        complete = KlippyGtk.ButtonImage('complete',_('Accept'),'color2')
        complete.connect("clicked", self.accept)


        b = KlippyGtk.ButtonImage('back', _('Abort'))
        b.connect("clicked", self.abort)


        grid.attach(zpos, 1, 0, 1, 1)
        grid.attach(box, 0, 1, 2, 1)
        grid.attach(zneg, 1, 1, 1, 1)
        grid.attach(complete, 3, 1, 1, 1)
        grid.attach(space_grid, 0, 2, 3, 1)
        grid.attach(b, 3, 2, 1, 1)


        self.panel = grid
        self._screen.add_subscription(panel_name)

    def activate(self):
        if self._screen.printer.get_stat("toolhead","homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
        self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_CALIBRATE)

    def process_update(self, data):
        if "toolhead" in data and "position" in data['toolhead']:
            self.updatePosition(data['toolhead']['position'])

    def updatePosition(self, position):
        self.labels['zpos'].set_text(str(round(position[2],2)))

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
        logger.info("# Moving %s", KlippyGcodes.probe_move(dist))
        self._screen._ws.klippy.gcode_script(KlippyGcodes.probe_move(dist))

    def abort(self, widget):
        logger.info("Aborting Z calibrate")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_ABORT)
        self._screen._menu_go_back(widget)

    def accept(self, widget):
        logger.info("Accepting Z calibrate")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_ACCEPT)
        #self._screen._ws.klippy.gcode_script(KlippyGcodes.SAVE_CONFIG)
