import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    distances = ["1", "10", "50"]
    distance = "10"
    temp_increment = 5

    def __init__(self, screen, title):
        title = title or _("Move")
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        self.settings = {}
        self.labels = {}
        self.temp_labels = {}

        # Main vertical layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        main_box.set_margin_top(8)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        self.content.add(main_box)

        # ===== Top Row: Z (left), X/Y (center), Speed Selector (right) =====
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        top_row.set_halign(Gtk.Align.CENTER)
        top_row.set_valign(Gtk.Align.CENTER)
        top_row.set_vexpand(True)

        # Z Section (left)
        z_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        z_box.set_valign(Gtk.Align.CENTER)
        z_label = Gtk.Label(label="Z")
        z_label.get_style_context().add_class("section-label")
        z_label.set_halign(Gtk.Align.CENTER)
        z_box.pack_start(z_label, False, False, 0)

        z_grid = Gtk.Grid()
        z_grid.set_row_spacing(4)
        z_grid.set_column_spacing(4)
        z_grid.set_halign(Gtk.Align.CENTER)

        # Z+ (up)
        btn_zp = self._create_jog_button("∧", "Z", "+")
        z_grid.attach(btn_zp, 0, 0, 1, 1)

        # Z- (down)
        btn_zm = self._create_jog_button("∨", "Z", "-")
        z_grid.attach(btn_zm, 0, 1, 1, 1)

        z_box.pack_start(z_grid, False, False, 0)
        top_row.pack_start(z_box, False, False, 0)

        # X/Y Section (center)
        xy_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        xy_box.set_valign(Gtk.Align.CENTER)
        xy_label = Gtk.Label(label="X/Y")
        xy_label.get_style_context().add_class("section-label")
        xy_label.set_halign(Gtk.Align.START)
        xy_label.set_margin_start(4)
        xy_box.pack_start(xy_label, False, False, 0)

        xy_grid = Gtk.Grid()
        xy_grid.set_row_spacing(4)
        xy_grid.set_column_spacing(4)
        xy_grid.set_halign(Gtk.Align.CENTER)

        # Y+ (up arrow) - row 0, col 1
        btn_yp = self._create_jog_button("∧", "Y", "+")
        xy_grid.attach(btn_yp, 1, 0, 1, 1)

        # X- (left arrow) - row 1, col 0
        btn_xm = self._create_jog_button("<", "X", "-")
        xy_grid.attach(btn_xm, 0, 1, 1, 1)

        # Home button - row 1, col 1 (center)
        btn_home = Gtk.Button()
        btn_home.get_style_context().add_class("jog-home-button")
        home_icon = Gtk.Label(label="⌂")
        home_icon.set_markup("<span size='x-large'>⌂</span>")
        btn_home.add(home_icon)
        btn_home.set_size_request(72, 72)
        btn_home.connect("clicked", self.home)
        xy_grid.attach(btn_home, 1, 1, 1, 1)

        # X+ (right arrow) - row 1, col 2
        btn_xp = self._create_jog_button(">", "X", "+")
        xy_grid.attach(btn_xp, 2, 1, 1, 1)

        # Y- (down arrow) - row 2, col 1
        btn_ym = self._create_jog_button("∨", "Y", "-")
        xy_grid.attach(btn_ym, 1, 2, 1, 1)

        xy_box.pack_start(xy_grid, False, False, 0)
        top_row.pack_start(xy_box, False, False, 0)

        # Jog Distance Selector (right, vertical stack)
        dist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dist_box.set_valign(Gtk.Align.CENTER)

        for d in self.distances:
            btn = Gtk.Button(label=f"{d}mm")
            btn.get_style_context().add_class("jog-distance")
            if d == self.distance:
                btn.get_style_context().add_class("jog-distance-active")
            btn.connect("clicked", self.change_distance, d)
            btn.set_size_request(100, 44)
            self.labels[f"dist_{d}"] = btn
            dist_box.pack_start(btn, False, False, 0)

        top_row.pack_start(dist_box, False, False, 0)

        main_box.pack_start(top_row, True, True, 0)

        # ===== Bottom: Temperature Controls =====
        temp_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        temp_bar.set_halign(Gtk.Align.CENTER)
        temp_bar.set_margin_bottom(10)
        temp_bar.set_margin_top(4)

        # Nozzle temp control
        nozzle_ctrl = self._create_temp_control("Nozzle", "extruder", 0.2, 0.6, 1.0)
        temp_bar.pack_start(nozzle_ctrl, False, False, 0)

        # Bed temp control
        bed_ctrl = self._create_temp_control("Bed", "heater_bed", 1.0, 0.5, 0.2)
        temp_bar.pack_start(bed_ctrl, False, False, 0)

        main_box.pack_end(temp_bar, False, False, 0)

        # Get printer config for speed limits
        printer_cfg = self._printer.get_config_section("printer")
        max_velocity = max(int(float(printer_cfg["max_velocity"])), 2)
        if "max_z_velocity" in printer_cfg:
            self.max_z_velocity = max(int(float(printer_cfg["max_z_velocity"])), 2)
        else:
            self.max_z_velocity = max_velocity

        # Start temp update timer
        GLib.timeout_add_seconds(1, self._update_temps)

    def _create_jog_button(self, symbol, axis, direction):
        """Create a jog movement button."""
        btn = Gtk.Button()
        btn.get_style_context().add_class("jog-button")
        lbl = Gtk.Label()
        lbl.set_markup(f"<span size='large'>{symbol}</span>")
        btn.add(lbl)
        btn.set_size_request(72, 72)
        btn.connect("clicked", self.move, axis, direction)
        return btn

    def _create_temp_control(self, label_text, device, r, g, b):
        """Create a temperature control with +/- buttons."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        # Minus button
        minus_btn = Gtk.Button(label="-")
        minus_btn.get_style_context().add_class("temp-adjust-btn")
        minus_btn.set_size_request(44, 48)
        minus_btn.connect("clicked", self._adjust_temp, device, -self.temp_increment)
        box.pack_start(minus_btn, False, False, 0)

        # Temperature card
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        card.get_style_context().add_class("temp-card")
        card.set_size_request(180, 52)

        # Indicator
        indicator = Gtk.DrawingArea()
        indicator.set_size_request(6, 28)
        indicator.connect("draw", self._draw_indicator, r, g, b)
        ind_box = Gtk.Box()
        ind_box.set_valign(Gtk.Align.CENTER)
        ind_box.set_margin_start(6)
        ind_box.add(indicator)
        card.pack_start(ind_box, False, False, 0)

        # Label and temp
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        info.set_valign(Gtk.Align.CENTER)
        name_lbl = Gtk.Label(label=label_text)
        name_lbl.get_style_context().add_class("temp-label")
        name_lbl.set_halign(Gtk.Align.START)
        info.add(name_lbl)

        temp_lbl = Gtk.Label(label="--°")
        temp_lbl.get_style_context().add_class("temp-value")
        temp_lbl.set_halign(Gtk.Align.START)
        info.add(temp_lbl)

        card.pack_start(info, True, True, 0)
        box.pack_start(card, False, False, 0)

        # Plus button
        plus_btn = Gtk.Button(label="+")
        plus_btn.get_style_context().add_class("temp-adjust-btn")
        plus_btn.set_size_request(44, 48)
        plus_btn.connect("clicked", self._adjust_temp, device, self.temp_increment)
        box.pack_start(plus_btn, False, False, 0)

        # Store temp label for updates
        self.temp_labels[device] = temp_lbl

        return box

    def _draw_indicator(self, widget, ctx, r, g, b):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        radius = width / 2
        ctx.set_source_rgb(r, g, b)
        ctx.arc(width / 2, radius, radius, 3.14159, 0)
        ctx.arc(width / 2, height - radius, radius, 0, 3.14159)
        ctx.close_path()
        ctx.fill()
        return True

    def _adjust_temp(self, widget, device, increment):
        """Adjust temperature by increment."""
        current_target = self._printer.get_stat(device, "target") or 0
        new_target = max(0, current_target + increment)

        # Enforce max temp
        max_temp = int(float(self._printer.get_config_section(device).get('max_temp', 300)))
        new_target = min(new_target, max_temp)

        if device == "extruder":
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(device), new_target)
        elif device == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(new_target)

    def _update_temps(self):
        """Update temperature displays."""
        for device, lbl in self.temp_labels.items():
            temp = self._printer.get_stat(device, "temperature")
            if temp is not None:
                lbl.set_label(f"{temp:.0f}°")
            else:
                lbl.set_label("--°")
        return True

    def change_distance(self, widget, distance):
        """Change jog distance selection."""
        logging.info(f"### Distance {distance}")
        # Remove active from old
        old_key = f"dist_{self.distance}"
        if old_key in self.labels:
            self.labels[old_key].get_style_context().remove_class("jog-distance-active")
        # Add active to new
        new_key = f"dist_{distance}"
        if new_key in self.labels:
            self.labels[new_key].get_style_context().add_class("jog-distance-active")
        self.distance = distance

    def move(self, widget, axis, direction):
        """Execute a jog movement."""
        # Safety: don't allow motion while printing
        if self._printer.state in ("printing",):
            self._screen.show_popup_message(_("Cannot move while printing"))
            return

        a = axis.lower()
        if self._config.get_config()["main"].getboolean(f"invert_{a}", False) and a != "z":
            direction = "-" if direction == "+" else "+"

        dist = f"{direction}{self.distance}"
        config_key = "move_speed_z" if a == "z" else "move_speed_xy"
        speed = (
            None
            if self.ks_printer_cfg is None
            else self.ks_printer_cfg.getint(config_key, None)
        )
        if speed is None:
            speed = self._config.get_config()["main"].getint(config_key, 50)
        speed = 60 * max(1, speed)
        script = f"{KlippyGcodes.MOVE_RELATIVE}\nG0 {axis}{dist} F{speed}"
        self._screen._send_action(widget, "printer.gcode.script", {"script": script})
        if self._printer.get_stat("gcode_move", "absolute_coordinates"):
            self._screen._ws.klippy.gcode_script("G90")

    def home(self, widget):
        """Home all axes."""
        if self._printer.state in ("printing",):
            self._screen.show_popup_message(_("Cannot home while printing"))
            return

        if "delta" in self._printer.get_config_section("printer")["kinematics"]:
            self._screen._send_action(widget, "printer.gcode.script", {"script": "G28"})
            return
        self._screen._send_action(widget, "printer.gcode.script", {"script": "G28"})

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        # Update temperatures from live data
        for device, lbl in self.temp_labels.items():
            if device in data:
                temp = self._printer.get_stat(device, "temperature")
                if temp is not None:
                    lbl.set_label(f"{temp:.0f}°")
