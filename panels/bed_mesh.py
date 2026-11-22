import contextlib
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.bedmap import BedMap


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Bed Mesh")
        super().__init__(screen, title)
        self.show_create = False
        self.active_mesh = None
        section = self._printer.get_config_section("bed_mesh")
        self.mesh_radius = section["mesh_radius"] if "mesh_radius" in section else None
        self.profiles = {}
        self.buttons = {
            "calib": self._gtk.Button(
                "refresh", " " + _("Calibrate"), "color3", self.bts, Gtk.PositionType.LEFT, 1
            ),
            "add": self._gtk.Button(
                "increase", " " + _("Add profile"), "color1", self.bts, Gtk.PositionType.LEFT, 1
            ),
            "clear": self._gtk.Button(
                "cancel", " " + _("Clear"), "color2", self.bts, Gtk.PositionType.LEFT, 1
            ),
        }
        self.buttons["add"].connect("clicked", self.show_create_profile)
        self.buttons["clear"].connect("clicked", self.send_clear_mesh)
        self.buttons["calib"].connect("clicked", self.calibrate_mesh)

        topbar = Gtk.Box(spacing=5, hexpand=True, vexpand=False)
        topbar.add(self.buttons["calib"])
        topbar.add(self.buttons["add"])
        topbar.add(self.buttons["clear"])

        # Create a grid for all profiles
        self.labels["profiles"] = Gtk.Grid(valign=Gtk.Align.CENTER)

        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.add(self.labels["profiles"])

        self.load_meshes()

        grid = Gtk.Grid(column_homogeneous=True)
        grid.attach(topbar, 0, 0, 2, 1)
        self.labels["map"] = BedMap(self._gtk.font_size, self.active_mesh)
        if self._screen.vertical_mode:
            grid.attach(self.labels["map"], 0, 2, 2, 1)
            grid.attach(self.scroll, 0, 3, 2, 1)
            self.labels["map"].set_size_request(
                self._gtk.content_width - 30, self._gtk.content_height * 0.4
            )
        else:
            grid.attach(self.labels["map"], 0, 2, 1, 1)
            grid.attach(self.scroll, 1, 2, 1, 1)
        self.labels["main_grid"] = grid
        self.content.add(self.labels["main_grid"])

    def activate(self):
        self.load_meshes()
        with contextlib.suppress(KeyError):
            self.activate_mesh(self._printer.get_stat("bed_mesh", "profile_name"))
        GLib.idle_add(self._scroll_to_active)

    def _scroll_to_active(self):
        if self.active_mesh in self.profiles:
            adjustment = self.scroll.get_vadjustment()
            row_top = self.profiles[self.active_mesh]["row"].get_allocation().y
            adjustment.set_value(min(row_top, adjustment.get_upper() - adjustment.get_page_size()))
        return False

    def _update_rows(self):
        for name, row in self.profiles.items():
            active = name == self.active_mesh
            for widget, style in ((row["row"], "button_active"), (row["marker"], "checked")):
                if active:
                    widget.get_style_context().add_class(style)
                else:
                    widget.get_style_context().remove_class(style)
            row["save"].set_sensitive(self.active_mesh is not None and not active)

    def activate_mesh(self, profile):
        if profile == "":
            logging.info("Clearing active profile")
            self._clear_profile()
            return
        if profile not in self.profiles:
            self.add_profile(profile)

        if self.active_mesh != profile:
            logging.info(f"Active {self.active_mesh} changing to {profile}")
        self.active_mesh = profile
        self._update_rows()
        self.update_graph(profile=profile)
        self.buttons["clear"].set_sensitive(True)

    def retrieve_bm(self, profile):
        if profile is None:
            return None
        if profile == self.active_mesh:
            return self._printer.get_stat("bed_mesh")
        else:
            return self._printer.get_config_section(f"bed_mesh {profile}")

    def update_graph(self, widget=None, profile=None):
        if self.ks_printer_cfg is not None:
            invert_x = self._config.get_config()["main"].getboolean("invert_x", False)
            invert_y = self._config.get_config()["main"].getboolean("invert_y", False)
            self.labels["map"].set_inversion(x=invert_x, y=invert_y)
            rotation = self.ks_printer_cfg.getint("screw_rotation", 0)
            if rotation not in (0, 90, 180, 270):
                rotation = 0
            self.labels["map"].set_rotation(rotation)
            logging.info(f"Inversion X: {invert_x} Y: {invert_y} Rotation: {rotation}")
        self.labels["map"].update_bm(self.retrieve_bm(profile), self.mesh_radius)
        self.labels["map"].queue_draw()

    def add_profile(self, profile):
        logging.debug(f"Adding Profile: {profile}")
        marker = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        marker.get_style_context().add_class("radio-marker")
        label = Gtk.Label(
            hexpand=True,
            xalign=0,
            use_markup=True,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
        )
        label.set_markup(f"<big><b>{GLib.markup_escape_text(profile)}</b></big>")
        name_box = Gtk.Box()
        name_box.add(marker)
        name_box.add(label)
        name = self._gtk.Button()
        name.get_style_context().add_class("profile-name")
        name.add(name_box)
        name.set_vexpand(False)
        name.connect("clicked", self.send_load_mesh, profile)

        buttons = {
            "save": self._gtk.Button("sd", None, "color4", self.bts),
            "delete": self._gtk.Button("delete", None, "color2", self.bts),
        }
        buttons["save"].connect("clicked", self.send_save_mesh, profile)
        buttons["delete"].connect("clicked", self.send_remove_mesh, profile)

        for b in buttons.values():
            b.set_hexpand(False)
            b.set_vexpand(False)
            b.set_halign(Gtk.Align.END)

        button_box = Gtk.Box(spacing=5)
        if profile != "default":
            button_box.add(buttons["save"])
        button_box.add(buttons["delete"])

        box = Gtk.Box(spacing=5)
        box.get_style_context().add_class("frame-item")
        box.pack_start(name, True, True, 0)
        box.pack_start(button_box, False, False, 0)

        self.profiles[profile] = {
            "name": name,
            "marker": marker,
            "button_box": button_box,
            "row": box,
            "save": buttons["save"],
            "delete": buttons["delete"],
        }

        pos = self._get_position(profile)
        self.labels["profiles"].insert_row(pos)
        self.labels["profiles"].attach(self.profiles[profile]["row"], 0, pos, 1, 1)
        self.labels["profiles"].show_all()
        self._update_rows()

    def back(self):
        if self.show_create is True:
            self.remove_create()
            return True
        return False

    def load_meshes(self):
        bm_profiles = self._printer.get_stat("bed_mesh", "profiles")
        for prof in bm_profiles:
            if prof not in self.profiles:
                self.add_profile(prof)
        for prof in list(self.profiles):
            if prof not in bm_profiles:
                self.remove_profile(prof)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        if "bed_mesh" in data:
            if "profile_name" in data["bed_mesh"]:
                self.activate_mesh(data["bed_mesh"]["profile_name"])
            self.load_meshes()

    def remove_create(self):
        if self.show_create is False:
            return

        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)

        self.show_create = False
        self.content.add(self.labels["main_grid"])
        self.content.show()

    def remove_profile(self, profile):
        if profile not in self.profiles:
            return

        pos = self._get_position(profile)
        self.labels["profiles"].remove_row(pos)
        del self.profiles[profile]
        if not self.profiles:
            self._clear_profile()

    def _clear_profile(self):
        self.active_mesh = None
        self._update_rows()
        self.update_graph()
        self.buttons["clear"].set_sensitive(False)
        self.remove_create()

    def _get_position(self, profile):
        pl = list(self.profiles)
        if "default" in pl:
            pl.remove("default")
        profiles = sorted(pl)
        return profiles.index(profile) + 1 if profile != "default" else 0

    def show_create_profile(self, widget):

        for child in self.content.get_children():
            self.content.remove(child)

        if "create_profile" not in self.labels:
            pl = Gtk.Label(label=_("Profile Name:"), hexpand=False)
            self.labels["profile_name"] = Gtk.Entry(hexpand=True, text="")
            self.labels["profile_name"].connect("activate", self.create_profile)
            self.labels["profile_name"].connect("touch-event", self._screen.show_keyboard)
            self.labels["profile_name"].connect("button-press-event", self._screen.show_keyboard)

            save = self._gtk.Button("complete", _("Save"), "color3")
            save.set_hexpand(False)
            save.connect("clicked", self.create_profile)

            box = Gtk.Box()
            box.pack_start(self.labels["profile_name"], True, True, 5)
            box.pack_start(save, False, False, 5)

            self.labels["create_profile"] = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=5,
                valign=Gtk.Align.CENTER,
                hexpand=True,
                vexpand=True,
            )
            self.labels["create_profile"].pack_start(pl, True, True, 5)
            self.labels["create_profile"].pack_start(box, True, True, 5)

        self.content.add(self.labels["create_profile"])
        self.labels["create_profile"].show_all()
        self.labels["profile_name"].grab_focus_without_selecting()
        self.show_create = True

    def create_profile(self, widget):
        name = self.labels["profile_name"].get_text()
        if self.active_mesh is None:
            self.calibrate_mesh(widget)

        self._screen._send_action(
            widget, "printer.gcode.script", {"script": f"BED_MESH_PROFILE SAVE={name}"}
        )
        self.remove_create()

    def calibrate_mesh(self, widget):
        widget.set_sensitive(False)
        self._screen.show_popup_message(_("Calibrating"), level=1)
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.api.gcode_script("G28")
        if "Z_TILT_ADJUST" in self._printer.available_commands and not bool(
            self._printer.get_stat("z_tilt", "applied")
        ):
            self._screen._ws.api.gcode_script("Z_TILT_ADJUST")
        if "QUAD_GANTRY_LEVEL" in self._printer.available_commands and not bool(
            self._printer.get_stat("quad_gantry_level", "applied")
        ):
            self._screen._ws.api.gcode_script("QUAD_GANTRY_LEVEL")
        self._screen._send_action(widget, "printer.gcode.script", {"script": "BED_MESH_CALIBRATE"})

    def send_clear_mesh(self, widget):
        self._screen._send_action(widget, "printer.gcode.script", {"script": "BED_MESH_CLEAR"})

    def send_load_mesh(self, widget, profile):
        self._screen._send_action(
            widget, "printer.gcode.script", {"script": KlippyGcodes.bed_mesh_load(profile)}
        )

    def send_save_mesh(self, widget, profile):
        self._screen._confirm_send_action(
            widget,
            _("Overwrite %(target)s mesh profile with %(source)s?")
            % {
                "target": f"<b>{GLib.markup_escape_text(profile)}</b>",
                "source": f"<b>{GLib.markup_escape_text(self.active_mesh)}</b>",
            },
            "printer.gcode.script",
            {"script": KlippyGcodes.bed_mesh_save(profile)},
        )

    def send_remove_mesh(self, widget, profile):
        self._screen._confirm_send_action(
            widget,
            _("Delete mesh profile?") + "\n\n" + GLib.markup_escape_text(profile),
            "printer.gcode.script",
            {"script": KlippyGcodes.bed_mesh_remove(profile)},
        )
