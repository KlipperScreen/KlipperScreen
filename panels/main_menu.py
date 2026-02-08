import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        eagle_path = os.path.join(styles_dir, "cro_eagle.svg")

        self.temp_labels = {}

        # Main vertical layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        self.content.add(main_box)

        # Center area: eagle logo
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        center_box.set_hexpand(True)
        center_box.set_vexpand(True)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)

        if os.path.exists(eagle_path):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(eagle_path, 320, 280)
            eagle_image = Gtk.Image.new_from_pixbuf(pixbuf)
            eagle_image.set_halign(Gtk.Align.CENTER)
            eagle_image.set_valign(Gtk.Align.CENTER)
            center_box.add(eagle_image)

        main_box.pack_start(center_box, True, True, 0)

        # Bottom temperature bar
        temp_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        temp_bar.set_halign(Gtk.Align.CENTER)
        temp_bar.set_valign(Gtk.Align.END)
        temp_bar.set_margin_bottom(12)
        temp_bar.set_margin_start(20)
        temp_bar.set_margin_end(20)

        # Nozzle temperature card
        nozzle_card = self._create_temp_card("Nozzle", "nozzle_blue", "extruder")
        temp_bar.pack_start(nozzle_card, False, False, 0)

        # Bed temperature card
        bed_card = self._create_temp_card("Bed", "bed_orange", "heater_bed")
        temp_bar.pack_start(bed_card, False, False, 0)

        main_box.pack_end(temp_bar, False, False, 0)

        # Start temperature update timer
        GLib.timeout_add_seconds(1, self._update_temps)

    def _create_temp_card(self, label_text, icon_type, device):
        """Create a temperature display card matching the mockup."""
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card.get_style_context().add_class("temp-card")
        card.set_size_request(280, 56)

        # Thermometer icon (colored indicator)
        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        icon_box.set_valign(Gtk.Align.CENTER)
        icon_box.set_margin_start(8)

        # Simple colored bar as thermometer indicator
        indicator = Gtk.DrawingArea()
        indicator.set_size_request(6, 32)
        if icon_type == "nozzle_blue":
            indicator.connect("draw", self._draw_indicator, 0.2, 0.6, 1.0)
        else:
            indicator.connect("draw", self._draw_indicator, 1.0, 0.5, 0.2)
        icon_box.add(indicator)
        card.pack_start(icon_box, False, False, 0)

        # Temperature info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        info_box.set_valign(Gtk.Align.CENTER)

        # Label (Nozzle / Bed)
        name_label = Gtk.Label(label=label_text)
        name_label.get_style_context().add_class("temp-label")
        name_label.set_halign(Gtk.Align.START)
        info_box.add(name_label)

        # Temperature value
        temp_label = Gtk.Label(label="--°")
        temp_label.get_style_context().add_class("temp-value")
        temp_label.set_halign(Gtk.Align.START)
        info_box.add(temp_label)

        card.pack_start(info_box, True, True, 0)

        # State label
        state_label = Gtk.Label(label="Idle")
        state_label.get_style_context().add_class("temp-state")
        state_label.set_valign(Gtk.Align.CENTER)
        state_label.set_margin_end(12)
        card.pack_end(state_label, False, False, 0)

        # Store references for updates
        self.temp_labels[device] = {
            'temp': temp_label,
            'state': state_label,
        }

        return card

    def _draw_indicator(self, widget, ctx, r, g, b):
        """Draw a colored thermometer indicator bar."""
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        # Rounded rectangle
        radius = width / 2
        ctx.set_source_rgb(r, g, b)
        ctx.arc(width / 2, radius, radius, 3.14159, 0)
        ctx.arc(width / 2, height - radius, radius, 0, 3.14159)
        ctx.close_path()
        ctx.fill()
        return True

    def _update_temps(self):
        """Update temperature displays."""
        for device, labels in self.temp_labels.items():
            temp = self._printer.get_stat(device, "temperature")
            target = self._printer.get_stat(device, "target")

            if temp is not None:
                labels['temp'].set_label(f"{temp:.0f}°")
            else:
                labels['temp'].set_label("--°")

            # Determine state
            if target and target > 0:
                state = self._printer.state
                if state in ("printing", "paused"):
                    labels['state'].set_label("Printing")
                else:
                    labels['state'].set_label("Heating")
            else:
                labels['state'].set_label("Idle")

        return True

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        # Update temps from live data
        for device in self.temp_labels:
            if device in data:
                temp = self._printer.get_stat(device, "temperature")
                target = self._printer.get_stat(device, "target")
                if temp is not None:
                    self.temp_labels[device]['temp'].set_label(f"{temp:.0f}°")
                if target and target > 0:
                    state = self._printer.state
                    if state in ("printing", "paused"):
                        self.temp_labels[device]['state'].set_label("Printing")
                    else:
                        self.temp_labels[device]['state'].set_label("Heating")
                else:
                    self.temp_labels[device]['state'].set_label("Idle")
