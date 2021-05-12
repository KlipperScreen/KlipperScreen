import gi
import logging
import numpy as np

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib import rc
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.backends.backend_gtk3cairo import FigureCanvasGTK3Cairo as FigureCanvas
from matplotlib.ticker import LinearLocator

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return BedMeshPanel(*args)

class BedMeshPanel(ScreenPanel):
    active_mesh = None
    graphs = {}

    def initialize(self, panel_name):
        _ = self.lang.gettext

        self.show_create = False

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)

        # Create a grid for all profiles
        self.labels['profiles'] = Gtk.Grid()
        scroll.add(self.labels['profiles'])


        addprofile = self._gtk.ButtonImage("increase","  %s" % _("Add bed mesh profile"),
                "color1", .5, .5, Gtk.PositionType.LEFT, False)
        addprofile.connect("clicked", self.show_create_profile)
        addprofile.set_size_request(60,0)
        addprofile.set_hexpand(False)
        addprofile.set_halign(Gtk.Align.END)
        abox = Gtk.Box(spacing=0)
        abox.set_vexpand(False)
        abox.add(addprofile)

        # Create a box to contain all of the above
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.pack_start(abox, False, False, 0)
        box.pack_end(scroll, True, True, 0)

        self.load_meshes()

        self.labels['main_box'] = box
        self.control['back'].disconnect_by_func(self._screen._menu_go_back)
        self.control['back'].connect("clicked", self.back)
        self.content.add(self.labels['main_box'])
        self._screen.add_subscription(panel_name)

    def activate(self):
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels['main_box'])

        am = self._screen.printer.get_stat("bed_mesh","profile_name")
        self.activate_mesh(am)

    def activate_mesh(self, profile):
        if profile == "":
            profile = None

        logging.debug("Activating profile: %s %s" % (self.active_mesh, profile))
        if profile != self.active_mesh:
            if profile not in self.profiles:
                self.add_profile(profile)
            if self.active_mesh != None and self.active_mesh in self.profiles:
                a = self.profiles[self.active_mesh]
                a['buttons'].remove(a['refresh'])
                a['buttons'].pack_start(a['load'], False, False, 0)
            self.active_mesh = profile
            if self.active_mesh != None:
                a = self.profiles[profile]
                a['buttons'].remove(a['load'])
                a['buttons'].pack_start(a['refresh'], False, False, 0)
            self._screen.show_all()

    def add_profile(self, profile):
        _ = self.lang.gettext

        frame = Gtk.Frame()
        frame.set_property("shadow-type",Gtk.ShadowType.NONE)

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (profile))
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        load = self._gtk.ButtonImage("load",_("Load"),"color2")
        load.connect("clicked", self.send_load_mesh, profile)
        load.set_size_request(60,0)
        load.set_hexpand(False)
        load.set_halign(Gtk.Align.END)

        refresh = self._gtk.ButtonImage("refresh",_("Calibrate"),"color4")
        refresh.connect("clicked", self.calibrate_mesh)
        refresh.set_size_request(60,0)
        refresh.set_hexpand(False)
        refresh.set_halign(Gtk.Align.END)

        view = self._gtk.ButtonImage("bed-level",_("View Mesh"),"color1")
        view.connect("clicked", self.show_mesh, profile)
        view.set_size_request(60,0)
        view.set_hexpand(False)
        view.set_halign(Gtk.Align.END)

        info = self._gtk.ButtonImage("info",None,"color3")
        info.connect("clicked", self.show_mesh, profile)
        info.set_size_request(60,0)
        info.set_hexpand(False)
        info.set_halign(Gtk.Align.END)

        save = self._gtk.ButtonImage("sd",_("Save"),"color3")
        save.connect("clicked", self.send_save_mesh, profile)
        save.set_size_request(60,0)
        save.set_hexpand(False)
        save.set_halign(Gtk.Align.END)

        delete = self._gtk.ButtonImage("cancel",_("Delete"),"color3")
        delete.connect("clicked", self.send_remove_mesh, profile)
        delete.set_size_request(60,0)
        delete.set_hexpand(False)
        delete.set_halign(Gtk.Align.END)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_margin_top(10)
        dev.set_margin_end(15)
        dev.set_margin_start(15)
        dev.set_margin_bottom(10)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.add(labels)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        logging.debug("Profile compare: '%s' '%s'" % (self.active_mesh, profile))
        if self.active_mesh == profile:
            buttons.pack_start(refresh, False, False, 0)
        else:
            buttons.pack_start(load, False, False, 0)
        #buttons.pack_end(info, False, False, 0)

        if profile != "default":
            buttons.pack_end(save, False, False, 0)
            buttons.pack_end(delete, False, False, 0)
        buttons.pack_end(view, False, False, 0)

        dev.add(buttons)
        frame.add(dev)

        self.profiles[profile] = {
            "box": dev,
            "buttons": buttons,
            "row": frame,
            "load": load,
            "refresh": refresh,
            "save": save,
            "view": view,
        }

        l = list(self.profiles)
        if "default" in l:
            l.remove('default')
        profiles = sorted(l)
        pos = profiles.index(profile)+1 if profile != "default" else 0

        self.labels['profiles'].insert_row(pos)
        self.labels['profiles'].attach(self.profiles[profile]['row'], 0, pos, 1, 1)
        self.labels['profiles'].show_all()

        #Gdk.threads_add_idle(GLib.PRIORITY_LOW, self.create_graph, profile)

    def back(self, widget):
        if self.show_create == True:
            self.remove_create()
        else:
            self._screen._menu_go_back()

    def create_profile(self, widget):
        name = self.labels['profile_name'].get_text()
        if " " in name:
            name = '"%s"' % name

        self._screen._ws.klippy.gcode_script("BED_MESH_PROFILE SAVE=%s" % name)
        self.remove_create()

    def calibrate_mesh(self, widget):
        self._screen._ws.klippy.gcode_script(
            "BED_MESH_CALIBRATE"
        )

    def load_meshes(self):
        bm_profiles = self._screen.printer.get_config_section_list("bed_mesh ")
        self.profiles = {}
        for prof in bm_profiles:
            self.add_profile(prof[9:])

    def process_update(self, action, data):
        if action == "notify_status_update":
            if "bed_mesh" in data and "profile_name" in data['bed_mesh']:
                if data['bed_mesh']['profile_name'] != self.active_mesh:
                    self.activate_mesh(data['bed_mesh']['profile_name'])

    def remove_create(self):
        if self.show_create == False:
            return

        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)

        self.show_create = False
        self.content.add(self.labels['main_box'])
        self.content.show()

    def remove_profile(self, profile):
        if profile not in self.profiles:
            return

        l = list(self.profiles)
        if "default" in l:
            l.remove('default')
        profiles = sorted(l)
        pos = profiles.index(profile)+1 if profile != "default" else 0
        self.labels['profiles'].remove_row(pos)
        del self.profiles[profile]

    def send_load_mesh(self, widget, profile):
        self._screen._ws.klippy.gcode_script(
            KlippyGcodes.bed_mesh_load(profile)
        )

    def send_save_mesh(self, widget, profile):
        self._screen._ws.klippy.gcode_script(
            KlippyGcodes.bed_mesh_save(profile)
        )

    def send_remove_mesh(self, widget, profile):
        self._screen._ws.klippy.gcode_script(
            KlippyGcodes.bed_mesh_remove(profile)
        )
        self.remove_profile(profile)

    def show_create_profile(self, widget):
        _ = self.lang.gettext

        for child in self.content.get_children():
            self.content.remove(child)

        if "create_profile" not in self.labels:
            self.labels['create_profile'] = Gtk.VBox()
            self.labels['create_profile'].set_valign(Gtk.Align.START)

            box = Gtk.Box(spacing=5)
            box.set_size_request(self._gtk.get_content_width(), self._gtk.get_content_height() -
                    self._screen.keyboard_height - 20)
            box.set_hexpand(True)
            box.set_vexpand(False)
            self.labels['create_profile'].add(box)

            l = self._gtk.Label(_("Profile Name:"))
            l.set_hexpand(False)
            entry = Gtk.Entry()
            entry.set_hexpand(True)

            save = self._gtk.ButtonImage("sd",_("Save"),"color3")
            save.set_hexpand(False)
            save.connect("clicked", self.create_profile)


            self.labels['profile_name'] = entry
            box.pack_start(l, False, False, 5)
            box.pack_start(entry, True, True, 5)
            box.pack_start(save, False, False, 5)

        self.show_create = True
        self.labels['profile_name'].set_text('')
        self.content.add(self.labels['create_profile'])
        self.content.show()
        self._screen.show_keyboard()
        self.labels['profile_name'].grab_focus_without_selecting()

    def show_mesh(self, widget, profile):
        _ = self.lang.gettext

        bm = self._printer.get_config_section("bed_mesh %s" % profile)
        if bm == False:
            logging.info("Unable to load profile: %s" % profile)
            return

        if profile == self.active_mesh:
            abm = self._printer.get_stat("bed_mesh")
            if abm == None:
                logging.info("Unable to load active mesh: %s" % profile)
                return
            x_range = [int(abm['mesh_min'][0]), int(abm['mesh_max'][0])]
            y_range = [int(abm['mesh_min'][1]), int(abm['mesh_max'][1])]
            z_range = [min(min(abm['mesh_matrix'])), max(max(abm['mesh_matrix']))]
            counts = [len(abm['mesh_matrix'][0]), len(abm['mesh_matrix'])]
            deltas = [(x_range[1] - x_range[0] )/ (counts[0]-1), (y_range[1] - y_range[0]) / (counts[1]-1)]
            x = [(i*deltas[0])+x_range[0] for i in range(counts[0])]
            y = [(i*deltas[0])+y_range[0] for i in range(counts[1])]
            x, y = np.meshgrid(x, y)
            z = np.asarray(abm['mesh_matrix'])
        else:
            x_range = [int(bm['min_x']), int(bm['max_x'])]
            y_range = [int(bm['min_y']), int(bm['max_y'])]
            z_range = [min(min(bm['points'])), max(max(bm['points']))]
            deltas = [(x_range[1] - x_range[0] )/ (int(bm['x_count'])-1), (y_range[1] - y_range[0]) / (int(bm['y_count'])-1)]
            x = [(i*deltas[0])+x_range[0] for i in range(bm['x_count'])]
            y = [(i*deltas[0])+y_range[0] for i in range(bm['y_count'])]
            x, y = np.meshgrid(x, y)
            z = np.asarray(bm['points'])

        rc('axes', edgecolor="#fff", labelcolor="#fff")
        rc(('xtick','ytick'), color="#fff")
        fig = plt.figure()
        fig.patch.set_facecolor("black")
        ax = Axes3D(fig, auto_add_to_figure=False)

        ax.set_facecolor("black")
        ax.set(title=profile, xlabel="X", ylabel="Y")
        ax.spines['bottom'].set_color("#fff")

        fig.add_axes(ax)
        surf = ax.plot_surface(x, y, z, rstride=1, cstride=1, cmap=cm.coolwarm)

        ax.set_zlim(z_range[0], z_range[1])
        ax.zaxis.set_major_locator(LinearLocator(10))
        # A StrMethodFormatter is used automatically
        ax.zaxis.set_major_formatter('{x:.02f}')
        fig.colorbar(surf, shrink=0.5, aspect=5)

        box = Gtk.VBox()
        box.set_hexpand(True)
        box.set_vexpand(True)

        title = Gtk.Label()
        title.set_markup("<b>%s</b>" % profile)
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.CENTER)

        canvas_box = Gtk.Box()
        canvas_box.set_hexpand(True)
        canvas_box.set_vexpand(True)

        box.add(title)
        box.add(canvas_box)

        buttons = [
            {"name": _("Close"), "response": Gtk.ResponseType.CANCEL}
        ]
        dialog = self._gtk.Dialog(self._screen, buttons, box, self._close_dialog)

        alloc = canvas_box.get_allocation()
        canvas = FigureCanvas(fig)
        canvas.set_size_request(alloc.width, self._screen.height/3*2)
        canvas_box.add(canvas)
        canvas_box.show_all()


    def _close_dialog(self, widget, response):
        widget.destroy()
