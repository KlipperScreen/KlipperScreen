import gi
import logging
import contextlib
import numpy as np

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib import rc
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from matplotlib.ticker import LinearLocator

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return BedMeshPanel(*args)


class BedMeshPanel(ScreenPanel):

    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)
        self.profiles = {}
        self.show_create = False
        self.active_mesh = None

    def initialize(self, panel_name):

        addprofile = self._gtk.ButtonImage("increase", " " + _("Add profile"), "color1", .66, Gtk.PositionType.LEFT, 1)
        addprofile.connect("clicked", self.show_create_profile)
        addprofile.set_hexpand(True)
        clear = self._gtk.ButtonImage("cancel", " " + _("Clear"), "color2", .66, Gtk.PositionType.LEFT, 1)
        clear.connect("clicked", self._clear_mesh)
        clear.set_hexpand(True)
        calibrate = self._gtk.ButtonImage("refresh", " " + _("Calibrate"), "color3", .66, Gtk.PositionType.LEFT, 1)
        calibrate.connect("clicked", self.calibrate_mesh)
        calibrate.set_hexpand(True)

        topbar = Gtk.Box(spacing=5)
        topbar.set_hexpand(True)
        topbar.set_vexpand(False)
        topbar.add(addprofile)
        topbar.add(clear)
        topbar.add(calibrate)

        # Create a grid for all profiles
        self.labels['profiles'] = Gtk.Grid()
        self.labels['profiles'].get_style_context().add_class("frame-item")
        self.labels['profiles'].set_valign(Gtk.Align.CENTER)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels['profiles'])
        scroll.set_vexpand(True)

        # Create a box to contain all of the above
        self.labels['main_box'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['main_box'].set_vexpand(True)
        self.labels['main_box'].pack_start(topbar, False, False, 0)
        self.labels['main_box'].pack_end(scroll, True, True, 0)

        self.load_meshes()

        self.content.add(self.labels['main_box'])

    def activate(self):
        with contextlib.suppress(KeyError):
            self.activate_mesh(self._screen.printer.get_stat("bed_mesh", "profile_name"))

    def activate_mesh(self, profile):
        if profile == "":
            logging.info("Clearing active profile")
            self.profiles[self.active_mesh]['button_box'].add(self.profiles[self.active_mesh]['load'])
            self.active_mesh = None
            return
        if profile not in self.profiles:
            self.add_profile(profile)

        logging.info(f"Active {self.active_mesh} changing to {profile}")
        self.profiles[profile]['button_box'].remove(self.profiles[profile]['load'])
        self.active_mesh = profile

    def add_profile(self, profile):
        logging.debug(f"Adding Profile: {profile}")
        name = Gtk.Label()
        name.set_markup(f"<big><b>{profile}</b></big>")
        name.set_hexpand(True)
        name.set_vexpand(False)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        buttons = {
            "save": self._gtk.ButtonImage("complete", _("Save"), "color3"),
            "delete": self._gtk.ButtonImage("cancel", _("Delete"), "color3"),
            "view": self._gtk.ButtonImage("bed-level", _("View Mesh"), "color1"),
            "load": self._gtk.ButtonImage("load", _("Load"), "color2"),
        }
        buttons["save"].connect("clicked", self.send_save_mesh, profile)
        buttons["delete"].connect("clicked", self.send_remove_mesh, profile)
        buttons["view"].connect("clicked", self.show_mesh, profile)
        buttons["load"].connect("clicked", self.send_load_mesh, profile)

        for b in buttons.values():
            b.set_hexpand(False)
            b.set_vexpand(False)
            b.set_halign(Gtk.Align.END)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        if profile != "default":
            button_box.add(buttons["save"])
        button_box.add(buttons["delete"])
        button_box.add(buttons["view"])
        button_box.add(buttons["load"])

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.pack_start(name, True, True, 0)
        box.pack_start(button_box, False, False, 0)

        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")
        frame.add(box)

        self.profiles[profile] = {
            "button_box": button_box,
            "row": frame,
            "load": buttons["load"],
            "save": buttons["save"],
            "delete": buttons["delete"],
            "view": buttons["view"],
        }

        pl = list(self.profiles)
        if "default" in pl:
            pl.remove('default')
        profiles = sorted(pl)
        pos = profiles.index(profile) + 1 if profile != "default" else 0

        self.labels['profiles'].insert_row(pos)
        self.labels['profiles'].attach(self.profiles[profile]['row'], 0, pos, 1, 1)
        self.labels['profiles'].show_all()

    def back(self):
        if self.show_create is True:
            self.remove_create()
            return True
        return False

    def load_meshes(self):
        bm_profiles = self._screen.printer.get_config_section_list("bed_mesh ")
        logging.info(f"Bed profiles: {bm_profiles}")
        for prof in bm_profiles:
            self.add_profile(prof[9:])

    def process_update(self, action, data):
        if action == "notify_status_update":
            with contextlib.suppress(KeyError):
                logging.info(data['bed_mesh'])
                self.activate_mesh(data['bed_mesh']['profile_name'])

    def remove_create(self):
        if self.show_create is False:
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

        pl = list(self.profiles)
        if "default" in pl:
            pl.remove('default')
        profiles = sorted(pl)
        pos = profiles.index(profile) + 1 if profile != "default" else 0
        self.labels['profiles'].remove_row(pos)
        del self.profiles[profile]

    def show_create_profile(self, widget):

        for child in self.content.get_children():
            self.content.remove(child)

        if "create_profile" not in self.labels:
            pl = self._gtk.Label(_("Profile Name:"))
            pl.set_hexpand(False)
            self.labels['profile_name'] = Gtk.Entry()
            self.labels['profile_name'].set_text('')
            self.labels['profile_name'].set_hexpand(True)
            self.labels['profile_name'].connect("activate", self.create_profile)
            self.labels['profile_name'].connect("focus-in-event", self._show_keyboard)
            self.labels['profile_name'].grab_focus_without_selecting()

            save = self._gtk.ButtonImage("complete", _("Save"), "color3")
            save.set_hexpand(False)
            save.connect("clicked", self.create_profile)

            box = Gtk.Box()
            box.pack_start(self.labels['profile_name'], True, True, 5)
            box.pack_start(save, False, False, 5)

            self.labels['create_profile'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            self.labels['create_profile'].set_valign(Gtk.Align.CENTER)
            self.labels['create_profile'].set_hexpand(True)
            self.labels['create_profile'].set_vexpand(True)
            self.labels['create_profile'].pack_start(pl, True, True, 5)
            self.labels['create_profile'].pack_start(box, True, True, 5)

        self.content.add(self.labels['create_profile'])
        self._show_keyboard()
        self.show_create = True

    def _show_keyboard(self, widget=None, event=None):
        self._screen.show_keyboard(entry=self.labels['profile_name'])

    def show_mesh(self, widget, profile):
        if profile == self.active_mesh:
            bm = self._printer.get_stat("bed_mesh")
            if bm is None:
                logging.info(f"Unable to load active mesh: {profile}")
                return
            matrix = 'probed_matrix'
            # if 'mesh_matrix' in bm and bm['mesh_matrix'][0]:
            #     matrix = 'mesh_matrix'
            x_range = [int(bm['mesh_min'][0]), int(bm['mesh_max'][0])]
            y_range = [int(bm['mesh_min'][1]), int(bm['mesh_max'][1])]
        else:
            bm = self._printer.get_config_section(f"bed_mesh {profile}")
            if bm is False:
                logging.info(f"Unable to load profile: {profile}")
                self.remove_profile(profile)
                return
            matrix = 'points'
            x_range = [int(bm['min_x']), int(bm['max_x'])]
            y_range = [int(bm['min_y']), int(bm['max_y'])]
        # Zscale can be offered as a slider instead of hardcoded values reasonable values 0.5 - 2 (mm)
        z_range = [min(min(min(bm[matrix])), -1), max(max(max(bm[matrix])), 1)]
        counts = [len(bm[matrix][0]), len(bm[matrix])]
        deltas = [(x_range[1] - x_range[0]) / (counts[0] - 1), (y_range[1] - y_range[0]) / (counts[1] - 1)]
        x = [(i * deltas[0]) + x_range[0] for i in range(counts[0])]
        y = [(i * deltas[0]) + y_range[0] for i in range(counts[1])]
        x, y = np.meshgrid(x, y)
        z = np.asarray(bm[matrix])

        rc('axes', edgecolor="#e2e2e2", labelcolor="#e2e2e2")
        rc(('xtick', 'ytick'), color="#e2e2e2")
        fig = plt.figure(facecolor='#12121277')
        ax = Axes3D(fig, azim=245, elev=23)
        ax.set(title=profile, xlabel="X", ylabel="Y", facecolor='none')
        ax.spines['bottom'].set_color("#e2e2e2")
        fig.add_axes(ax)
        # Color gradient could also be configurable as a slider reasonable values 0.1 - 0.2 (mm)
        surf = ax.plot_surface(x, y, z, cmap=cm.coolwarm, vmin=-0.2, vmax=0.2)

        chartbox = ax.get_position()
        ax.set_position([chartbox.x0, chartbox.y0 + 0.1, chartbox.width * .92, chartbox.height])

        ax.set_zlim(z_range[0], z_range[1])
        ax.zaxis.set_major_locator(LinearLocator(5))
        # A StrMethodFormatter is used automatically
        ax.zaxis.set_major_formatter('{x:.02f}')
        fig.colorbar(surf, shrink=0.7, aspect=5, pad=0.25)

        title = Gtk.Label()
        title.set_markup(f"<b>{profile}</b>")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.CENTER)

        canvas = FigureCanvas(fig)
        canvas.set_size_request(self._screen.width * .9, self._screen.height / 3 * 2)
        # Remove the "matplotlib-canvas" class which forces a white background.
        # https://github.com/matplotlib/matplotlib/commit/3c832377fb4c4b32fcbdbc60fdfedb57296bc8c0
        style_ctx = canvas.get_style_context()
        for css_class in style_ctx.list_classes():
            style_ctx.remove_class(css_class)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(title)
        box.add(canvas)
        box.show_all()

        buttons = [
            {"name": _("Close"), "response": Gtk.ResponseType.CANCEL}
        ]
        self._gtk.Dialog(self._screen, buttons, box, self._close_dialog)

    @staticmethod
    def _close_dialog(widget, response):
        widget.destroy()

    def create_profile(self, widget):
        name = self.labels['profile_name'].get_text()
        if " " in name:
            name = f'"{name}"'

        self._screen._ws.klippy.gcode_script(f"BED_MESH_PROFILE SAVE={name}")
        self.remove_create()

    def calibrate_mesh(self, widget):
        self._screen.show_popup_message(_("Calibrating"), level=1)
        if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

        self._screen._ws.klippy.gcode_script(
            "BED_MESH_CALIBRATE"
        )

        # Load zcalibrate to do a manual mesh
        if not (self._printer.config_section_exists("probe") or self._printer.config_section_exists("bltouch")):
            self.menu_item_clicked(widget, "refresh", {"name": "Mesh calibrate", "panel": "zcalibrate"})

    def _clear_mesh(self, widget):
        self._screen._ws.klippy.gcode_script(
            "BED_MESH_CLEAR"
        )

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
