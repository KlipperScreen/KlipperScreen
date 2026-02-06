import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf
from ks_includes.screen_panel import ScreenPanel


# Filament temperature profiles: (nozzle_temp, bed_temp)
FILAMENT_PROFILES = {
    'PLA':  (210, 60),
    'PETG': (230, 80),
    'ABS':  (240, 100),
    'N/A':  (0, 0),
}

# Spool colors for display: (fill_r, fill_g, fill_b) for the spool icon tint
SPOOL_COLORS = {
    'PLA':  (0.93, 0.16, 0.16),   # Red
    'PETG': (0.88, 0.88, 0.88),   # White/gray
    'ABS':  (0.30, 0.30, 0.30),   # Dark gray
    'N/A':  (0.30, 0.30, 0.30),   # Dark gray
}


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        self.spool_svg_path = os.path.join(styles_dir, "spool.svg")

        self.selected_filament = None
        self.filament_buttons = {}

        # Check if UNLOAD_FILAMENT macro exists
        macros = self._printer.get_config_section_list("gcode_macro ")
        self.has_unload = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        main_box.set_margin_top(20)
        main_box.set_margin_start(30)
        main_box.set_margin_end(30)
        main_box.set_margin_bottom(12)
        self.content.add(main_box)

        # 2x2 grid of filament buttons
        grid = Gtk.Grid()
        grid.set_row_spacing(12)
        grid.set_column_spacing(12)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        grid.set_vexpand(True)
        grid.set_hexpand(True)
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)

        filament_types = ['PLA', 'PETG', 'ABS', 'N/A']
        positions = [(0, 0), (1, 0), (0, 1), (1, 1)]

        for ftype, (col, row) in zip(filament_types, positions):
            btn = self._create_filament_button(ftype)
            self.filament_buttons[ftype] = btn
            grid.attach(btn, col, row, 1, 1)

        main_box.pack_start(grid, True, True, 0)

        # Unload Filament button
        unload_btn = Gtk.Button()
        unload_btn.get_style_context().add_class("filament-unload")
        unload_lbl = Gtk.Label(label="Unload Filament")
        unload_btn.add(unload_lbl)
        unload_btn.set_hexpand(True)
        unload_btn.connect("clicked", self._unload_filament)
        if not self.has_unload:
            unload_btn.set_sensitive(False)
        main_box.pack_end(unload_btn, False, False, 0)

    def _create_filament_button(self, filament_type):
        """Create a filament type selection button with spool icon."""
        btn = Gtk.Button()
        btn.get_style_context().add_class("filament-button")
        btn.set_hexpand(True)
        btn.set_vexpand(True)

        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        inner.set_halign(Gtk.Align.CENTER)
        inner.set_valign(Gtk.Align.CENTER)

        # Spool icon (using a colored circle as spool representation)
        spool_area = Gtk.DrawingArea()
        spool_area.set_size_request(48, 48)
        r, g, b = SPOOL_COLORS.get(filament_type, (0.5, 0.5, 0.5))
        spool_area.connect("draw", self._draw_spool, r, g, b)
        inner.pack_start(spool_area, False, False, 0)

        # Filament label
        lbl = Gtk.Label(label=filament_type)
        lbl.set_halign(Gtk.Align.START)
        inner.pack_start(lbl, False, False, 0)

        btn.add(inner)
        btn.connect("clicked", self._select_filament, filament_type)

        return btn

    def _draw_spool(self, widget, ctx, r, g, b):
        """Draw a simple spool icon."""
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx = w / 2
        cy = h / 2
        radius = min(w, h) / 2 - 2

        # Outer ring
        ctx.set_source_rgb(r, g, b)
        ctx.arc(cx, cy, radius, 0, 2 * 3.14159)
        ctx.fill()

        # Inner hole (dark)
        ctx.set_source_rgb(0.12, 0.13, 0.16)
        ctx.arc(cx, cy, radius * 0.35, 0, 2 * 3.14159)
        ctx.fill()

        # Rim highlight
        ctx.set_source_rgba(1, 1, 1, 0.15)
        ctx.set_line_width(2)
        ctx.arc(cx, cy, radius - 1, 0, 2 * 3.14159)
        ctx.stroke()

        return True

    def _select_filament(self, widget, filament_type):
        """Select a filament type and set temperature profile."""
        # Update visual selection
        for ftype, btn in self.filament_buttons.items():
            ctx = btn.get_style_context()
            ctx.remove_class("filament-selected")

        widget.get_style_context().add_class("filament-selected")
        self.selected_filament = filament_type

        # Set temperature profile
        nozzle_temp, bed_temp = FILAMENT_PROFILES.get(filament_type, (0, 0))
        if nozzle_temp > 0:
            self._screen._ws.klippy.set_tool_temp(
                self._printer.get_tool_number("extruder"), nozzle_temp
            )
            logging.info(f"Set nozzle temp to {nozzle_temp}°C for {filament_type}")
        if bed_temp > 0:
            self._screen._ws.klippy.set_bed_temp(bed_temp)
            logging.info(f"Set bed temp to {bed_temp}°C for {filament_type}")

        if filament_type == 'N/A':
            # Clear temperatures
            self._screen._ws.klippy.set_tool_temp(
                self._printer.get_tool_number("extruder"), 0
            )
            self._screen._ws.klippy.set_bed_temp(0)
            logging.info("Cleared temperatures (N/A selected)")

    def _unload_filament(self, widget):
        """Run the UNLOAD_FILAMENT macro."""
        if self.has_unload:
            self._screen._send_action(
                widget, "printer.gcode.script",
                {"script": "UNLOAD_FILAMENT"}
            )
            logging.info("Unload filament command sent")
        else:
            self._screen.show_popup_message("UNLOAD_FILAMENT macro not found")
