# -*- coding: utf-8 -*-
import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango, GdkPixbuf
from math import pi, sqrt, trunc
from statistics import median
from time import time
from ks_includes.screen_panel import ScreenPanel
from ks_includes.KlippyGtk import find_widget


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Job Status")
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        eagle_path = os.path.join(styles_dir, "cro_eagle.png")

        self.thumb_dialog = None
        self.pos_z = 0.0
        self.extrusion = 100
        self.speed_factor = 1.0
        self.speed = 100
        self.req_speed = 0
        self.oheight = 0.0
        self.current_extruder = None
        self.fila_section = pi * ((1.75 / 2) ** 2)
        self.filename_label = {'complete': "Filename"}
        self.filename = ""
        self.prev_pos = None
        self.prev_gpos = None
        self.can_close = False
        self.flow_timeout = None
        self.animation_timeout = None
        self.file_metadata = self.fans = {}
        self.state = "standby"
        self.timeleft_type = "auto"
        self.progress = 0.0
        self.zoffset = 0.0
        self.flowrate = 0.0
        self.vel = 0.0
        self.flowstore = []
        self.mm = _("mm")
        self.mms = _("mm/s")
        self.mms2 = _("mm/s²")
        self.mms3 = _("mm³/s")
        self.temp_labels = {}
        self.buttons = {}

        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        if self.current_extruder:
            diameter = float(self._printer.get_config_section(self.current_extruder)['filament_diameter'])
            self.fila_section = pi * ((diameter / 2) ** 2)

        # ===== Main layout: horizontal split =====
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        self.content.add(main_box)

        # Top content area (thumbnail left, info right)
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top_box.set_hexpand(True)
        top_box.set_vexpand(True)
        top_box.set_margin_top(8)
        top_box.set_margin_start(12)
        top_box.set_margin_end(12)

        # Left: Thumbnail
        self.labels = {}
        self.labels['thumbnail'] = self._gtk.Button("file")
        self.labels['thumbnail'].connect("clicked", self.show_fullscreen_thumbnail)
        self.labels['thumbnail'].set_hexpand(True)
        self.labels['thumbnail'].set_vexpand(True)
        self.labels['thumbnail'].set_size_request(300, 260)
        thumb_box = Gtk.Box()
        thumb_box.set_hexpand(True)
        thumb_box.set_vexpand(True)
        thumb_box.add(self.labels['thumbnail'])
        top_box.pack_start(thumb_box, True, True, 0)

        # Right: Info panel
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        info_box.set_margin_end(4)

        # Eagle logo (top-right, small)
        if os.path.exists(eagle_path):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(eagle_path, 36, 36)
            eagle_img = Gtk.Image.new_from_pixbuf(pixbuf)
            eagle_img.set_halign(Gtk.Align.END)
            eagle_img.set_margin_bottom(2)
            info_box.pack_start(eagle_img, False, False, 0)

        # Filename
        self.labels['file'] = Gtk.Label(label="Filename")
        self.labels['file'].get_style_context().add_class("print-filename-label")
        self.labels['file'].set_halign(Gtk.Align.START)
        self.labels['file'].set_ellipsize(Pango.EllipsizeMode.END)
        self.labels['file'].set_max_width_chars(22)
        info_box.pack_start(self.labels['file'], False, False, 0)

        # Author
        self.labels['author'] = Gtk.Label(label="Author Name")
        self.labels['author'].get_style_context().add_class("print-author-label")
        self.labels['author'].set_halign(Gtk.Align.START)
        info_box.pack_start(self.labels['author'], False, False, 0)

        # Spacer
        info_box.pack_start(Gtk.Box(), False, False, 2)

        # Pause button
        pause_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pause_icon = Gtk.Label(label="⏸")
        pause_icon.set_margin_start(12)
        self.buttons['pause'] = Gtk.Button()
        self.buttons['pause'].get_style_context().add_class("control-button")
        pause_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pause_inner.pack_start(Gtk.Label(label="  ⏸"), False, False, 0)
        pause_lbl = Gtk.Label(label="PAUSE")
        pause_lbl.set_hexpand(True)
        pause_inner.pack_start(pause_lbl, True, True, 0)
        self.buttons['pause'].add(pause_inner)
        self.buttons['pause'].set_hexpand(True)
        self.buttons['pause'].connect("clicked", self.pause)
        info_box.pack_start(self.buttons['pause'], False, False, 0)

        # Resume button (hidden initially)
        self.buttons['resume'] = Gtk.Button()
        self.buttons['resume'].get_style_context().add_class("control-button")
        resume_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        resume_inner.pack_start(Gtk.Label(label="  ▶"), False, False, 0)
        resume_lbl = Gtk.Label(label="RESUME")
        resume_lbl.set_hexpand(True)
        resume_inner.pack_start(resume_lbl, True, True, 0)
        self.buttons['resume'].add(resume_inner)
        self.buttons['resume'].set_hexpand(True)
        self.buttons['resume'].connect("clicked", self.resume)
        self.buttons['resume'].set_no_show_all(True)
        info_box.pack_start(self.buttons['resume'], False, False, 0)

        # Cancel button
        self.buttons['cancel'] = Gtk.Button()
        self.buttons['cancel'].get_style_context().add_class("control-button")
        cancel_inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cancel_inner.pack_start(Gtk.Label(label="  ⊗"), False, False, 0)
        cancel_lbl = Gtk.Label(label="CANCEL")
        cancel_lbl.set_hexpand(True)
        cancel_inner.pack_start(cancel_lbl, True, True, 0)
        self.buttons['cancel'].add(cancel_inner)
        self.buttons['cancel'].set_hexpand(True)
        self.buttons['cancel'].connect("clicked", self.cancel)
        info_box.pack_start(self.buttons['cancel'], False, False, 0)

        # Spacer
        info_box.pack_start(Gtk.Box(), False, False, 2)

        # Progress section
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        # Percentage + time remaining row
        progress_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.labels['progress_text'] = Gtk.Label(label="0%")
        self.labels['progress_text'].get_style_context().add_class("print-progress-text")
        self.labels['progress_text'].set_halign(Gtk.Align.START)
        progress_top.pack_start(self.labels['progress_text'], False, False, 0)

        self.labels['time_left'] = Gtk.Label(label="--")
        self.labels['time_left'].get_style_context().add_class("print-time-text")
        self.labels['time_left'].set_halign(Gtk.Align.END)
        progress_top.pack_end(self.labels['time_left'], False, False, 0)
        progress_box.add(progress_top)

        # Progress bar (custom drawn)
        self.labels['darea'] = Gtk.DrawingArea()
        self.labels['darea'].set_size_request(-1, 8)
        self.labels['darea'].connect("draw", self.on_draw)
        progress_box.add(self.labels['darea'])

        # Layer count
        self.labels['layer'] = Gtk.Label(label="0/0")
        self.labels['layer'].get_style_context().add_class("print-layer-text")
        self.labels['layer'].set_halign(Gtk.Align.START)
        self.labels['total_layers'] = Gtk.Label(label="0")
        progress_box.add(self.labels['layer'])

        info_box.pack_start(progress_box, False, False, 0)

        top_box.pack_start(info_box, True, True, 0)
        main_box.pack_start(top_box, True, True, 0)

        # Bottom temperature bar
        temp_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        temp_bar.set_halign(Gtk.Align.CENTER)
        temp_bar.set_valign(Gtk.Align.END)
        temp_bar.set_margin_bottom(10)
        temp_bar.set_margin_start(20)
        temp_bar.set_margin_end(20)

        nozzle_card = self._create_temp_card("Nozzle", "nozzle_blue", "extruder")
        temp_bar.pack_start(nozzle_card, False, False, 0)

        bed_card = self._create_temp_card("Bed", "bed_orange", "heater_bed")
        temp_bar.pack_start(bed_card, False, False, 0)

        main_box.pack_end(temp_bar, False, False, 0)

        # Hidden labels for compatibility with process_update
        data_keys = ['pos_x', 'pos_y', 'pos_z', 'duration', 'slicer_time', 'file_time',
                     'filament_time', 'est_time', 'speed_factor', 'req_speed', 'max_accel',
                     'extrude_factor', 'zoffset', 'filament_used', 'filament_total',
                     'advance', 'height', 'flowrate']
        for item in data_keys:
            self.labels[item] = Gtk.Label(label="-")

        self.labels['left'] = Gtk.Label(_("Left:"))
        self.labels['elapsed'] = Gtk.Label(_("Elapsed:"))
        self.labels['lcdmessage'] = Gtk.Label(no_show_all=True)

        # Restart and menu buttons (for end-of-print state)
        self.buttons['restart'] = Gtk.Button(label="Restart")
        self.buttons['restart'].get_style_context().add_class("control-button")
        self.buttons['restart'].connect("clicked", self.restart)
        self.buttons['menu'] = Gtk.Button(label="Main Menu")
        self.buttons['menu'].get_style_context().add_class("control-button")
        self.buttons['menu'].connect("clicked", self.close_panel)

        # Compatibility buttons
        self.buttons['save_offset_probe'] = Gtk.Button(label="Save Z Probe")
        self.buttons['save_offset_probe'].connect("clicked", self.save_offset, "probe")
        self.buttons['save_offset_endstop'] = Gtk.Button(label="Save Z Endstop")
        self.buttons['save_offset_endstop'].connect("clicked", self.save_offset, "endstop")

    def _create_temp_card(self, label_text, icon_type, device):
        """Create a temperature display card."""
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card.get_style_context().add_class("temp-card")
        card.set_size_request(280, 56)

        # Thermometer indicator
        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        icon_box.set_valign(Gtk.Align.CENTER)
        icon_box.set_margin_start(8)

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

        name_label = Gtk.Label(label=label_text)
        name_label.get_style_context().add_class("temp-label")
        name_label.set_halign(Gtk.Align.START)
        info_box.add(name_label)

        temp_label = Gtk.Label(label="--°")
        temp_label.get_style_context().add_class("temp-value")
        temp_label.set_halign(Gtk.Align.START)
        info_box.add(temp_label)

        card.pack_start(info_box, True, True, 0)

        state_label = Gtk.Label(label="Printing")
        state_label.get_style_context().add_class("temp-state")
        state_label.set_valign(Gtk.Align.CENTER)
        state_label.set_margin_end(12)
        card.pack_end(state_label, False, False, 0)

        self.temp_labels[device] = {
            'temp': temp_label,
            'state': state_label,
        }

        return card

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

    def on_draw(self, da, ctx):
        width = da.get_allocated_width()
        height = da.get_allocated_height()
        radius = height / 2

        # Background
        ctx.set_source_rgb(0.2, 0.21, 0.25)
        self._rounded_rect(ctx, 0, 0, width, height, radius)
        ctx.fill()

        # Filled portion
        filled_width = max(width * self.progress, height)
        ctx.set_source_rgb(0.898, 0.224, 0.208)
        self._rounded_rect(ctx, 0, 0, filled_width, height, radius)
        ctx.fill()

        return True

    def _rounded_rect(self, ctx, x, y, w, h, r):
        from math import pi
        ctx.arc(x + r, y + r, r, pi, 1.5 * pi)
        ctx.arc(x + w - r, y + r, r, 1.5 * pi, 2 * pi)
        ctx.arc(x + w - r, y + h - r, r, 0, 0.5 * pi)
        ctx.arc(x + r, y + h - r, r, 0.5 * pi, pi)
        ctx.close_path()

    def activate(self):
        if self.flow_timeout is None:
            self.flow_timeout = GLib.timeout_add_seconds(2, self.update_flow)
        if self.animation_timeout is None:
            self.animation_timeout = GLib.timeout_add(500, self.animate_label)

    def deactivate(self):
        if self.flow_timeout is not None:
            GLib.source_remove(self.flow_timeout)
            self.flow_timeout = None
        if self.animation_timeout is not None:
            GLib.source_remove(self.animation_timeout)
            self.animation_timeout = None

    def save_offset(self, widget, device):
        sign = "+" if self.zoffset > 0 else "-"
        label = Gtk.Label(hexpand=True, vexpand=True, wrap=True)
        saved_z_offset = None
        msg = f"Apply {sign}{abs(self.zoffset)} offset to {device}?"
        if device == "probe":
            msg = _("Apply %s%.3f offset to Probe?") % (sign, abs(self.zoffset))
            if probe := self._printer.get_probe():
                saved_z_offset = probe['z_offset']
        elif device == "endstop":
            msg = _("Apply %s%.3f offset to Endstop?") % (sign, abs(self.zoffset))
            if 'stepper_z' in self._printer.get_config_section_list():
                saved_z_offset = self._printer.get_config_section('stepper_z')['position_endstop']
            elif 'stepper_a' in self._printer.get_config_section_list():
                saved_z_offset = self._printer.get_config_section('stepper_a')['position_endstop']
        if saved_z_offset:
            msg += "\n\n" + _("Saved offset: %s") % saved_z_offset
        label.set_label(msg)
        buttons = [
            {"name": _("Apply"), "response": Gtk.ResponseType.APPLY, "style": 'dialog-default'},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'}
        ]
        self._gtk.Dialog(_("Save Z"), buttons, label, self.save_confirm, device)

    def save_confirm(self, dialog, response_id, device):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.APPLY:
            if device == "probe":
                self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_PROBE")
            if device == "endstop":
                self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_ENDSTOP")
            self._screen._ws.klippy.gcode_script("SAVE_CONFIG")

    def restart(self, widget):
        if self.filename:
            self.buttons['restart'].set_sensitive(False)
            if self.state == "error":
                self._screen._ws.klippy.gcode_script("SDCARD_RESET_FILE")
            self._screen._ws.klippy.print_start(self.filename)
            logging.info(f"Starting print: {self.filename}")
            self.new_print()
        else:
            logging.info(f"Could not restart {self.filename}")

    def resume(self, widget):
        self._screen._ws.klippy.print_resume()
        self._screen.show_all()

    def pause(self, widget):
        self.buttons['pause'].set_sensitive(False)
        self.buttons['resume'].set_sensitive(False)
        self._screen._ws.klippy.print_pause()
        self._screen.show_all()

    def cancel(self, widget):
        buttons = [
            {"name": _("Cancel Print"), "response": Gtk.ResponseType.OK, "style": 'dialog-error'},
            {"name": _("Go Back"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-info'}
        ]
        if len(self._printer.get_stat("exclude_object", "objects")) > 1:
            buttons.insert(0, {"name": _("Exclude Object"), "response": Gtk.ResponseType.APPLY})
        label = Gtk.Label(hexpand=True, vexpand=True, wrap=True)
        label.set_markup(_("Are you sure you wish to cancel this print?"))
        self._gtk.Dialog(_("Cancel"), buttons, label, self.cancel_confirm)

    def cancel_confirm(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.APPLY:
            self.menu_item_clicked(None, {"panel": "exclude"})
            return
        if response_id == Gtk.ResponseType.CANCEL:
            self.buttons['pause'].set_sensitive(True)
            self.buttons['cancel'].set_sensitive(True)
            return
        logging.debug("Canceling print")
        self.set_state("cancelling")
        self.buttons['pause'].set_sensitive(False)
        self.buttons['resume'].set_sensitive(False)
        self.buttons['cancel'].set_sensitive(False)
        self._screen._ws.klippy.print_cancel()

    def close_panel(self, widget=None):
        if self.can_close:
            logging.debug("Closing job_status panel")
            self._screen.state_ready(wait=False)

    def enable_button(self, *args):
        for arg in args:
            if arg in self.buttons:
                self.buttons[arg].set_sensitive(True)

    def disable_button(self, *args):
        for arg in args:
            if arg in self.buttons:
                self.buttons[arg].set_sensitive(False)

    def new_print(self):
        self._screen.screensaver.close()
        if "virtual_sdcard" in self._printer.data:
            logging.info("resetting progress")
            self._printer.data["virtual_sdcard"]["progress"] = 0
        self.update_progress(0.0)
        self.set_state("printing")

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            if "action:cancel" in data:
                self.set_state("cancelled")
            elif "action:paused" in data:
                self.set_state("paused")
            elif "action:resumed" in data:
                self.set_state("printing")
            return
        elif action == "notify_metadata_update" and data['filename'] == self.filename:
            self.get_file_metadata(response=True)
        elif action != "notify_status_update":
            return

        # Update temperatures
        for x in self._printer.get_temp_devices():
            if x in data:
                temp = self._printer.get_stat(x, "temperature")
                target = self._printer.get_stat(x, "target")
                if x in self.temp_labels and temp is not None:
                    self.temp_labels[x]['temp'].set_label(f"{temp:.0f}°")
                    if self.state in ("printing", "paused"):
                        self.temp_labels[x]['state'].set_label("Printing")
                    elif target and target > 0:
                        self.temp_labels[x]['state'].set_label("Heating")
                    else:
                        self.temp_labels[x]['state'].set_label("Idle")

        if "display_status" in data and "message" in data["display_status"]:
            if data['display_status']['message']:
                self.labels['lcdmessage'].set_label(f"{data['display_status']['message']}")
                self.labels['lcdmessage'].show()
            else:
                self.labels['lcdmessage'].hide()

        if 'gcode_move' in data:
            if 'gcode_position' in data['gcode_move']:
                self.pos_z = round(float(data['gcode_move']['gcode_position'][2]), 2)
            if 'extrude_factor' in data['gcode_move']:
                self.extrusion = round(float(data['gcode_move']['extrude_factor']) * 100)
                self.labels['extrude_factor'].set_label(f"{self.extrusion:3}%")
            if 'speed_factor' in data['gcode_move']:
                self.speed = round(float(data['gcode_move']['speed_factor']) * 100)
                self.speed_factor = float(data['gcode_move']['speed_factor'])
                self.labels['speed_factor'].set_label(f"{self.speed:3}%")
            if 'homing_origin' in data['gcode_move']:
                self.zoffset = float(data['gcode_move']['homing_origin'][2])
                self.labels['zoffset'].set_label(f"{self.zoffset:.3f} {self.mm}")

        if 'motion_report' in data:
            if 'live_position' in data['motion_report']:
                pos = data["motion_report"]["live_position"]
                now = time()
                if self.prev_pos is not None:
                    interval = (now - self.prev_pos[1])
                    evelocity = (pos[3] - self.prev_pos[0][3]) / interval
                    self.flowstore.append(self.fila_section * evelocity)
                self.prev_pos = [pos, now]
            if 'live_extruder_velocity' in data['motion_report']:
                self.flowstore.append(self.fila_section * float(data["motion_report"]["live_extruder_velocity"]))

        if "print_stats" in data:
            if 'state' in data['print_stats']:
                self.set_state(
                    data["print_stats"]["state"],
                    msg=f'{data["print_stats"]["message"] if "message" in data["print_stats"] else ""}'
                )
            if 'filename' in data['print_stats']:
                self.update_filename(data['print_stats']["filename"])
            if 'filament_used' in data['print_stats']:
                self.labels['filament_used'].set_label(
                    f"{float(data['print_stats']['filament_used']) / 1000:.1f} m"
                )
            if 'info' in data["print_stats"]:
                if ('total_layer' in data['print_stats']['info']
                        and data["print_stats"]['info']['total_layer'] is not None):
                    self.labels['total_layers'].set_label(f"{data['print_stats']['info']['total_layer']}")
                if ('current_layer' in data['print_stats']['info']
                        and data['print_stats']['info']['current_layer'] is not None):
                    self.labels['layer'].set_label(
                        f"{data['print_stats']['info']['current_layer']}/"
                        f"{self.labels['total_layers'].get_text()}"
                    )
            if 'total_duration' in data["print_stats"]:
                self.labels["duration"].set_label(self.format_time(data["print_stats"]["total_duration"]))
            if self.state in ["printing", "paused"]:
                self.update_time_left()

    def update_flow(self):
        if not self.flowstore:
            self.flowstore.append(0)
        self.flowrate = median(self.flowstore)
        self.flowstore = []
        self.labels['flowrate'].set_label(f"{self.flowrate:.1f} {self.mms3}")
        return True

    def update_time_left(self):
        progress = (
            max(self._printer.get_stat('virtual_sdcard', 'file_position') - self.file_metadata.get('gcode_start_byte', 0), 0)
            / max((self.file_metadata.get('gcode_end_byte', 1) - self.file_metadata.get('gcode_start_byte', 0)), 1)
        ) if "gcode_start_byte" in self.file_metadata else self._printer.get_stat('virtual_sdcard', 'progress')

        last_time = self.file_metadata.get('last_time', 0)
        slicer_time = self.file_metadata.get('estimated_time', 0)
        print_duration = float(self._printer.get_stat('print_stats', 'print_duration'))
        if print_duration < 1:
            if last_time:
                print_duration = last_time * progress
            elif slicer_time:
                print_duration = slicer_time * progress
            else:
                print_duration = float(self._printer.get_stat('print_stats', 'total_duration'))

        fila_used = float(self._printer.get_stat('print_stats', 'filament_used'))
        filament_time = 0
        if 'filament_total' in self.file_metadata and self.file_metadata['filament_total'] >= fila_used > 0:
            filament_time = (print_duration / (fila_used / self.file_metadata['filament_total']))
        file_time = (print_duration / progress) if progress > 0 else 0

        estimated = 0
        timeleft_type = self._config.get_config()['main'].get('print_estimate_method', 'auto')
        if timeleft_type == "file":
            estimated = file_time
        elif timeleft_type == "filament":
            estimated = filament_time
        elif timeleft_type == "slicer":
            estimated = slicer_time
        else:
            estimated = self.estimate_time(
                progress, print_duration, file_time, filament_time, slicer_time, last_time
            )
        if estimated > 1:
            progress = min(max(print_duration / estimated, 0), 1)
            remaining = estimated - print_duration
            if remaining > 0:
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                if hours > 0:
                    self.labels['time_left'].set_label(f"{hours}h {minutes:02d}m")
                else:
                    self.labels['time_left'].set_label(f"{minutes}m")
            else:
                self.labels['time_left'].set_label("--")
        self.update_progress(progress)

    def estimate_time(self, progress, print_duration, file_time, filament_time, slicer_time, last_time):
        estimate_above = 0.3
        slicer_time /= sqrt(self.speed_factor) if self.speed_factor > 0 else 1
        if progress <= estimate_above:
            return last_time or slicer_time or filament_time or file_time
        objects = self._printer.get_stat("exclude_object", "objects")
        excluded_objects = self._printer.get_stat("exclude_object", "excluded_objects")
        exclude_compensation = 3 * (len(excluded_objects) / len(objects)) if len(objects) > 0 else 0
        weight_last = 4.0 - exclude_compensation if print_duration < last_time else 0
        weight_slicer = 1.0 + estimate_above - progress - exclude_compensation if print_duration < slicer_time else 0
        weight_filament = min(progress - estimate_above, 0.33) if print_duration < filament_time else 0
        weight_file = progress - estimate_above
        total_weight = weight_last + weight_slicer + weight_filament + weight_file
        if total_weight == 0:
            return 0
        return (
            (last_time * weight_last + slicer_time * weight_slicer
             + filament_time * weight_filament + file_time * weight_file)
            / total_weight
        )

    def update_progress(self, progress: float):
        self.progress = progress
        self.labels['progress_text'].set_label(f"{trunc(progress * 100)}%")
        self.labels['darea'].queue_draw()

    def set_state(self, state, msg=""):
        if state == "printing":
            self.buttons['pause'].show()
            self.buttons['resume'].hide()
            self.buttons['cancel'].show()
            self.buttons['pause'].set_sensitive(True)
            self.buttons['cancel'].set_sensitive(True)
            self.can_close = False
        elif state == "paused":
            self.buttons['pause'].hide()
            self.buttons['resume'].show()
            self.buttons['resume'].set_sensitive(True)
            self.buttons['cancel'].show()
            self.buttons['cancel'].set_sensitive(True)
            self.can_close = False
        elif state == "complete":
            self.update_progress(1)
            self.can_close = True
            self._add_timeout(self._config.get_main_config().getint("job_complete_timeout", 0))
        elif state == "error":
            self._screen.show_popup_message(msg)
            self.can_close = True
            self._add_timeout(self._config.get_main_config().getint("job_error_timeout", 0))
        elif state == "cancelling":
            self.can_close = False
        elif state == "cancelled" or (state == "standby" and self.state == "cancelled"):
            self.can_close = True
            self._add_timeout(self._config.get_main_config().getint("job_cancelled_timeout", 0))

        if self.state != state:
            logging.debug(f"Changing job_status state from '{self.state}' to '{state}'")
            self.state = state
            if self.thumb_dialog:
                self.close_dialog(self.thumb_dialog)
        self.content.show_all()
        # Re-hide resume if printing
        if self.state == "printing":
            self.buttons['resume'].hide()
        elif self.state == "paused":
            self.buttons['pause'].hide()

    def _add_timeout(self, timeout):
        self._screen.screensaver.close()
        if timeout != 0:
            GLib.timeout_add_seconds(timeout, self.close_panel)

    def show_file_thumbnail(self):
        max_width = 300
        max_height = 260
        width = max(self.labels['thumbnail'].get_allocated_width(), max_width)
        height = max(self.labels['thumbnail'].get_allocated_height(), max_height)
        if width <= 1 or height <= 1:
            width = max_width
            height = max_height
        pixbuf = self.get_file_image(self.filename, width, height)
        if pixbuf is None:
            return
        if image := find_widget(self.labels['thumbnail'], Gtk.Image):
            image.set_from_pixbuf(pixbuf)

    def show_fullscreen_thumbnail(self, widget):
        pixbuf = self.get_file_image(self.filename, self._screen.width * .9, self._screen.height * .75)
        if pixbuf is None:
            return
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        image.set_vexpand(True)
        self.thumb_dialog = self._gtk.Dialog(self.filename, None, image, self.close_dialog)

    def close_dialog(self, dialog=None, response_id=None):
        self._gtk.remove_dialog(dialog)
        self.thumb_dialog = None

    def update_filename(self, filename):
        if not filename or filename == self.filename:
            return
        self.filename = filename
        logging.debug(f"Updating filename to {filename}")
        self.labels["file"].set_label(os.path.splitext(self.filename)[0])
        self.filename_label = {
            "complete": self.labels['file'].get_label(),
            "current": self.labels['file'].get_label(),
        }
        self.get_file_metadata()

    def animate_label(self):
        if self.labels['file'].get_layout().is_ellipsized():
            self.filename_label['current'] = self.filename_label['current'][1:]
            self.labels['file'].set_label(self.filename_label['current'] + " " * 6)
        else:
            self.filename_label['current'] = self.filename_label['complete']
            self.labels['file'].set_label(self.filename_label['complete'])
        return True

    def get_file_metadata(self, response=False):
        if self._files.file_metadata_exists(self.filename):
            self._update_file_metadata()
        elif not response:
            logging.debug("Cannot find file metadata. Listening for updated metadata")
            self._files.request_metadata(self.filename)
        else:
            logging.debug("Cannot load file metadata")
        self.show_file_thumbnail()

    def _update_file_metadata(self):
        self.file_metadata = self._files.get_file_info(self.filename)
        logging.info(f"Update Metadata. File: {self.filename} Size: {self.file_metadata['size']}")
        if "object_height" in self.file_metadata:
            self.oheight = float(self.file_metadata['object_height'])
        if "job_id" in self.file_metadata and self.file_metadata['job_id']:
            history = self._screen.apiclient.send_request(f"server/history/job?uid={self.file_metadata['job_id']}")
            if history and history['job']['status'] == "completed" and history['job']['print_duration']:
                self.file_metadata["last_time"] = history['job']['print_duration']
