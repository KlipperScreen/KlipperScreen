# -*- coding: utf-8 -*-
import json
import logging
import math
import os

import cairo
import requests

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango
from math import pi, sqrt, trunc
from statistics import median
from time import time
from ks_includes.screen_panel import ScreenPanel
from ks_includes.KlippyGtk import find_widget


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Job Status")
        super().__init__(screen, title)
        self.thumb_dialog = None
        self.grid = Gtk.Grid(column_homogeneous=True)
        self.pos_z = 0.0
        self.extrusion = 100
        self.speed_factor = 1.0
        self.speed = 100
        self.req_speed = 0
        self.oheight = 0.0
        self.current_extruder = None
        self.fila_section = pi * ((1.75 / 2) ** 2)
        self.filename_label = {"complete": "Filename"}
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
        self.toolchange_count = 0
        self._last_toolchange_tool = None
        self.toolchange_per_tool = {}
        self.tool_filament_per_tool = {}
        self._last_filament_used_total = 0.0
        self.toolchange_grid = None
        self.mm = _("mm")
        self.mms = _("mm/s")
        self.mms2 = _("mm/s2")
        self.mms3 = _("mm3/s")
        self.status_grid = None
        self.move_grid = None
        self.time_grid = None
        self.extrusion_grid = None

        data = ["pos_x", "pos_y", "pos_z", "time_left", "duration", "slicer_time", "file_time",
                "filament_time", "est_time", "speed_factor", "req_speed", "max_accel",
                "extrude_factor", "zoffset", "zoffset", "filament_used", "filament_total",
                "advance", "layer", "total_layers", "height", "flowrate"]
        for item in data:
            self.labels[item] = Gtk.Label(label="-", hexpand=True, vexpand=True)

        self.labels["left"] = Gtk.Label(_("Left:"))
        self.labels["elapsed"] = Gtk.Label(_("Elapsed:"))
        self.labels["total"] = Gtk.Label(_("Total:"))
        self.labels["slicer"] = Gtk.Label(_("Slicer:"))
        self.labels["file_tlbl"] = Gtk.Label(_("File:"))
        self.labels["fila_tlbl"] = Gtk.Label(_("Filament:"))
        self.labels["speed_lbl"] = Gtk.Label(_("Speed:"))
        self.labels["accel_lbl"] = Gtk.Label(_("Acceleration:"))
        self.labels["flow"] = Gtk.Label(_("Flow:"))
        self.labels["zoffset_lbl"] = Gtk.Label(_("Z offset:"))
        self.labels["fila_used_lbl"] = Gtk.Label(_("Filament used:"))
        self.labels["fila_total_lbl"] = Gtk.Label(_("Filament total:"))
        self.labels["pa_lbl"] = Gtk.Label(_("Pressure Advance:"))
        self.labels["flowrate_lbl"] = Gtk.Label(_("Flowrate:"))
        self.labels["height_lbl"] = Gtk.Label(_("Height:"))
        self.labels["layer_lbl"] = Gtk.Label(_("Layer:"))

        for fan in self._printer.get_fans():
            if fan == "fan":
                name = " "
            elif fan.startswith("fan_generic"):
                name = " ".join(fan.split(" ")[1:])[:1].upper() + ":"
                if name.startswith("_"):
                    continue
            else:
                continue
            self.fans[fan] = {"name": name, "speed": "-"}

        self.labels["file"] = Gtk.Label(label="Filename", hexpand=True)
        self.labels["file"].get_style_context().add_class("printing-filename")
        self.labels["lcdmessage"] = Gtk.Label(no_show_all=True)
        self.labels["lcdmessage"].get_style_context().add_class("printing-status")

        self._tool_cfg = self._load_toolchanger_settings()
        self.tool_widgets = []
        self.tool_spools = {}
        self._tool_css_provider = None
        self._progress_css_provider = None
        self._progress_bar_color = None

        for label in self.labels:
            self.labels[label].set_halign(Gtk.Align.START)
            self.labels[label].set_ellipsize(Pango.EllipsizeMode.END)

        self._init_tool_strip_css()

        # --- Row 0: progress bar + filename + preview button ---
        self.labels["progress_bar"] = Gtk.ProgressBar()
        self.labels["progress_bar"].set_fraction(0.0)
        self.labels["progress_bar"].set_show_text(True)
        self.labels["progress_bar"].set_text("0%")
        self.labels["progress_bar"].get_style_context().add_class("printing-progress-bar")
        self.labels["progress_bar"].set_hexpand(True)
        self.labels["progress_bar"].set_valign(Gtk.Align.CENTER)

        fi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        self.labels["file"].set_ellipsize(Pango.EllipsizeMode.END)
        fi_box.add(self.labels["file"])
        fi_box.add(self.labels["lcdmessage"])
        fi_box.add(self.labels["progress_bar"])

        self.labels["preview_btn"] = Gtk.Button(label=_("Preview"))
        self.labels["preview_btn"].set_size_request(72, 28)
        self.labels["preview_btn"].get_style_context().add_class("printing-info")
        self.labels["preview_btn"].connect("clicked", self.show_fullscreen_thumbnail)
        self.labels["preview_btn"].set_halign(Gtk.Align.END)
        self.labels["preview_btn"].set_valign(Gtk.Align.START)
        self.labels["preview_btn"].set_margin_end(6)
        self.labels["preview_btn"].set_margin_top(4)

        self.grid.attach(fi_box, 0, 0, 3, 1)
        self.grid.attach(self.labels["preview_btn"], 3, 0, 1, 1)

        # --- Rows 1-2: tool strip left | info grid right ---
        self.labels["info_grid"] = Gtk.Grid()
        self.labels["toolstrip_box"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.labels["toolstrip_box"].set_halign(Gtk.Align.CENTER)
        self.labels["toolstrip_box"].set_valign(Gtk.Align.CENTER)
        self._build_tool_strip()
        self.labels["info_grid"].attach(self.labels["toolstrip_box"], 0, 0, 1, 1)

        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        if self.current_extruder:
            diameter = float(self._printer.get_config_section(self.current_extruder)["filament_diameter"])
            self.fila_section = pi * ((diameter / 2) ** 2)
        self._reset_toolchange_counter(seed_tool=self.current_extruder)

        self.buttons = {}
        self.create_buttons()
        self.buttons["button_grid"] = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, vexpand=False)
        self.buttons["button_grid"].set_margin_top(4)
        self.grid.attach(self.buttons["button_grid"], 0, 3, 4, 1)

        self.create_status_grid()
        self.create_extrusion_grid()
        self.create_time_grid()
        self.create_toolchange_grid()
        self.create_move_grid()
        self.grid.attach(self.labels["info_grid"], 0, 1, 4, 2)
        self.switch_info(info=self.status_grid)

        GLib.timeout_add_seconds(10, self.update_spool_data)
        self._update_tool_strip_runtime()
        self.content.add(self.grid)

    # ------------------------------------------------------------------ CSS

    def _tool_strip_css_data(self):
        return b"""
.ks-toolcard {background:rgba(33,34,88,0.74);border-radius:12px;border:2px solid rgba(112,150,255,0.22);padding:4px;}
.ks-toolcard-active {background:rgba(24,34,102,0.88);border-radius:12px;border:3px solid rgba(85,235,255,0.95);padding:3px;}
.ks-tool-title {color:#bfe8ff;font-weight:800;font-size:13px;}
.ks-tool-temp {color:#ffffff;font-weight:900;font-size:15px;}
.ks-tool-mat {color:#d7e7ff;font-weight:700;font-size:11px;}
.ks-tool-badge-active {background:#11a84f;color:#ffffff;border-radius:6px;padding:1px 6px;font-size:9px;font-weight:800;}
.ks-tool-badge-parked {background:rgba(255,255,255,0.82);color:#6c6c6c;border-radius:6px;padding:1px 6px;font-size:9px;font-weight:800;}
"""

    def _progress_bar_css_data(self, color=None):
        color = self._normalize_tool_color(color or "#b71c1c")
        return f"""
.printing-progress-bar trough {{border-radius:6px;background:rgba(255,255,255,0.12);min-height:14px;}}
.printing-progress-bar progress {{border-radius:6px;background:{color};min-height:14px;}}
.printing-progress-bar text {{color:#ffffff;font-weight:800;font-size:12px;}}
""".encode("utf-8")

    def _set_progress_bar_color(self, color=None):
        color = self._normalize_tool_color(color or "#b71c1c")
        if self._progress_css_provider is None:
            return
        if color == self._progress_bar_color:
            return
        self._progress_css_provider.load_from_data(self._progress_bar_css_data(color))
        self._progress_bar_color = color

    def _init_tool_strip_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(self._tool_strip_css_data())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._tool_css_provider = provider

        progress_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), progress_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._progress_css_provider = progress_provider
        self._set_progress_bar_color("#b71c1c")

    # ------------------------------------------------------------------ Config helpers

    def _load_toolchanger_settings(self):
        cfg = {"num_tools": len(self._printer.get_tools()) if self._printer.get_tools() else 1}
        path = os.path.expanduser("~/.toolchanger_settings.json")
        if not os.path.exists(path):
            return cfg
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                cfg.update(raw)
        except Exception as exc:
            logging.debug(f"Unable to read toolchanger settings: {exc}")
        return cfg

    def _configured_tool_count(self):
        cfg_tools = self._tool_cfg.get("num_tools") if isinstance(self._tool_cfg, dict) else None
        try:
            cfg_tools = int(cfg_tools) if cfg_tools is not None else None
        except Exception:
            cfg_tools = None
        printer_tools = len(self._printer.get_tools()) if self._printer.get_tools() else 1
        if cfg_tools is None or cfg_tools < 1:
            return printer_tools
        return max(cfg_tools, printer_tools)

    def _tool_heater_name(self, idx):
        return "extruder" if idx == 0 else f"extruder{idx}"

    def _get_active_tool_index(self):
        active = self._printer.get_stat("toolhead", "extruder")
        if not active or active == "extruder":
            return 1
        try:
            return int(active.replace("extruder", "")) + 1
        except Exception:
            return 1

    def _normalize_tool_name(self, tool_name):
        if not tool_name:
            return None
        return str(tool_name).strip()

    def _toolchange_tool_label(self, tool_name):
        tool_name = self._normalize_tool_name(tool_name)
        if not tool_name:
            return "--"
        if tool_name == "extruder":
            return "T0"
        if tool_name.startswith("extruder"):
            suffix = tool_name.replace("extruder", "", 1)
            if suffix.isdigit():
                return f"T{int(suffix)}"
        return str(tool_name).upper()

    def _tool_index_from_name(self, tool_name):
        tool_name = self._normalize_tool_name(tool_name)
        if not tool_name or tool_name == "extruder":
            return 0
        if tool_name.startswith("extruder"):
            suffix = tool_name.replace("extruder", "", 1)
            if suffix.isdigit():
                return int(suffix)
        return 0

    def _active_tool_filament_color(self):
        active_tool = self.current_extruder or self._printer.get_stat("toolhead", "extruder")
        spool = self.tool_spools.get(self._tool_index_from_name(active_tool), {})
        color = spool.get("color")
        return self._normalize_tool_color(color) if color else "#b71c1c"

    def _update_status_bar_color(self):
        self._set_progress_bar_color(self._active_tool_filament_color())

    def _toolchange_tool_names(self):
        return [self._tool_heater_name(i) for i in range(self._configured_tool_count())]

    def _reset_toolchange_counter(self, seed_tool=None):
        self.toolchange_count = 0
        tool_names = self._toolchange_tool_names()
        self.toolchange_per_tool = {tool_name: 0 for tool_name in tool_names}
        self.tool_filament_per_tool = {tool_name: 0.0 for tool_name in tool_names}
        self._last_filament_used_total = 0.0
        if seed_tool is None:
            seed_tool = self._printer.get_stat("toolhead", "extruder")
        self._last_toolchange_tool = self._normalize_tool_name(seed_tool)
        if self._last_toolchange_tool is not None:
            self.toolchange_per_tool.setdefault(self._last_toolchange_tool, 0)
            self.tool_filament_per_tool.setdefault(self._last_toolchange_tool, 0.0)
        self._update_toolchange_display()

    def _format_tool_filament_length(self, length_mm):
        try:
            return f"{float(length_mm) / 1000:.1f} m"
        except Exception:
            return "0.0 m"

    def _update_toolchange_display(self):
        if "toolchanges" in getattr(self, "buttons", {}):
            self.buttons["toolchanges"].set_label(f"TC: {self.toolchange_count}")

        if "toolchange_total" in self.labels:
            self.labels["toolchange_total"].set_label(str(self.toolchange_count))

        if "toolchange_current" in self.labels:
            self.labels["toolchange_current"].set_label(
                self._toolchange_tool_label(self._last_toolchange_tool)
            )

        for tool_name, label in getattr(self, "toolchange_tool_labels", {}).items():
            label.set_label(str(self.toolchange_per_tool.get(tool_name, 0)))

        for tool_name, label in getattr(self, "toolchange_tool_filament_labels", {}).items():
            label.set_label(self._format_tool_filament_length(self.tool_filament_per_tool.get(tool_name, 0.0)))

    def _track_toolchange(self, tool_name, state=None):
        tool_name = self._normalize_tool_name(tool_name)
        if tool_name is None:
            return

        self.toolchange_per_tool.setdefault(tool_name, 0)
        state = state or self.state
        if state not in ["printing", "paused"]:
            self._last_toolchange_tool = tool_name
            self._update_toolchange_display()
            return

        if self._last_toolchange_tool is None:
            self._last_toolchange_tool = tool_name
        elif tool_name != self._last_toolchange_tool:
            self.toolchange_count += 1
            self.toolchange_per_tool[tool_name] = self.toolchange_per_tool.get(tool_name, 0) + 1
            self._last_toolchange_tool = tool_name

        self._update_toolchange_display()

    def _track_tool_filament_usage(self, total_filament_used, tool_name=None, state=None):
        try:
            total_filament_used = float(total_filament_used or 0.0)
        except Exception:
            return

        state = state or self.state
        tool_name = self._normalize_tool_name(tool_name or self.current_extruder or self._last_toolchange_tool)
        if tool_name is not None:
            self.tool_filament_per_tool.setdefault(tool_name, 0.0)

        if state not in ["printing", "paused"]:
            self._last_filament_used_total = max(0.0, total_filament_used)
            self._update_toolchange_display()
            return

        delta = total_filament_used - float(self._last_filament_used_total or 0.0)
        if delta < 0:
            self._last_filament_used_total = max(0.0, total_filament_used)
            self._update_toolchange_display()
            return

        if delta > 0 and tool_name is not None:
            self.tool_filament_per_tool[tool_name] = self.tool_filament_per_tool.get(tool_name, 0.0) + delta

        self._last_filament_used_total = max(0.0, total_filament_used)
        self._update_toolchange_display()

    def _get_active_tool_fan_percent(self):
        active = self._printer.get_stat("toolhead", "extruder")
        if not active or active == "extruder":
            fan_name = "fan_generic t0_partfan"
        else:
            try:
                tool_idx = int(str(active).replace("extruder", ""))
            except Exception:
                tool_idx = 0
            fan_name = f"fan_generic t{tool_idx}_partfan"

        try:
            speed = self._printer.get_fan_speed(fan_name)
            return float(speed or 0) * 100.0
        except Exception:
            return 0.0

    def _normalize_tool_color(self, color):
        color = str(color or "#4d6df3").strip().lstrip("#")
        if len(color) != 6:
            return "#4d6df3"
        try:
            int(color, 16)
        except ValueError:
            return "#4d6df3"
        return f"#{color.lower()}"

    def _spoolman_proxy_get(self, path):
        try:
            result = self._screen.apiclient.post_request(
                "server/spoolman/proxy",
                json={
                    "request_method": "GET",
                    "path": path,
                },
            )
            if isinstance(result, dict):
                return result.get("result")
        except Exception as exc:
            logging.debug(f"Spoolman proxy GET failed for {path}: {exc}")
        return None

    def _spoolman_get_spool(self, spool_id):
        if not spool_id:
            return None
        item = self._spoolman_proxy_get(f"/v1/spool/{int(spool_id)}")
        return item if isinstance(item, dict) else None

    # ------------------------------------------------------------------ Tool strip

    def _build_tool_strip(self):
        if "tool_strip" in self.labels:
            for child in self.labels["tool_strip"].get_children():
                self.labels["tool_strip"].remove(child)
        else:
            self.labels["tool_strip"] = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.labels["toolstrip_box"].pack_start(self.labels["tool_strip"], False, False, 0)

        self.tool_widgets = []
        n = self._configured_tool_count()
        card_w = max(100, min(140, (258 - (n - 1) * 6) // n))
        card_h = 158

        for i in range(n):
            frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            frame.set_size_request(card_w, card_h)
            frame.get_style_context().add_class("ks-toolcard")

            title = Gtk.Label(label=self._toolchange_tool_label(self._tool_heater_name(i)))
            title.get_style_context().add_class("ks-tool-title")
            title.set_halign(Gtk.Align.CENTER)

            badge = Gtk.Label(label=_("PARKED"))
            badge.get_style_context().add_class("ks-tool-badge-parked")
            badge.set_halign(Gtk.Align.CENTER)

            temp = Gtk.Label(label="--C")
            temp.get_style_context().add_class("ks-tool-temp")
            temp.set_halign(Gtk.Align.CENTER)

            ring_size = card_w - 20
            ring = Gtk.DrawingArea()
            ring.set_size_request(ring_size, ring_size)
            ring_wrap = Gtk.Box()
            ring_wrap.set_halign(Gtk.Align.CENTER)
            ring_wrap.pack_start(ring, False, False, 0)

            material = Gtk.Label(label="")
            material.get_style_context().add_class("ks-tool-mat")
            material.set_halign(Gtk.Align.CENTER)

            frame.pack_start(title, False, False, 0)
            frame.pack_start(badge, False, False, 0)
            frame.pack_start(temp, False, False, 0)
            frame.pack_start(ring_wrap, True, True, 2)
            frame.pack_start(material, False, False, 2)
            self.labels["tool_strip"].pack_start(frame, False, False, 0)

            state = {
                "frame": frame, "title": title, "badge": badge, "temp": temp,
                "ring": ring, "material": material, "index": i,
                "active": False, "temperature": 0.0, "target": 0.0,
                "color": "#4d6df3", "ratio": None,
            }
            ring.connect("draw", self._draw_tool_ring, state)
            self.tool_widgets.append(state)
        self.labels["tool_strip"].show_all()

    def _draw_tool_ring(self, widget, cr, state):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx, cy = w / 2.0, h / 2.0
        outer = min(w, h) * 0.44
        inner = outer * 0.52
        mid = (outer + inner) / 2.0
        full = math.pi * 2

        def hex_rgb(color):
            color = (color or "#4d6df3").lstrip("#")
            if len(color) != 6:
                color = "4d6df3"
            return tuple(int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

        r, g, b = hex_rgb(state.get("color"))
        cr.set_source_rgba(0.10, 0.14, 0.25, 0.85)
        cr.set_line_width(max(5.0, outer - inner))
        cr.arc(cx, cy, mid, 0, full)
        cr.stroke()

        cr.set_source_rgba(r, g, b, 0.96)
        cr.set_line_width(max(4.0, outer - inner - 3))
        ratio = state.get("ratio")
        if ratio is None:
            ratio = 0.16 if state.get("active") else 0.08
        ratio = max(0.0, min(1.0, float(ratio)))
        cr.arc(cx, cy, mid, -math.pi / 2.0, -math.pi / 2.0 + full * ratio)
        cr.stroke()

        cr.set_source_rgba(0.60, 0.82, 1.00, 0.22 if state.get("active") else 0.10)
        cr.set_line_width(2.0)
        cr.arc(cx, cy, outer + 3, 0, full)
        cr.stroke()

        cr.set_source_rgba(0.08, 0.11, 0.22, 0.92)
        cr.arc(cx, cy, inner - 1, 0, full)
        cr.fill()

        ratio_val = state.get("ratio")
        if ratio_val is not None:
            pct_text = f"{int(float(ratio_val) * 100)}%"
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(max(9, inner * 0.45))
            ext = cr.text_extents(pct_text)
            cr.move_to(cx - (ext[2] / 2 + ext[0]), cy - (ext[3] / 2 + ext[1]))
            cr.show_text(pct_text)
        return False

    def _update_tool_strip_runtime(self):
        active_name = self._printer.get_stat("toolhead", "extruder")
        for state in self.tool_widgets:
            idx = state["index"]
            heater = self._tool_heater_name(idx)
            temp = float(self._printer.get_stat(heater, "temperature") or 0)
            target = float(self._printer.get_stat(heater, "target") or 0)
            active = heater == active_name or (idx == 0 and active_name == "extruder")
            spool = self.tool_spools.get(idx, {})
            material = spool.get("material", "")
            color = self._normalize_tool_color(spool.get("color", "#4d6df3"))
            ratio = spool.get("ratio")
            state.update({"temperature": temp, "target": target, "active": active,
                          "color": color, "ratio": ratio})
            if target > 0:
                state["temp"].set_label(f"{temp:.0f}/{target:.0f}")
            else:
                state["temp"].set_label(f"{temp:.0f}C")
            state["material"].set_label(material[:12])
            state["title"].set_label(self._toolchange_tool_label(heater))
            badge_ctx = state["badge"].get_style_context()
            badge_ctx.remove_class("ks-tool-badge-active")
            badge_ctx.remove_class("ks-tool-badge-parked")
            frame_ctx = state["frame"].get_style_context()
            frame_ctx.remove_class("ks-toolcard")
            frame_ctx.remove_class("ks-toolcard-active")
            if active:
                state["badge"].set_label(_("ACTIVE"))
                badge_ctx.add_class("ks-tool-badge-active")
                frame_ctx.add_class("ks-toolcard-active")
            else:
                state["badge"].set_label(_("PARKED"))
                badge_ctx.add_class("ks-tool-badge-parked")
                frame_ctx.add_class("ks-toolcard")
            state["ring"].queue_draw()
        self._update_status_bar_color()

    # ------------------------------------------------------------------ Spoolman

    def _moonraker_tool_spool_ids(self):
        try:
            heater_names = [self._tool_heater_name(i) for i in range(self._configured_tool_count())]
            query = "&".join(heater_names + ["save_variables", "toolhead"])
            response = requests.get(f"http://localhost:7125/printer/objects/query?{query}", timeout=1.5)
            response.raise_for_status()
            status = response.json().get("result", {}).get("status", {})
            variables = status.get("save_variables", {}).get("variables", {}) or {}
        except Exception as exc:
            logging.debug(f"Moonraker spool-id refresh failed: {exc}")
            return {}
        mapping = {}
        for idx in range(self._configured_tool_count()):
            raw = variables.get(f"t{idx}__spool_id")
            try:
                mapping[idx] = int(raw) if raw not in (None, "", 0, "0") else 0
            except Exception:
                mapping[idx] = 0
        return mapping

    def update_spool_data(self):
        spool_ids = self._moonraker_tool_spool_ids()
        self.tool_spools = {}
        for tool_idx, spool_id in spool_ids.items():
            if not spool_id:
                continue
            spool = self._spoolman_get_spool(spool_id)
            if not spool:
                continue
            filament = spool.get("filament", {}) or {}
            material = str(filament.get("material", "") or "").upper()
            color_hex = self._normalize_tool_color(filament.get("color_hex"))
            total_weight = float(filament.get("weight", 0) or 0)
            used_weight = float(spool.get("used_weight", 0) or 0)
            ratio = None
            if total_weight > 0:
                ratio = max(0.0, min(1.0, 1.0 - (used_weight / total_weight)))
            self.tool_spools[int(tool_idx)] = {
                "material": material, "color": color_hex,
                "ratio": ratio, "spool_id": int(spool_id),
            }
        self._update_tool_strip_runtime()
        return True

    # ------------------------------------------------------------------ Status grid

    def create_status_grid(self, widget=None):
        buttons = {
            "speed": self._gtk.Button("speed+", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            "z": self._gtk.Button("home-z", _("Layer:") + " --/--", None, self.bts, Gtk.PositionType.LEFT, 1),
            "toolchanges": self._gtk.Button("extrude", "TC: 0", None, self.bts, Gtk.PositionType.LEFT, 1),
            "extrusion": self._gtk.Button("extrude", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            "fan": self._gtk.Button("fan", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            "elapsed": self._gtk.Button("clock", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
            "left": self._gtk.Button("hourglass", "-", None, self.bts, Gtk.PositionType.LEFT, 1),
        }
        for button in buttons:
            buttons[button].set_halign(Gtk.Align.START)
        buttons["fan"].connect("clicked", self.menu_item_clicked, {"panel": "fan"})
        buttons["toolchanges"].set_can_focus(False)
        buttons["toolchanges"].set_halign(Gtk.Align.START)
        buttons["toolchanges"].get_style_context().add_class("printing-info")
        self.buttons.update(buttons)

        self.buttons["extruder"] = {}
        for i, extruder in enumerate(self._printer.get_tools()):
            self.labels[extruder] = Gtk.Label(label="-")
            self.buttons["extruder"][extruder] = self._gtk.Button(
                f"extruder-{i}", "", None, self.bts, Gtk.PositionType.LEFT, 1)
            self.buttons["extruder"][extruder].set_label(self.labels[extruder].get_text())
            self.buttons["extruder"][extruder].connect(
                "clicked", self.menu_item_clicked, {"panel": "temperature", "extra": extruder})
            self.buttons["extruder"][extruder].set_halign(Gtk.Align.START)

        self.labels["temp_grid"] = Gtk.Grid()
        self.labels["temp_grid"].set_column_spacing(8)
        self.buttons["heater"] = {}
        top_row_heaters = []
        n = 0
        nlimit = 2 if self._screen.width <= 500 else 3

        for dev in self._printer.get_heaters():
            if dev.startswith("extruder"):
                self.buttons["heater"][dev] = self._gtk.Button(
                    "heater", "", None, self.bts, Gtk.PositionType.LEFT, 1)
                self.labels[dev] = Gtk.Label(label="-")
                self.buttons["heater"][dev].set_label(self.labels[dev].get_text())
                self.buttons["heater"][dev].connect(
                    "clicked", self.menu_item_clicked, {"panel": "temperature", "extra": dev})
                continue
            if n >= nlimit:
                break
            if dev == "heater_bed":
                self.buttons["heater"][dev] = self._gtk.Button(
                    "bed", "", None, self.bts, Gtk.PositionType.LEFT, 1)
            else:
                self.buttons["heater"][dev] = self._gtk.Button(
                    "heater", "", None, self.bts, Gtk.PositionType.LEFT, 1)
            self.labels[dev] = Gtk.Label(label="-")
            self.buttons["heater"][dev].set_label(self.labels[dev].get_text())
            self.buttons["heater"][dev].connect(
                "clicked", self.menu_item_clicked, {"panel": "temperature", "extra": dev})
            self.buttons["heater"][dev].set_halign(Gtk.Align.START)
            top_row_heaters.append((dev, self.buttons["heater"][dev]))
            n += 1

        # Keep the existing heater tiles on the row, but group Bed/Fan/Layer into a
        # compact strip so they sit visibly closer together.
        compact_col = 0
        for dev, button in top_row_heaters:
            if dev == "heater_bed":
                continue
            self.labels["temp_grid"].attach(button, compact_col, 0, 1, 1)
            compact_col += 1

        top_row_compact = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        top_row_compact.set_halign(Gtk.Align.START)
        if "heater_bed" in self.buttons["heater"]:
            top_row_compact.pack_start(self.buttons["heater"]["heater_bed"], False, False, 0)
        if self._printer.get_fans():
            top_row_compact.pack_start(self.buttons["fan"], False, False, 0)
        top_row_compact.pack_start(self.buttons["z"], False, False, 0)
        self.labels["temp_grid"].attach(top_row_compact, compact_col, 0, 1, 1)
        self._update_toolchange_display()

        szfe = Gtk.Grid(column_homogeneous=True)
        szfe.set_column_spacing(8)
        szfe.attach(self.buttons["toolchanges"], 0, 0, 1, 1)
        szfe.attach(self.buttons["speed"], 1, 0, 3, 1)
        if self._printer.get_tools():
            szfe.attach(self.buttons["extrusion"], 0, 1, 4, 1)

        info = Gtk.Grid(row_homogeneous=True)
        info.get_style_context().add_class("printing-info")
        info.set_margin_start(20)
        info.attach(self.labels["temp_grid"], 0, 0, 1, 1)
        info.attach(szfe, 0, 1, 1, 2)
        info.attach(self.buttons["left"], 0, 3, 1, 1)
        self.status_grid = info

    def create_extrusion_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color1", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")
        info = Gtk.Grid(hexpand=True, vexpand=True, halign=Gtk.Align.START)
        info.get_style_context().add_class("printing-info-secondary")
        info.set_margin_start(20)
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels["flow"], 1, 0, 1, 1)
        info.attach(self.labels["extrude_factor"], 2, 0, 1, 1)
        info.attach(self.labels["flowrate_lbl"], 1, 1, 1, 1)
        info.attach(self.labels["flowrate"], 2, 1, 1, 1)
        info.attach(self.labels["pa_lbl"], 1, 2, 1, 1)
        info.attach(self.labels["advance"], 2, 2, 1, 1)
        info.attach(self.labels["fila_used_lbl"], 1, 3, 1, 1)
        info.attach(self.labels["filament_used"], 2, 3, 1, 1)
        info.attach(self.labels["fila_total_lbl"], 1, 4, 1, 1)
        info.attach(self.labels["filament_total"], 2, 4, 1, 1)
        self.extrusion_grid = info
        self.buttons["extrusion"].connect("clicked", self.switch_info, self.extrusion_grid)

    def create_move_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color2", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")
        pos_box = Gtk.Box(spacing=5)
        pos_box.add(self.labels["pos_x"])
        pos_box.add(self.labels["pos_y"])
        pos_box.add(self.labels["pos_z"])
        info = Gtk.Grid(hexpand=True, vexpand=True, halign=Gtk.Align.START)
        info.get_style_context().add_class("printing-info-secondary")
        info.set_margin_start(20)
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels["speed_lbl"], 1, 0, 1, 1)
        info.attach(self.labels["req_speed"], 2, 0, 1, 1)
        info.attach(self.labels["accel_lbl"], 1, 1, 1, 1)
        info.attach(self.labels["max_accel"], 2, 1, 1, 1)
        info.attach(pos_box, 1, 2, 2, 1)
        info.attach(self.labels["zoffset_lbl"], 1, 3, 1, 1)
        info.attach(self.labels["zoffset"], 2, 3, 1, 1)
        info.attach(self.labels["height_lbl"], 1, 4, 1, 1)
        info.attach(self.labels["height"], 2, 4, 1, 1)
        info.attach(self.labels["layer_lbl"], 1, 5, 1, 1)
        info.attach(self.labels["layer"], 2, 5, 1, 1)
        self.move_grid = info
        self.buttons["z"].connect("clicked", self.switch_info, self.move_grid)
        self.buttons["speed"].connect("clicked", self.switch_info, self.move_grid)

    def create_time_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color3", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)
        info = Gtk.Grid()
        info.get_style_context().add_class("printing-info-secondary")
        info.set_margin_start(20)
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels["elapsed"], 1, 0, 1, 1)
        info.attach(self.labels["duration"], 2, 0, 1, 1)
        info.attach(self.labels["left"], 1, 1, 1, 1)
        info.attach(self.labels["time_left"], 2, 1, 1, 1)
        info.attach(self.labels["total"], 1, 2, 1, 1)
        info.attach(self.labels["est_time"], 2, 2, 1, 1)
        info.attach(self.labels["slicer"], 1, 3, 1, 1)
        info.attach(self.labels["slicer_time"], 2, 3, 1, 1)
        info.attach(self.labels["file_tlbl"], 1, 4, 1, 1)
        info.attach(self.labels["file_time"], 2, 4, 1, 1)
        info.attach(self.labels["fila_tlbl"], 1, 5, 1, 1)
        info.attach(self.labels["filament_time"], 2, 5, 1, 1)
        self.time_grid = info
        self.buttons["elapsed"].connect("clicked", self.switch_info, self.time_grid)
        self.buttons["left"].connect("clicked", self.switch_info, self.time_grid)

    def create_toolchange_grid(self, widget=None):
        goback = self._gtk.Button("back", None, "color4", self.bts, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.switch_info, self.status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")

        info = Gtk.Grid()
        info.get_style_context().add_class("printing-info-secondary")
        info.set_margin_start(20)

        tool_names = self._toolchange_tool_names()
        row_span = max(5, len(tool_names) + 3)
        info.attach(goback, 0, 0, 1, row_span)

        total_lbl = Gtk.Label(_("Total changes:"))
        total_lbl.set_halign(Gtk.Align.START)
        total_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.labels["toolchange_total_lbl"] = total_lbl

        total_val = Gtk.Label(label="0")
        total_val.set_halign(Gtk.Align.START)
        total_val.set_ellipsize(Pango.EllipsizeMode.END)
        self.labels["toolchange_total"] = total_val

        current_lbl = Gtk.Label(_("Current tool:"))
        current_lbl.set_halign(Gtk.Align.START)
        current_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.labels["toolchange_current_lbl"] = current_lbl

        current_val = Gtk.Label(label="--")
        current_val.set_halign(Gtk.Align.START)
        current_val.set_ellipsize(Pango.EllipsizeMode.END)
        self.labels["toolchange_current"] = current_val

        info.attach(self.labels["toolchange_total_lbl"], 1, 0, 1, 1)
        info.attach(self.labels["toolchange_total"], 2, 0, 1, 1)
        info.attach(self.labels["toolchange_current_lbl"], 1, 1, 1, 1)
        info.attach(self.labels["toolchange_current"], 2, 1, 1, 1)

        changes_hdr = Gtk.Label(label=_("Changes"))
        changes_hdr.set_halign(Gtk.Align.START)
        changes_hdr.set_ellipsize(Pango.EllipsizeMode.END)
        filament_hdr = Gtk.Label(label=_("Filament used"))
        filament_hdr.set_halign(Gtk.Align.START)
        filament_hdr.set_ellipsize(Pango.EllipsizeMode.END)
        self.labels["toolchange_changes_hdr"] = changes_hdr
        self.labels["toolchange_filament_hdr"] = filament_hdr
        info.attach(self.labels["toolchange_changes_hdr"], 2, 2, 1, 1)
        info.attach(self.labels["toolchange_filament_hdr"], 3, 2, 1, 1)

        self.toolchange_tool_labels = {}
        self.toolchange_tool_filament_labels = {}
        for row, tool_name in enumerate(tool_names, start=3):
            label = Gtk.Label(label=f"{self._toolchange_tool_label(tool_name)}:")
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            value = Gtk.Label(label="0")
            value.set_halign(Gtk.Align.START)
            value.set_ellipsize(Pango.EllipsizeMode.END)
            filament = Gtk.Label(label="0.0 m")
            filament.set_halign(Gtk.Align.START)
            filament.set_ellipsize(Pango.EllipsizeMode.END)

            self.labels[f"toolchange_tool_lbl_{tool_name}"] = label
            self.toolchange_tool_labels[tool_name] = value
            self.toolchange_tool_filament_labels[tool_name] = filament

            info.attach(label, 1, row, 1, 1)
            info.attach(value, 2, row, 1, 1)
            info.attach(filament, 3, row, 1, 1)

        self.toolchange_grid = info
        self.buttons["toolchanges"].connect("clicked", self.switch_info, self.toolchange_grid)
        self._update_toolchange_display()

    def switch_info(self, widget=None, info=None):
        if not info:
            logging.debug("No info to attach")
            return
        if self._screen.vertical_mode:
            self.labels["info_grid"].remove_row(1)
            self.labels["info_grid"].attach(info, 0, 1, 1, 1)
        else:
            self.labels["info_grid"].remove_column(1)
            self.labels["info_grid"].attach(info, 1, 0, 1, 1)
        self.labels["info_grid"].show_all()

    # ------------------------------------------------------------------ Progress bar

    def update_progress(self, progress: float):
        self.progress = progress
        pct = trunc(progress * 100)
        self.labels["progress_bar"].set_fraction(min(1.0, max(0.0, progress)))
        self.labels["progress_bar"].set_text(f"{pct}%")

    # ------------------------------------------------------------------ Lifecycle

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

    # ------------------------------------------------------------------ Buttons

    def create_buttons(self):
        self.buttons = {
            "cancel": self._gtk.Button("stop", _("Cancel"), "color2"),
            "control": self._gtk.Button("settings", _("Settings"), "color3"),
            "fine_tune": self._gtk.Button("fine-tune", _("Fine Tuning"), "color4"),
            "menu": self._gtk.Button("complete", _("Main Menu"), "color4"),
            "pause": self._gtk.Button("pause", _("Pause"), "color1"),
            "restart": self._gtk.Button("refresh", _("Restart"), "color3"),
            "resume": self._gtk.Button("resume", _("Resume"), "color1"),
            "save_offset_probe": self._gtk.Button("home-z", _("Save Z") + "\n" + "Probe", "color1"),
            "save_offset_endstop": self._gtk.Button("home-z", _("Save Z") + "\n" + "Endstop", "color2"),
        }
        self.buttons["cancel"].connect("clicked", self.cancel)
        self.buttons["control"].connect("clicked", self._screen._go_to_submenu, "")
        self.buttons["fine_tune"].connect("clicked", self.menu_item_clicked, {"panel": "fine_tune"})
        self.buttons["menu"].connect("clicked", self.close_panel)
        self.buttons["pause"].connect("clicked", self.pause)
        self.buttons["restart"].connect("clicked", self.restart)
        self.buttons["resume"].connect("clicked", self.resume)
        self.buttons["save_offset_probe"].connect("clicked", self.save_offset, "probe")
        self.buttons["save_offset_endstop"].connect("clicked", self.save_offset, "endstop")

    def save_offset(self, widget, device):
        sign = "+" if self.zoffset > 0 else "-"
        label = Gtk.Label(hexpand=True, vexpand=True, wrap=True)
        saved_z_offset = None
        msg = f"Apply {sign}{abs(self.zoffset)} offset to {device}?"
        if device == "probe":
            msg = _("Apply %s%.3f offset to Probe?") % (sign, abs(self.zoffset))
            if probe := self._printer.get_probe():
                saved_z_offset = probe["z_offset"]
        elif device == "endstop":
            msg = _("Apply %s%.3f offset to Endstop?") % (sign, abs(self.zoffset))
            if "stepper_z" in self._printer.get_config_section_list():
                saved_z_offset = self._printer.get_config_section("stepper_z")["position_endstop"]
            elif "stepper_a" in self._printer.get_config_section_list():
                saved_z_offset = self._printer.get_config_section("stepper_a")["position_endstop"]
        if saved_z_offset:
            msg += "\n\n" + _("Saved offset: %s") % saved_z_offset
        label.set_label(msg)
        buttons = [
            {"name": _("Apply"), "response": Gtk.ResponseType.APPLY, "style": "dialog-default"},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": "dialog-error"},
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
            self.disable_button("restart")
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
        self.disable_button("pause", "resume")
        self._screen._ws.klippy.print_pause()
        self._screen.show_all()

    def cancel(self, widget):
        buttons = [
            {"name": _("Cancel Print"), "response": Gtk.ResponseType.OK, "style": "dialog-error"},
            {"name": _("Go Back"), "response": Gtk.ResponseType.CANCEL, "style": "dialog-info"},
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
            self.enable_button("pause", "cancel")
            return
        logging.debug("Canceling print")
        self.set_state("cancelling")
        self.disable_button("pause", "resume", "cancel")
        self._screen._ws.klippy.print_cancel()

    def close_panel(self, widget=None):
        if self.can_close:
            logging.debug("Closing job_status panel")
            self._screen.state_ready(wait=False)

    def enable_button(self, *args):
        for arg in args:
            self.buttons[arg].set_sensitive(True)

    def disable_button(self, *args):
        for arg in args:
            self.buttons[arg].set_sensitive(False)

    def new_print(self):
        self._screen.screensaver.close()
        if "virtual_sdcard" in self._printer.data:
            logging.info("resetting progress")
            self._printer.data["virtual_sdcard"]["progress"] = 0
        self._reset_toolchange_counter()
        self.update_progress(0.0)
        self.set_state("printing")

    # ------------------------------------------------------------------ process_update

    def process_update(self, action, data):
        incoming_state = data.get("print_stats", {}).get("state", self.state) if isinstance(data, dict) else self.state
        if action == "notify_gcode_response":
            if "action:cancel" in data:
                self.set_state("cancelled")
            elif "action:paused" in data:
                self.set_state("paused")
            elif "action:resumed" in data:
                self.set_state("printing")
            return
        elif action == "notify_metadata_update" and data["filename"] == self.filename:
            self.get_file_metadata(response=True)
        elif action != "notify_status_update":
            return

        for x in self._printer.get_temp_devices():
            if x in data:
                self.update_temp(
                    x,
                    self._printer.get_stat(x, "temperature"),
                    self._printer.get_stat(x, "target"),
                    self._printer.get_stat(x, "power"),
                    digits=0,
                )
                if x in self.buttons["extruder"]:
                    self.buttons["extruder"][x].set_label(self.labels[x].get_text())
                elif x in self.buttons["heater"]:
                    self.buttons["heater"][x].set_label(self.labels[x].get_text())

        if "display_status" in data and "message" in data["display_status"]:
            if data["display_status"]["message"]:
                self.labels["lcdmessage"].set_label(f"{data['display_status']['message']}")
                self.labels["lcdmessage"].show()
            else:
                self.labels["lcdmessage"].hide()

        if "toolhead" in data:
            if "extruder" in data["toolhead"]:
                self.current_extruder = data["toolhead"]["extruder"]
                self._track_toolchange(self.current_extruder, state=incoming_state)
            if "max_accel" in data["toolhead"]:
                self.labels["max_accel"].set_label(f"{data['toolhead']['max_accel']:.0f} {self.mms2}")

        if "extruder" in data and "pressure_advance" in data["extruder"]:
            self.labels["advance"].set_label(f"{data['extruder']['pressure_advance']:.2f}")

        if "gcode_move" in data:
            if "gcode_position" in data["gcode_move"]:
                self.pos_z = round(float(data["gcode_move"]["gcode_position"][2]), 2)
            if "extrude_factor" in data["gcode_move"]:
                self.extrusion = round(float(data["gcode_move"]["extrude_factor"]) * 100)
                self.labels["extrude_factor"].set_label(f"{self.extrusion:3}%")
            if "speed_factor" in data["gcode_move"]:
                self.speed = round(float(data["gcode_move"]["speed_factor"]) * 100)
                self.speed_factor = float(data["gcode_move"]["speed_factor"])
                self.labels["speed_factor"].set_label(f"{self.speed:3}%")
            if "speed" in data["gcode_move"]:
                self.req_speed = round(float(data["gcode_move"]["speed"]) / 60 * self.speed_factor)
                self.labels["req_speed"].set_label(
                    f"{self.speed}% {self.vel:3.0f}/{self.req_speed:3.0f} "
                    f"{self.mms if self.vel < 1000 and self.req_speed < 1000 and self._screen.width > 500 else ''}"
                )
                self.buttons["speed"].set_label(self.labels["req_speed"].get_label())
            if "homing_origin" in data["gcode_move"]:
                self.zoffset = float(data["gcode_move"]["homing_origin"][2])
                self.labels["zoffset"].set_label(f"{self.zoffset:.3f} {self.mm}")

        if "motion_report" in data:
            if "live_position" in data["motion_report"]:
                self.labels["pos_x"].set_label(f"X: {data['motion_report']['live_position'][0]:6.2f}")
                self.labels["pos_y"].set_label(f"Y: {data['motion_report']['live_position'][1]:6.2f}")
                self.labels["pos_z"].set_label(f"Z: {data['motion_report']['live_position'][2]:6.2f}")
                pos = data["motion_report"]["live_position"]
                now = time()
                if self.prev_pos is not None:
                    interval = now - self.prev_pos[1]
                    evelocity = (pos[3] - self.prev_pos[0][3]) / interval
                    self.flowstore.append(self.fila_section * evelocity)
                self.prev_pos = [pos, now]
            if "live_velocity" in data["motion_report"]:
                self.vel = float(data["motion_report"]["live_velocity"])
                self.labels["req_speed"].set_label(
                    f"{self.speed}% {self.vel:3.0f}/{self.req_speed:3.0f} "
                    f"{self.mms if self.vel < 1000 and self.req_speed < 1000 and self._screen.width > 500 else ''}"
                )
                self.buttons["speed"].set_label(self.labels["req_speed"].get_label())
            if "live_extruder_velocity" in data["motion_report"]:
                self.flowstore.append(
                    self.fila_section * float(data["motion_report"]["live_extruder_velocity"]))

        if "heater_bed" in self.buttons.get("heater", {}):
            bed_temp = self._printer.get_stat("heater_bed", "temperature") or 0
            bed_target = self._printer.get_stat("heater_bed", "target") or 0
            self.buttons["heater"]["heater_bed"].set_label(f"{bed_temp:.0f}/{bed_target:.0f}")

        if "print_stats" in data:
            if "state" in data["print_stats"]:
                self.set_state(
                    data["print_stats"]["state"],
                    msg=data["print_stats"].get("message", ""),
                )
            if "filename" in data["print_stats"]:
                self.update_filename(data["print_stats"]["filename"])
            if "filament_used" in data["print_stats"]:
                filament_used_total = float(data["print_stats"]["filament_used"])
                self.labels["filament_used"].set_label(
                    f"{filament_used_total / 1000:.1f} m")
                self._track_tool_filament_usage(filament_used_total, state=incoming_state)
            if "info" in data["print_stats"]:
                if (data["print_stats"]["info"].get("total_layer") is not None):
                    self.labels["total_layers"].set_label(
                        f"{data['print_stats']['info']['total_layer']}")
                if (data["print_stats"]["info"].get("current_layer") is not None):
                    self.labels["layer"].set_label(
                        f"{data['print_stats']['info']['current_layer']} / "
                        f"{self.labels['total_layers'].get_text()}")
                    self.buttons["z"].set_label(
                        f"{_('Layer:')} {data['print_stats']['info']['current_layer']}"
                        f"/{self.labels['total_layers'].get_text()}")
                elif self.buttons.get("z"):
                    self.buttons["z"].set_label(f"{_('Layer:')} --/--")
            if "total_duration" in data["print_stats"]:
                self.labels["duration"].set_label(
                    self.format_time(data["print_stats"]["total_duration"]))
            if self.state in ["printing", "paused"]:
                self.update_time_left()

        active_fan = self._get_active_tool_fan_percent()
        self.buttons["fan"].set_label(f"{active_fan:.0f}%")

        self._update_tool_strip_runtime()

    # ------------------------------------------------------------------ Flow / time

    def update_flow(self):
        if not self.flowstore:
            self.flowstore.append(0)
        self.flowrate = median(self.flowstore)
        self.flowstore = []
        self.labels["flowrate"].set_label(f"{self.flowrate:.1f} {self.mms3}")
        self.buttons["extrusion"].set_label(f"{self.extrusion:3}% {self.flowrate:5.1f} {self.mms3}")
        return True

    def update_time_left(self):
        progress = (
            max(self._printer.get_stat("virtual_sdcard", "file_position")
                - self.file_metadata["gcode_start_byte"], 0)
            / (self.file_metadata["gcode_end_byte"] - self.file_metadata["gcode_start_byte"])
        ) if "gcode_start_byte" in self.file_metadata else self._printer.get_stat("virtual_sdcard", "progress")

        elapsed_label = f"{self.labels['elapsed'].get_text()}  {self.labels['duration'].get_text()}"
        self.buttons["elapsed"].set_label(elapsed_label)
        find_widget(self.buttons["elapsed"], Gtk.Label).set_ellipsize(Pango.EllipsizeMode.END)

        last_time = self.file_metadata.get("last_time", 0)
        slicer_time = self.file_metadata.get("estimated_time", 0)
        print_duration = float(self._printer.get_stat("print_stats", "print_duration"))
        if print_duration < 1:
            if last_time:
                print_duration = last_time * progress
            elif slicer_time:
                print_duration = slicer_time * progress
            else:
                print_duration = float(self._printer.get_stat("print_stats", "total_duration"))

        fila_used = float(self._printer.get_stat("print_stats", "filament_used"))
        if "filament_total" in self.file_metadata and self.file_metadata["filament_total"] >= fila_used > 0:
            filament_time = print_duration / (fila_used / self.file_metadata["filament_total"])
            self.labels["filament_time"].set_label(self.format_time(filament_time))
        else:
            filament_time = 0
        file_time = (print_duration / progress) if progress > 0 else 0
        if file_time:
            self.labels["file_time"].set_label(self.format_time(file_time))

        timeleft_type = self._config.get_config()["main"].get("print_estimate_method", "auto")
        if timeleft_type == "file":
            estimated = file_time
        elif timeleft_type == "filament":
            estimated = filament_time
        elif timeleft_type == "slicer":
            estimated = slicer_time
        else:
            estimated = self.estimate_time(
                progress, print_duration, file_time, filament_time, slicer_time, last_time)

        if estimated > 1:
            progress = min(max(print_duration / estimated, 0), 1)
            self.labels["est_time"].set_label(self.format_time(estimated))
            self.labels["time_left"].set_label(self.format_eta(estimated, print_duration))
            remaining_label = f"{self.labels['left'].get_text()}  {self.labels['time_left'].get_text()}"
            self.buttons["left"].set_label(remaining_label)
            find_widget(self.buttons["left"], Gtk.Label).set_ellipsize(Pango.EllipsizeMode.END)
        self.update_progress(progress)

    def estimate_time(self, progress, print_duration, file_time, filament_time, slicer_time, last_time):
        estimate_above = 0.3
        slicer_time /= sqrt(self.speed_factor)
        if progress <= estimate_above:
            return last_time or slicer_time or filament_time or file_time
        objects = self._printer.get_stat("exclude_object", "objects")
        excluded_objects = self._printer.get_stat("exclude_object", "excluded_objects")
        exclude_compensation = 3 * (len(excluded_objects) / len(objects)) if len(objects) > 0 else 0
        weight_last = 4.0 - exclude_compensation if print_duration < last_time else 0
        weight_slicer = (1.0 + estimate_above - progress - exclude_compensation
                         if print_duration < slicer_time else 0)
        weight_filament = min(progress - estimate_above, 0.33) if print_duration < filament_time else 0
        weight_file = progress - estimate_above
        total_weight = weight_last + weight_slicer + weight_filament + weight_file
        if total_weight == 0:
            return 0
        return (last_time * weight_last + slicer_time * weight_slicer
                + filament_time * weight_filament + file_time * weight_file) / total_weight

    # ------------------------------------------------------------------ State

    def set_state(self, state, msg=""):
        if state == "printing":
            self._screen.set_panel_title(
                _("Printing") if self._printer.extrudercount > 0 else _("Working"))
            if self.state not in ["printing", "paused"]:
                self._reset_toolchange_counter()
        elif state == "complete":
            self.update_progress(1)
            self._screen.set_panel_title(_("Complete"))
            self.buttons["left"].set_label("-")
            self._add_timeout(self._config.get_main_config().getint("job_complete_timeout", 0))
        elif state == "error":
            self._screen.set_panel_title(_("Error"))
            self._screen.show_popup_message(msg)
            self._add_timeout(self._config.get_main_config().getint("job_error_timeout", 0))
        elif state == "cancelling":
            self._screen.set_panel_title(_("Cancelling"))
        elif state == "cancelled" or (state == "standby" and self.state == "cancelled"):
            self._screen.set_panel_title(_("Cancelled"))
            self._add_timeout(self._config.get_main_config().getint("job_cancelled_timeout", 0))
        elif state == "paused":
            self._screen.set_panel_title(_("Paused"))
        elif state == "standby":
            self._screen.set_panel_title(_("Standby"))
        if self.state != state:
            logging.debug(f"Changing job_status state from '{self.state}' to '{state}'")
            self.state = state
            if self.thumb_dialog:
                self.close_dialog(self.thumb_dialog)
        self.show_buttons_for_state()

    def _add_timeout(self, timeout):
        self._screen.screensaver.close()
        if timeout != 0:
            GLib.timeout_add_seconds(timeout, self.close_panel)

    def show_buttons_for_state(self):
        self.buttons["button_grid"].remove_row(0)
        self.buttons["button_grid"].insert_row(0)
        if self.state == "printing":
            self.buttons["button_grid"].attach(self.buttons["pause"], 0, 0, 1, 1)
            self.buttons["button_grid"].attach(self.buttons["cancel"], 1, 0, 1, 1)
            self.buttons["button_grid"].attach(self.buttons["fine_tune"], 2, 0, 1, 1)
            self.buttons["button_grid"].attach(self.buttons["control"], 3, 0, 1, 1)
            self.enable_button("pause", "cancel")
            self.can_close = False
        elif self.state == "paused":
            self.buttons["button_grid"].attach(self.buttons["resume"], 0, 0, 1, 1)
            self.buttons["button_grid"].attach(self.buttons["cancel"], 1, 0, 1, 1)
            self.buttons["button_grid"].attach(self.buttons["fine_tune"], 2, 0, 1, 1)
            self.buttons["button_grid"].attach(self.buttons["control"], 3, 0, 1, 1)
            self.enable_button("resume", "cancel")
            self.can_close = False
        else:
            offset = self._printer.get_stat("gcode_move", "homing_origin")
            self.zoffset = float(offset[2]) if offset else 0
            if self.zoffset != 0:
                if "Z_OFFSET_APPLY_ENDSTOP" in self._printer.available_commands:
                    self.buttons["button_grid"].attach(self.buttons["save_offset_endstop"], 0, 0, 1, 1)
                else:
                    self.buttons["button_grid"].attach(Gtk.Label(), 0, 0, 1, 1)
                if "Z_OFFSET_APPLY_PROBE" in self._printer.available_commands:
                    self.buttons["button_grid"].attach(self.buttons["save_offset_probe"], 1, 0, 1, 1)
                else:
                    self.buttons["button_grid"].attach(Gtk.Label(), 1, 0, 1, 1)
            else:
                self.buttons["button_grid"].attach(Gtk.Label(), 0, 0, 1, 1)
                self.buttons["button_grid"].attach(Gtk.Label(), 1, 0, 1, 1)
            if self.filename:
                self.buttons["button_grid"].attach(self.buttons["restart"], 2, 0, 1, 1)
                self.enable_button("restart")
            else:
                self.disable_button("restart")
            if self.state != "cancelling":
                self.buttons["button_grid"].attach(self.buttons["menu"], 3, 0, 1, 1)
                self.can_close = True
        self.content.show_all()

    # ------------------------------------------------------------------ Thumbnail / filename

    def show_file_thumbnail(self):
        return

    def show_fullscreen_thumbnail(self, widget=None):
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
            "complete": self.labels["file"].get_label(),
            "current": self.labels["file"].get_label(),
        }
        self.get_file_metadata()

    def animate_label(self):
        if self.labels["file"].get_layout().is_ellipsized():
            self.filename_label["current"] = self.filename_label["current"][1:]
            self.labels["file"].set_label(self.filename_label["current"] + " " * 6)
        else:
            self.filename_label["current"] = self.filename_label["complete"]
            self.labels["file"].set_label(self.filename_label["complete"])
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
        if "estimated_time" in self.file_metadata:
            if self.timeleft_type == "slicer":
                self.labels["est_time"].set_label(self.format_time(self.file_metadata["estimated_time"]))
            self.labels["slicer_time"].set_label(self.format_time(self.file_metadata["estimated_time"]))
        if "object_height" in self.file_metadata:
            self.oheight = float(self.file_metadata["object_height"])
            self.labels["height"].set_label(f"{self.oheight:.2f} {self.mm}")
        if "filament_total" in self.file_metadata:
            self.labels["filament_total"].set_label(
                f"{float(self.file_metadata['filament_total']) / 1000:.1f} m")
        if "job_id" in self.file_metadata and self.file_metadata["job_id"]:
            history = self._screen.apiclient.send_request(
                f"server/history/job?uid={self.file_metadata['job_id']}")
            if history and history["job"]["status"] == "completed" and history["job"]["print_duration"]:
                self.file_metadata["last_time"] = history["job"]["print_duration"]
