import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.BedMeshPanel")

def create_panel(*args):
    return BedMeshPanel(*args)

class BedMeshPanel(ScreenPanel):
    active_mesh = None
    graphs = {}

    def initialize(self, panel_name):
        _ = self.lang.gettext

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)

        # Create a grid for all profiles
        self.labels['profiles'] = Gtk.Grid()
        scroll.add(self.labels['profiles'])

        # Create a box to contain all of the above
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.pack_start(scroll, True, True, 0)

        self.load_meshes()

        self.content.add(box)
        self._screen.add_subscription(panel_name)

    def activate(self):
        am = self._screen.printer.get_stat("bed_mesh","profile_name")
        self.activate_mesh(am)

    def activate_mesh(self, profile):
        if profile == "":
            profile = None

        logger.debug("Activating profile: %s %s" % (self.active_mesh, profile))
        if profile != self.active_mesh:
            if self.active_mesh != None:
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
        frame = Gtk.Frame()
        frame.set_property("shadow-type",Gtk.ShadowType.NONE)

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (profile))
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        load = self._gtk.ButtonImage("load","Load","color2")
        load.connect("clicked", self.send_load_mesh, profile)
        load.set_size_request(60,0)
        load.set_hexpand(False)
        load.set_halign(Gtk.Align.END)

        refresh = self._gtk.ButtonImage("refresh","Calibrate","color4")
        refresh.connect("clicked", self.calibrate_mesh)
        refresh.set_size_request(60,0)
        refresh.set_hexpand(False)
        refresh.set_halign(Gtk.Align.END)

        info = self._gtk.ButtonImage("info",None,"color3")
        info.connect("clicked", self.show_mesh, profile)
        info.set_size_request(60,0)
        info.set_hexpand(False)
        info.set_halign(Gtk.Align.END)

        save = self._gtk.ButtonImage("sd","Save","color3")
        save.connect("clicked", self.send_save_mesh, profile)
        save.set_size_request(60,0)
        save.set_hexpand(False)
        save.set_halign(Gtk.Align.END)

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
        logger.debug("Profile compare: '%s' '%s'" % (self.active_mesh, profile))
        if self.active_mesh == profile:
            buttons.pack_start(refresh, False, False, 0)
        else:
            buttons.pack_start(load, False, False, 0)
        #buttons.pack_end(info, False, False, 0)

        if profile != "default":
            buttons.pack_end(save, False, False, 0)

        dev.add(buttons)
        frame.add(dev)

        self.profiles[profile] = {
            "box": dev,
            "buttons": buttons,
            "row": frame,
            "load": load,
            "refresh": refresh,
            "save": save
        }

        profiles = sorted(self.profiles)
        pos = profiles.index(profile)

        self.labels['profiles'].insert_row(pos)
        self.labels['profiles'].attach(self.profiles[profile]['row'], 0, pos, 1, 1)
        self.labels['profiles'].show_all()

        #Gdk.threads_add_idle(GLib.PRIORITY_LOW, self.create_graph, profile)

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

    def send_load_mesh(self, widget, profile):
        self._screen._ws.klippy.gcode_script(
            KlippyGcodes.bed_mesh_load(profile)
        )

    def send_save_mesh(self, widget, profile):
        self._screen._ws.klippy.gcode_script(
            KlippyGcodes.bed_mesh_save(profile)
        )

    def show_mesh(self, widget, profile):
        _ = self.lang.gettext

        buttons = [
            {"name": _("Close"), "response": Gtk.ResponseType.CANCEL}
        ]
        dialog = self._gtk.Dialog(self._screen, buttons, self.graphs[profile], self._close_dialog)

    def _close_dialog(self, widget, response):
        widget.destroy()
