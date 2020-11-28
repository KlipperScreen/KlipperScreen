import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.MovePanel")

def create_panel(*args):
    return MovePanel(*args)

class MovePanel(ScreenPanel):
    distance = 1
    distances = ['.1','.5','1','5','10','25']


    def initialize(self, panel_name):
        _ = self.lang.gettext

        grid = KlippyGtk.HomogeneousGrid()

        self.labels['x+'] = KlippyGtk.ButtonImage("move-x+", _("X+"), "color1")
        self.labels['x+'].connect("clicked", self.move, "X", "+")
        self.labels['x-'] = KlippyGtk.ButtonImage("move-x-", _("X-"), "color1")
        self.labels['x-'].connect("clicked", self.move, "X", "-")

        self.labels['y+'] = KlippyGtk.ButtonImage("move-y+", _("Y+"), "color2")
        self.labels['y+'].connect("clicked", self.move, "Y", "+")
        self.labels['y-'] = KlippyGtk.ButtonImage("move-y-", _("Y-"), "color2")
        self.labels['y-'].connect("clicked", self.move, "Y", "-")

        self.labels['z+'] = KlippyGtk.ButtonImage("move-z-", _("Z+"), "color3")
        self.labels['z+'].connect("clicked", self.move, "Z", "+")
        self.labels['z-'] = KlippyGtk.ButtonImage("move-z+", _("Z-"), "color3")
        self.labels['z-'].connect("clicked", self.move, "Z", "-")

        self.labels['home'] = KlippyGtk.ButtonImage("home", _("Home All"))
        self.labels['home'].connect("clicked", self.home)


        grid.attach(self.labels['x+'], 2, 1, 1, 1)
        grid.attach(self.labels['x-'], 0, 1, 1, 1)
        grid.attach(self.labels['y+'], 1, 0, 1, 1)
        grid.attach(self.labels['y-'], 1, 1, 1, 1)
        grid.attach(self.labels['z+'], 3, 0, 1, 1)
        grid.attach(self.labels['z-'], 3, 1, 1, 1)

        grid.attach(self.labels['home'], 0, 0, 1, 1)

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

        #space_grid = KlippyGtk.HomogeneousGrid()
        #space_grid.attach(Gtk.Label("Distance (mm):"),0,0,1,1)
        #space_grid.attach(distgrid,0,1,1,1)
        #space_grid.attach(Gtk.Label(" "),0,2,1,1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        bottomgrid = KlippyGtk.HomogeneousGrid()
        self.labels['pos_x'] = Gtk.Label("X: 0")
        self.labels['pos_y'] = Gtk.Label("Y: 0")
        self.labels['pos_z'] = Gtk.Label("Z: 0")
        self.labels['pos_x'].get_style_context().add_class("text")
        self.labels['pos_y'].get_style_context().add_class("text")
        self.labels['pos_z'].get_style_context().add_class("text")
        bottomgrid.attach(self.labels['pos_x'], 0, 0, 1, 1)
        bottomgrid.attach(self.labels['pos_y'], 1, 0, 1, 1)
        bottomgrid.attach(self.labels['pos_z'], 2, 0, 1, 1)
        box.pack_start(bottomgrid, True, True, 0)
        self.labels['move_dist'] = Gtk.Label(_("Move Distance (mm)"))
        self.labels['move_dist'].get_style_context().add_class("text")
        box.pack_start(self.labels['move_dist'], True, True, 0)
        box.pack_start(distgrid, True, True, 0)

        grid.attach(box, 0, 2, 3, 1)



        b = KlippyGtk.ButtonImage('back', _('Back'))
        b.connect("clicked", self._screen._menu_go_back)
        grid.attach(b, 3, 2, 1, 1)

        self.panel = grid
        self._screen.add_subscription(panel_name)

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
        dist = str(self.distance) if dir == "+" else "-" + str(self.distance)
        logging.info("# Moving " + axis + " " + dist + "mm")

        print("%s\n%s %s%s" % (KlippyGcodes.MOVE_RELATIVE, KlippyGcodes.MOVE, axis, dist))
        self._screen._ws.klippy.gcode_script(
            "%s\n%s %s%s" % (KlippyGcodes.MOVE_RELATIVE, KlippyGcodes.MOVE, axis, dist)
        )
