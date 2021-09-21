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
        box = Gtk.VBox()
        box.set_vexpand(False)
        box.set_valign(Gtk.Align.CENTER)

        box.add(label)
        box.add(self.labels['zposition'])

        zpos = self._gtk.ButtonImage('z-farther', _("Raise Nozzle"), 'color3')
        zpos.connect("clicked", self.move, "+")
        zneg = self._gtk.ButtonImage('z-closer', _("Lower Nozzle"), 'color2')
        zneg.connect("clicked", self.move, "-")

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

        bottombox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        bottombox.pack_start(self.labels['move_dist'], True, True, 0)
        bottombox.pack_start(distgrid, True, True, 0)

        complete = self._gtk.ButtonImage('complete', _('Accept'), 'color4')
        complete.connect("clicked", self.accept)

        b = self._gtk.ButtonImage('cancel', _('Abort'), 'color1')
        b.connect("clicked", self.abort)


        grid.set_column_homogeneous(True)
        grid.attach(zpos, 0, 0, 1, 1)
        grid.attach(box, 1, 0, 2, 2)
        grid.attach(zneg, 0, 1, 1, 1)
        grid.attach(complete, 3, 0, 1, 1)
        grid.attach(bottombox, 0, 2, 4, 1)
        grid.attach(b, 3, 1, 1, 1)


        self.content.add(grid)

    def activate(self):
        if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
        self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_CALIBRATE)

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
        self.menu_return(widget)

    def accept(self, widget):
        logging.info("Accepting Z calibrate")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.PROBE_ACCEPT)
        self.menu_return(widget)
