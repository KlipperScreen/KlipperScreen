#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ToolchangerPanel rewritten from scratch with a cleaner architecture, safer polling,
and stricter separation between bg I/O and GTK UI updates.

Updated to use KlipperScreen/Moonraker's shared Spoolman proxy instead of a
panel-local Spoolman URL. This removes the broken custom Spoolman IP handling
and reuses the same configured Spoolman connection that the built-in
KlipperScreen Spoolman panel uses.

Also updated to auto-detect tool count from Moonraker's toolchanger status
(tool_numbers / tool_names) and remove the manual tool count setting.
"""

from __future__ import annotations

import cairo
import gi
import json
import math
import os
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import requests

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk


MOONRAKER = "http://localhost:7125"
CONFIG_PATH = os.path.expanduser("~/.toolchanger_settings.json")
POLL_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_MOONRAKER = 1.0


# -----------------------------------------------------------------------------
# Theme helpers
# -----------------------------------------------------------------------------

def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_hex(color: str, fallback: str = "#333b54") -> str:
    if not color:
        return fallback
    raw = color.strip().lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        int(raw, 16)
    except ValueError:
        return fallback
    return f"#{raw.lower()}"


def hex_to_rgb01(color: str) -> tuple[float, float, float]:
    color = normalize_hex(color)
    raw = color.lstrip("#")
    return (
        int(raw[0:2], 16) / 255.0,
        int(raw[2:4], 16) / 255.0,
        int(raw[4:6], 16) / 255.0,
    )


def rgb01_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        int(clamp01(r) * 255),
        int(clamp01(g) * 255),
        int(clamp01(b) * 255),
    )


def adjust_color(color: str, factor: float) -> str:
    r, g, b = hex_to_rgb01(color)
    return rgb01_to_hex(r * factor, g * factor, b * factor)


def mix_colors(a: str, b: str, t: float) -> str:
    t = clamp01(t)
    ar, ag, ab = hex_to_rgb01(a)
    br, bg, bb = hex_to_rgb01(b)
    return rgb01_to_hex(
        ar + (br - ar) * t,
        ag + (bg - ag) * t,
        ab + (bb - ab) * t,
    )


def luminance(color: str) -> float:
    r, g, b = hex_to_rgb01(color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def hex_to_gdk(color: str) -> Gdk.RGBA:
    r, g, b = hex_to_rgb01(color)
    return Gdk.RGBA(r, g, b, 1.0)


def gdk_to_hex(rgba: Gdk.RGBA) -> str:
    return rgb01_to_hex(rgba.red, rgba.green, rgba.blue)


BASE_THEMES: Dict[str, Dict[str, str]] = {
    "Ocean": {
        "bg": "#1a2035",
        "card": "#242d48",
        "accent": "#00d4ff",
        "text": "#ffffff",
        "bar_bg": "#151c30",
        "btn_bg": "#252f4a",
    },
    "Ember": {
        "bg": "#1f1208",
        "card": "#2e1a0a",
        "accent": "#ff7722",
        "text": "#ffe8d0",
        "bar_bg": "#120c04",
        "btn_bg": "#2a1808",
    },
    "Stealth": {
        "bg": "#0d0d0d",
        "card": "#1a1a1a",
        "accent": "#cccccc",
        "text": "#ffffff",
        "bar_bg": "#080808",
        "btn_bg": "#1a1a1a",
    },
    "Neon": {
        "bg": "#0a001a",
        "card": "#130028",
        "accent": "#cc00ff",
        "text": "#f0d0ff",
        "bar_bg": "#06000e",
        "btn_bg": "#130028",
    },
    "Crimson": {
        "bg": "#1a0510",
        "card": "#2a0a18",
        "accent": "#ff2255",
        "text": "#ffd0da",
        "bar_bg": "#0e0208",
        "btn_bg": "#200810",
    },
    "Arctic": {
        "bg": "#0a1520",
        "card": "#0f2030",
        "accent": "#44ddaa",
        "text": "#d0fff0",
        "bar_bg": "#060f18",
        "btn_bg": "#0d1e2e",
    },
    "Sunset": {
        "bg": "#2a0f0f",
        "card": "#3a1a1a",
        "accent": "#ff8844",
        "text": "#ffe6d5",
        "bar_bg": "#1a0808",
        "btn_bg": "#3a1a1a",
    },
    "Forest": {
        "bg": "#0e1a12",
        "card": "#16261c",
        "accent": "#22cc66",
        "text": "#d8ffe8",
        "bar_bg": "#08120c",
        "btn_bg": "#16261c",
    },
    "Midnight Blue": {
        "bg": "#050a18",
        "card": "#0c1428",
        "accent": "#4488ff",
        "text": "#d6e4ff",
        "bar_bg": "#030612",
        "btn_bg": "#0c1428",
    },
}


def derive_theme_fields(base: Dict[str, str]) -> Dict[str, str]:
    bg = normalize_hex(base["bg"])
    card = normalize_hex(base["card"])
    accent = normalize_hex(base["accent"])
    text = normalize_hex(base["text"])
    bar_bg = normalize_hex(base["bar_bg"])
    btn_bg = normalize_hex(base["btn_bg"])

    return {
        "bg": bg,
        "card": card,
        "card_border": mix_colors(card, accent, 0.28),
        "accent": accent,
        "accent_dark": adjust_color(accent, 0.78),
        "btn_bg": btn_bg,
        "btn_bg2": mix_colors(btn_bg, accent, 0.12),
        "btn_border": mix_colors(btn_bg, accent, 0.35),
        "text": text,
        "bar_bg": bar_bg,
        "warn": "#ffb020",
        "danger": "#ff4d4f",
        "ok": "#12d67a",
        "muted": mix_colors(text, bg, 0.55),
    }


THEMES = {name: derive_theme_fields(values) for name, values in BASE_THEMES.items()}


def make_css(theme: Dict[str, str]) -> bytes:
    accent = theme["accent"]
    btn_text = "#001820" if luminance(accent) > 0.45 else theme["text"]

    css = f"""
.tc-root {{ background-color: {theme['bg']}; }}
.tc-card {{ background-color: {theme['card']}; border-radius: 14px; border: 1px solid {theme['card_border']}; }}
.tc-card-active {{ background-color: {theme['card']}; border-radius: 14px; border: 3px solid {accent}; }}
.tc-tool-label {{ color: {accent}; font-size: 18px; font-weight: 800; }}
.tc-mat-label {{ color: {theme['text']}; font-size: 16px; font-weight: 800; }}
.tc-mat-label-empty {{ color: {theme['text']}; font-size: 16px; font-weight: 800; }}
.tc-temp-label {{ color: {theme['text']}; font-size: 26px; font-weight: 800; padding: 4px; }}
.tc-bottom-bar {{ background-color: {theme['bar_bg']}; border-top: 1px solid {theme['card_border']}; }}
.tc-btn-global {{ background: {theme['btn_bg']}; color: {theme['text']}; border-radius: 8px; font-size: 12px; font-weight: 700; border: 1px solid {theme['btn_border']}; }}
.tc-btn-select {{ background: {accent}; color: {btn_text}; border-radius: 8px; font-size: 12px; font-weight: 800; border: 1px solid {accent}; }}
.tc-badge-active {{ background-color: #003a20; color: #00ff88; border-radius: 6px; font-size: 11px; font-weight: 800; padding: 2px 8px; border: 1px solid #00cc66; }}
.tc-badge-heating {{ background-color: #3f2700; color: #ffbf40; border-radius: 6px; font-size: 11px; font-weight: 800; padding: 2px 8px; border: 1px solid #ffb020; }}
.tc-badge-parked {{ background-color: #e0e0e0; color: #555555; border-radius: 6px; font-size: 11px; font-weight: 800; padding: 2px 8px; border: 1px solid #c0c0c0; }}
.tc-badge-error {{ background-color: #3a0a0a; color: #ff4444; border-radius: 6px; font-size: 11px; font-weight: 800; padding: 2px 8px; border: 1px solid #aa2222; }}
.tc-badge-changing {{ background-color: #002a4a; color: #44c8ff; border-radius: 6px; font-size: 11px; font-weight: 800; padding: 2px 8px; border: 1px solid #44c8ff; }}
.tc-popup {{ background-color: {theme['card']}; border: 2px solid {accent}; border-radius: 15px; }}
"""
    return css.encode("utf-8")


# -----------------------------------------------------------------------------
# State models
# -----------------------------------------------------------------------------

@dataclass
class ToolState:
    index: int
    heater_name: str
    material: str = "EMPTY"
    color_hex: str = "#333b54"
    remaining_ratio: float = -1.0
    temperature: float = 0.0
    target: float = 0.0
    active: bool = False
    spool_id: Optional[int] = None
    reachable: bool = True
    spool_error: bool = False
    ktc_state: str = "unknown"

    @property
    def display_title(self) -> str:
        return f"TOOL {self.index + 1}"

    @property
    def is_heating(self) -> bool:
        return self.target > 0 and self.temperature + 5 < self.target

    @property
    def status_label(self) -> str:
        if not self.reachable:
            return "OFFLINE"
        if self.spool_error:
            return "ERROR"
        if self.ktc_state == "error":
            return "ERROR"
        if self.ktc_state == "active":
            return "ACTIVE"
        if self.ktc_state == "changing":
            return "CHANGING"
        if self.ktc_state == "docked":
            return "PARKED"
        if self.is_heating:
            return "HEATING"
        return "UNKNOWN"

    @property
    def status_css(self) -> str:
        if not self.reachable or self.spool_error:
            return "tc-badge-error"
        if self.ktc_state == "error":
            return "tc-badge-error"
        if self.ktc_state == "active":
            return "tc-badge-active"
        if self.ktc_state == "changing":
            return "tc-badge-changing"
        if self.ktc_state == "docked":
            return "tc-badge-parked"
        if self.is_heating:
            return "tc-badge-heating"
        return "tc-badge-parked"


@dataclass
class CardWidgets:
    frame: Gtk.Box
    badge: Gtk.Label
    temp: Gtk.Label
    mat: Gtk.Label
    spool_area: Gtk.DrawingArea


@dataclass
class RuntimeSnapshot:
    tools: List[ToolState]
    moonraker_ok: bool = True


# -----------------------------------------------------------------------------
# Utility UI builders
# -----------------------------------------------------------------------------

def popup_window(parent: Gtk.Window) -> Gtk.Window:
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_transient_for(parent)
    win.set_modal(True)
    win.set_decorated(False)
    win.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
    return win


def button(label: str, css_class: str, callback: Callable[..., Any]) -> Gtk.Button:
    b = Gtk.Button(label=label)
    b.get_style_context().add_class(css_class)
    b.connect("clicked", callback)
    return b


def box(orientation: Gtk.Orientation = Gtk.Orientation.VERTICAL, spacing: int = 0) -> Gtk.Box:
    return Gtk.Box(orientation=orientation, spacing=spacing)


# -----------------------------------------------------------------------------
# Main panel
# -----------------------------------------------------------------------------

class ToolchangerPanel:
    def __init__(self, screen: Gtk.Window, title: str):
        self._screen = screen
        self.title = "Tool Changer"
        self.menu = [title]

        self._session = requests.Session()
        self._poll_stop = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._command_queue: "queue.Queue[str]" = queue.Queue()
        self._command_thread: Optional[threading.Thread] = None
        self._active_popup: Optional[Gtk.Window] = None

        self._css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        config = self._load_config()
        self.num_tools = 2
        self._theme_name = config.get("theme", "Ocean")
        self._custom = config.get("custom")
        self._theme = self._resolve_theme()
        self._apply_theme()

        self._tool_states: List[ToolState] = []
        self._card_widgets: Dict[int, CardWidgets] = {}

        self.content = self._build_root()
        self._rebuild_cards()
        self.content.show_all()

        self._start_command_worker()
        self._start_polling_worker()

    # ------------------------------------------------------------------
    # Configuration / theme
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, Any]:
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
                    return json.load(handle)
        except Exception:
            pass
        return {}

    def _save_config(self) -> None:
        payload = {
            "theme": self._theme_name,
            "custom": self._custom,
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except Exception:
            pass

    def _resolve_theme(self) -> Dict[str, str]:
        if self._theme_name == "Custom" and isinstance(self._custom, dict):
            try:
                return derive_theme_fields(self._custom)
            except Exception:
                return THEMES["Ocean"]
        return THEMES.get(self._theme_name, THEMES["Ocean"])

    def _apply_theme(self) -> None:
        self._theme = self._resolve_theme()
        self._css_provider.load_from_data(make_css(self._theme))

    # ------------------------------------------------------------------
    # Root layout
    # ------------------------------------------------------------------

    def _build_root(self) -> Gtk.Box:
        root = box(spacing=0)
        root.get_style_context().add_class("tc-root")
        root.set_size_request(800, 480)
        root.set_vexpand(True)

        wrap = box(Gtk.Orientation.HORIZONTAL, 0)
        wrap.set_halign(Gtk.Align.CENTER)
        wrap.set_valign(Gtk.Align.CENTER)
        wrap.set_vexpand(True)

        self.card_area = box(Gtk.Orientation.HORIZONTAL, 15)
        wrap.add(self.card_area)
        root.pack_start(wrap, True, True, 0)

        bar = box(Gtk.Orientation.HORIZONTAL, 6)
        bar.get_style_context().add_class("tc-bottom-bar")
        bar.set_size_request(800, 72)
        bar.set_halign(Gtk.Align.FILL)
        bar.set_valign(Gtk.Align.END)

        controls = box(Gtk.Orientation.HORIZONTAL, 6)
        controls.set_margin_top(6)
        controls.set_margin_bottom(6)

        actions = [
            ("HOME ALL", lambda _w: self._queue_gcode("G28")),
            ("QGL", lambda _w: self._queue_gcode("QUAD_GANTRY_LEVEL")),
            ("DROP TOOL", lambda _w: self._queue_gcode("UNSELECT_TOOL")),
            ("SELECT TOOL", self._show_tool_selector),
            ("SETTINGS", self._show_settings),
        ]
        for label, callback in actions:
            b = button(label, "tc-btn-select", callback)
            b.set_size_request(135, 58)
            controls.pack_start(b, False, False, 0)

        bar.pack_start(controls, True, True, 0)
        root.pack_end(bar, False, False, 0)
        return root

    # ------------------------------------------------------------------
    # Card building
    # ------------------------------------------------------------------

    def _make_tool_states(self) -> List[ToolState]:
        states: List[ToolState] = []
        for index in range(self.num_tools):
            heater_name = "extruder" if index == 0 else f"extruder{index}"
            states.append(ToolState(index=index, heater_name=heater_name))
        return states

    def _rebuild_cards(self) -> None:
        for child in self.card_area.get_children():
            self.card_area.remove(child)

        self._tool_states = self._make_tool_states()
        self._card_widgets.clear()

        for state in self._tool_states:
            card, widgets = self._build_card(state)
            self._card_widgets[state.index] = widgets
            self.card_area.pack_start(card, False, False, 0)

        self.card_area.show_all()

    def _build_card(self, state: ToolState) -> tuple[Gtk.Box, CardWidgets]:
        frame = box(spacing=5)
        frame.get_style_context().add_class("tc-card")
        frame.set_size_request(185, 320)

        inner = box(spacing=2)
        inner.set_margin_top(8)
        inner.set_margin_bottom(8)
        inner.set_margin_start(6)
        inner.set_margin_end(6)

        title = Gtk.Label(label=state.display_title)
        title.get_style_context().add_class("tc-tool-label")
        inner.pack_start(title, False, False, 0)

        badge = Gtk.Label(label="PARKED")
        badge.get_style_context().add_class("tc-badge-parked")
        badge_wrap = box(Gtk.Orientation.HORIZONTAL, 0)
        badge_wrap.set_halign(Gtk.Align.CENTER)
        badge_wrap.pack_start(badge, False, False, 0)
        inner.pack_start(badge_wrap, False, False, 0)

        temp_event = Gtk.EventBox()
        temp_event.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        temp_label = Gtk.Label(label="--C")
        temp_label.get_style_context().add_class("tc-temp-label")
        temp_event.add(temp_label)
        temp_event.connect("button-press-event", lambda _w, _e, idx=state.index: self._show_temp_popup(idx))
        inner.pack_start(temp_event, False, False, 0)

        spool_button = Gtk.Button()
        spool_button.get_style_context().add_class("tc-spool-btn")
        spool_button.set_relief(Gtk.ReliefStyle.NONE)
        spool_button.set_focus_on_click(False)
        spool_button.set_size_request(110, 110)

        spool_area = Gtk.DrawingArea()
        spool_area.set_size_request(110, 110)
        spool_area.connect("draw", self._draw_spool, state.index)
        spool_button.add(spool_area)
        spool_button.connect("clicked", lambda _w, idx=state.index: self._show_spool_assign_popup(idx))

        spool_wrap = box(Gtk.Orientation.HORIZONTAL, 0)
        spool_wrap.set_halign(Gtk.Align.CENTER)
        spool_wrap.pack_start(spool_button, False, False, 0)
        inner.pack_start(spool_wrap, True, True, 5)

        material = Gtk.Label(label="EMPTY")
        material.get_style_context().add_class("tc-mat-label-empty")
        inner.pack_start(material, False, False, 5)

        buttons_row = box(Gtk.Orientation.HORIZONTAL, 8)
        buttons_row.set_halign(Gtk.Align.CENTER)
        buttons_row.pack_start(self._make_longpress_button("LOAD", "tc-btn-load", f"LOAD_FILAMENT TOOL={state.index}"), False, False, 0)
        buttons_row.pack_start(self._make_longpress_button("UNLOAD", "tc-btn-unload", f"UNLOAD_FILAMENT TOOL={state.index}"), False, False, 0)
        inner.pack_start(buttons_row, False, False, 10)

        frame.add(inner)

        return frame, CardWidgets(
            frame=frame,
            badge=badge,
            temp=temp_label,
            mat=material,
            spool_area=spool_area,
        )

    def _make_longpress_button(self, label: str, css_class: str, gcode: str) -> Gtk.Button:
        steps = 35
        b = Gtk.Button(label=label)
        b.get_style_context().add_class(css_class)
        b.set_size_request(80, 42)
        b.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)

        state = {"ticks": 0, "running": False, "source_id": None}

        def on_draw(widget: Gtk.Widget, cr: cairo.Context) -> bool:
            if not state["ticks"]:
                return False
            alloc = widget.get_allocation()
            progress = (state["ticks"] / steps) ** 1.5
            cr.set_source_rgba(1, 1, 1, 0.25)
            cr.rectangle(0, 0, alloc.width * progress, alloc.height)
            cr.fill()
            cr.set_source_rgba(1, 1, 1, 0.7)
            cr.rectangle(max(0, alloc.width * progress - 2), 0, 2, alloc.height)
            cr.fill()
            return False

        def tick() -> bool:
            if not state["running"]:
                return False
            state["ticks"] = min(state["ticks"] + 1, steps)
            b.queue_draw()
            if state["ticks"] >= steps:
                state["running"] = False
                state["ticks"] = 0
                b.queue_draw()
                self._queue_gcode(gcode)
                return False
            return True

        def on_press(_widget: Gtk.Widget, _event: Gdk.EventButton) -> bool:
            state["running"] = True
            state["ticks"] = 0
            state["source_id"] = GLib.timeout_add(max(1, 700 // steps), tick)
            return False

        def on_release(_widget: Gtk.Widget, _event: Gdk.EventButton) -> bool:
            state["running"] = False
            state["ticks"] = 0
            b.queue_draw()
            if state["source_id"]:
                GLib.source_remove(state["source_id"])
                state["source_id"] = None
            return False

        b.connect("draw", on_draw)
        b.connect("button-press-event", on_press)
        b.connect("button-release-event", on_release)
        b.connect("clicked", lambda _w: None)
        return b

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_spool(self, widget: Gtk.DrawingArea, cr: cairo.Context, tool_index: int) -> bool:
        state = self._tool_states[tool_index]
        color = normalize_hex(state.color_hex)
        r, g, b = hex_to_rgb01(color)

        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx = w / 2.0
        cy = h / 2.0
        outer = 46
        inner = 30
        hub = 10
        mid = (outer + inner) / 2.0
        full = 2 * math.pi
        active_glow = hex_to_gdk(color)

        if state.active:
            for i in range(10, 0, -1):
                cr.set_source_rgba(active_glow.red, active_glow.green, active_glow.blue, 0.03 * (11 - i))
                cr.set_line_width(i * 2)
                cr.arc(cx, cy, outer + 1, 0, full)
                cr.stroke()

        cr.set_source_rgb(0.18, 0.22, 0.34)
        cr.set_line_width(outer - inner)
        cr.arc(cx, cy, mid, 0, full)
        cr.stroke()

        grad = cairo.LinearGradient(cx - outer, cy - outer, cx + outer, cy + outer)
        grad.add_color_stop_rgb(0.0, min(1, r * 1.08 + 0.06), min(1, g * 1.08 + 0.06), min(1, b * 1.08 + 0.06))
        grad.add_color_stop_rgb(1.0, max(0, r * 0.55), max(0, g * 0.55), max(0, b * 0.55))
        cr.set_source(grad)
        cr.set_line_width(outer - inner - 2)
        cr.arc(cx, cy, mid, 0, full)
        cr.stroke()

        cr.set_source_rgba(1, 1, 1, 0.18)
        cr.set_line_width(3)
        cr.arc(cx, cy, mid, -math.pi * 0.7, -math.pi * 0.3)
        cr.stroke()

        cr.set_source_rgb(0.16, 0.20, 0.30)
        cr.arc(cx, cy, inner - 1, 0, full)
        cr.fill()

        if state.active:
            cr.set_source_rgb(active_glow.red, active_glow.green, active_glow.blue)
        elif state.is_heating:
            wr, wg, wb = hex_to_rgb01(self._theme["warn"])
            cr.set_source_rgb(wr, wg, wb)
        else:
            cr.set_source_rgb(0.28, 0.34, 0.50)
        cr.set_line_width(1.5)
        cr.arc(cx, cy, hub + 2, 0, full)
        cr.stroke()

        cr.set_source_rgba(0, 0, 0, 0.4)
        cr.set_line_width(1.5)
        for angle in [0, full / 3, full * 2 / 3]:
            cr.move_to(cx + math.cos(angle) * (hub + 4), cy + math.sin(angle) * (hub + 4))
            cr.line_to(cx + math.cos(angle) * (inner - 3), cy + math.sin(angle) * (inner - 3))
            cr.stroke()

        if state.remaining_ratio >= 0:
            ratio = clamp01(state.remaining_ratio)
            arc_radius = outer + 7
            start = -math.pi / 2

            cr.set_source_rgba(1, 1, 1, 0.10)
            cr.set_line_width(3)
            cr.arc(cx, cy, arc_radius, 0, full)
            cr.stroke()

            if ratio > 0.01:
                cr.set_source_rgba(1, 1, 1, 0.90)
                cr.set_line_width(3)
                cr.arc(cx, cy, arc_radius, start, start + full * ratio)
                cr.stroke()

                end_angle = start + full * ratio
                cr.arc(cx + math.cos(end_angle) * arc_radius, cy + math.sin(end_angle) * arc_radius, 2.5, 0, full)
                cr.fill()

            text = f"{int(ratio * 100)}%"
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(14)
            ext = cr.text_extents(text)
            cr.move_to(cx - (ext.width / 2 + ext.x_bearing), cy - (ext.height / 2 + ext.y_bearing))
            cr.show_text(text)

        return False

    # ------------------------------------------------------------------
    # Networking
    # ------------------------------------------------------------------

    def _moonraker_query(self) -> Optional[Dict[str, Any]]:
        tool_objects = [f"tool%20T{state.index}" for state in self._tool_states]
        heater_objects = [state.heater_name for state in self._tool_states]
        query = "&".join(heater_objects + ["save_variables", "toolhead", "toolchanger"] + tool_objects)
        url = f"{MOONRAKER}/printer/objects/query?{query}"

        for _ in range(2):
            try:
                response = self._session.get(url, timeout=REQUEST_TIMEOUT_MOONRAKER)
                response.raise_for_status()
                payload = response.json()
                return payload.get("result", {}).get("status", {})
            except Exception:
                pass
        return None

    def _spoolman_proxy_get(self, path: str) -> Any:
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
        except Exception:
            pass
        return None

    def _spoolman_list(self) -> List[Dict[str, Any]]:
        items = self._spoolman_proxy_get("/v1/spool?allow_archived=false")
        if not isinstance(items, list):
            return []
        try:
            items = sorted(items, key=lambda item: int(item.get("id", 0)))
        except Exception:
            pass
        return items

    def _spoolman_get_spool(self, spool_id: int) -> Optional[Dict[str, Any]]:
        if not spool_id:
            return None
        item = self._spoolman_proxy_get(f"/v1/spool/{spool_id}")
        return item if isinstance(item, dict) else None

    def _set_active_spoolman_spool(self, spool_id: Optional[int]) -> bool:
        try:
            payload = {} if not spool_id else {"spool_id": int(spool_id)}
            result = self._screen.apiclient.post_request(
                "server/spoolman/spool_id",
                json=payload,
            )
            return bool(result)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Polling and snapshots
    # ------------------------------------------------------------------

    def _start_polling_worker(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._refresh_tool_count_from_moonraker()
        self._poll_stop.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        while not self._poll_stop.is_set():
            snapshot = self._collect_snapshot()
            GLib.idle_add(self._apply_snapshot, snapshot)
            self._poll_stop.wait(POLL_INTERVAL_SECONDS)

    def _collect_snapshot(self) -> RuntimeSnapshot:
        base_states = [ToolState(index=s.index, heater_name=s.heater_name) for s in self._tool_states]
        status = self._moonraker_query()

        if not status:
            for state in base_states:
                state.reachable = False
            return RuntimeSnapshot(tools=base_states, moonraker_ok=False)

        save_variables = status.get("save_variables", {}).get("variables", {})
        active_name = status.get("toolhead", {}).get("extruder", "")

        tc_status = status.get("toolchanger", {}) or {}
        tc_status_str = str(tc_status.get("status", "ready")).lower()
        tc_active_tool = tc_status.get("tool_number", -1)
        tc_is_changing = tc_status_str == "changing"

        for state in base_states:
            heater = status.get(state.heater_name, {}) or {}
            state.temperature = float(heater.get("temperature", 0) or 0)
            state.target = float(heater.get("target", 0) or 0)
            state.active = active_name == state.heater_name or (state.index == 0 and active_name == "extruder")

            tool_obj = status.get(f"tool T{state.index}", {}) or {}
            tool_active = tool_obj.get("active", None)

            if tc_status_str == "error":
                state.ktc_state = "error"
            elif tc_is_changing and tc_active_tool == state.index:
                state.ktc_state = "changing"
            elif tool_active is True:
                state.ktc_state = "active"
            elif tool_active is False:
                state.ktc_state = "docked"
            else:
                state.ktc_state = "unknown"

            spool_key = f"t{state.index}__spool_id"
            raw_spool_id = save_variables.get(spool_key)
            try:
                state.spool_id = int(raw_spool_id) if raw_spool_id else None
            except Exception:
                state.spool_id = None

            if state.spool_id:
                spool = self._spoolman_get_spool(state.spool_id)
                if spool is None:
                    state.spool_error = True
                    continue

                filament = spool.get("filament", {}) or {}
                state.material = str(filament.get("material", "??")).upper()
                state.color_hex = normalize_hex(str(filament.get("color_hex") or "#333b54"))

                total_weight = float(filament.get("weight", 0) or 0)
                used_weight = float(spool.get("used_weight", 0) or 0)
                if total_weight > 0:
                    state.remaining_ratio = clamp01(1.0 - used_weight / total_weight)
                else:
                    state.remaining_ratio = -1.0
            else:
                state.material = "EMPTY"
                state.color_hex = "#333b54"
                state.remaining_ratio = -1.0

        return RuntimeSnapshot(tools=base_states, moonraker_ok=True)

    def _refresh_tool_count_from_moonraker(self) -> None:
        try:
            result = self._session.get(f"{MOONRAKER}/printer/objects/query?toolchanger", timeout=REQUEST_TIMEOUT_MOONRAKER)
            result.raise_for_status()
            payload = result.json()
            status = payload.get("result", {}).get("status", {})
        except Exception:
            status = None

        if not isinstance(status, dict):
            return

        tc = status.get("toolchanger", {}) or {}
        tool_numbers = tc.get("tool_numbers")
        tool_names = tc.get("tool_names")

        detected_count = None
        if isinstance(tool_numbers, list) and tool_numbers:
            detected_count = len(tool_numbers)
        elif isinstance(tool_names, list) and tool_names:
            detected_count = len(tool_names)
        elif isinstance(tc.get("tool_number"), int):
            detected_count = max(1, int(tc.get("tool_number")) + 1)

        if detected_count is None:
            return

        detected_count = max(1, detected_count)
        if detected_count != self.num_tools:
            self.num_tools = detected_count
            self._rebuild_cards()

    def _apply_snapshot(self, snapshot: RuntimeSnapshot) -> bool:
        self._tool_states = snapshot.tools
        for state in self._tool_states:
            widgets = self._card_widgets.get(state.index)
            if not widgets:
                continue

            widgets.temp.set_text(
                f"{state.temperature:.0f}C" + (f" / {state.target:.0f}" if state.target > 0 else "")
            )
            widgets.mat.set_text(state.material)

            frame_ctx = widgets.frame.get_style_context()
            if state.active:
                frame_ctx.add_class("tc-card-active")
                frame_ctx.remove_class("tc-card")
            else:
                frame_ctx.add_class("tc-card")
                frame_ctx.remove_class("tc-card-active")

            badge_ctx = widgets.badge.get_style_context()
            for cls in ("tc-badge-active", "tc-badge-heating", "tc-badge-parked", "tc-badge-error", "tc-badge-changing"):
                badge_ctx.remove_class(cls)
            widgets.badge.set_text(state.status_label)
            badge_ctx.add_class(state.status_css)

            widgets.spool_area.queue_draw()

        return False

    # ------------------------------------------------------------------
    # Command queue
    # ------------------------------------------------------------------

    def _start_command_worker(self) -> None:
        if self._command_thread and self._command_thread.is_alive():
            return
        self._command_thread = threading.Thread(target=self._command_loop, daemon=True)
        self._command_thread.start()

    def _command_loop(self) -> None:
        while not self._poll_stop.is_set():
            try:
                command = self._command_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                self._screen._ws.klippy.gcode_script(command)
            except Exception:
                pass
            finally:
                self._command_queue.task_done()

    def _queue_gcode(self, command: str) -> None:
        self._command_queue.put(command)

    # ------------------------------------------------------------------
    # Popup lifecycle helpers
    # ------------------------------------------------------------------

    def _register_popup(self, popup: Gtk.Window) -> Gtk.Window:
        if self._active_popup is not None:
            try:
                self._active_popup.destroy()
            except Exception:
                pass
        self._active_popup = popup
        popup.connect("destroy", self._on_popup_destroy)
        return popup

    def _on_popup_destroy(self, popup: Gtk.Window) -> None:
        if self._active_popup is popup:
            self._active_popup = None

    # ------------------------------------------------------------------
    # Tool selection
    # ------------------------------------------------------------------

    def _select_tool(self, tool_index: int) -> None:
        state = self._tool_states[tool_index]

        if not state.spool_id:
            self._show_message(f"Tool {tool_index + 1} has no spool assigned")
            return

        if state.ktc_state == "changing":
            self._show_message("Tool change already in progress")
            return

        if state.ktc_state == "active":
            self._show_message(f"Tool {tool_index + 1} already active")
            return

        if state.ktc_state == "error":
            self._show_message(f"Tool {tool_index + 1} is in error state")
            return

        state.ktc_state = "changing"
        GLib.idle_add(self._apply_snapshot, RuntimeSnapshot(self._tool_states))
        self._queue_gcode(f"T{tool_index}")

    # ------------------------------------------------------------------
    # Simple message popup
    # ------------------------------------------------------------------

    def _show_message(self, text: str) -> None:
        popup = self._register_popup(popup_window(self._screen))

        layout = box(spacing=10)
        layout.get_style_context().add_class("tc-popup")
        layout.set_margin_top(20)
        layout.set_margin_bottom(20)
        layout.set_margin_start(20)
        layout.set_margin_end(20)

        label = Gtk.Label(label=text)
        layout.pack_start(label, True, True, 0)

        btn = button("OK", "tc-btn-select", lambda _w: popup.destroy())
        layout.pack_start(btn, False, False, 0)

        popup.add(layout)
        popup.show_all()

    # ------------------------------------------------------------------
    # Popups
    # ------------------------------------------------------------------

    def _show_temp_popup(self, tool_index: int) -> None:
        state = self._tool_states[tool_index]
        popup = self._register_popup(popup_window(self._screen))

        layout = box(Gtk.Orientation.HORIZONTAL, 20)
        layout.get_style_context().add_class("tc-popup")
        layout.set_size_request(320, 380)
        layout.set_margin_top(15)
        layout.set_margin_bottom(15)
        layout.set_margin_start(15)
        layout.set_margin_end(15)

        value_label = Gtk.Label(label=f"{int(state.target)} C")
        value_label.get_style_context().add_class("tc-temp-label")

        adjustment = Gtk.Adjustment(value=state.target, lower=0, upper=310, step_increment=1, page_increment=10)
        slider = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=adjustment)
        slider.set_inverted(True)
        slider.set_vexpand(True)
        slider.set_draw_value(False)
        slider.connect("value-changed", lambda s: value_label.set_text(f"{int(s.get_value())} C"))

        slider_box = box(spacing=10)
        slider_box.pack_start(value_label, False, False, 0)
        slider_box.pack_start(slider, True, True, 0)
        layout.pack_start(slider_box, True, True, 0)

        def set_temperature(target: float) -> None:
            self._queue_gcode(f"SET_HEATER_TEMPERATURE HEATER={state.heater_name} TARGET={int(target)}")
            popup.destroy()

        controls = box(spacing=12)
        off_btn = button("OFF", "tc-btn-preset", lambda _w: set_temperature(0))
        off_btn.set_size_request(110, 58)

        set_btn = button("SET", "tc-btn-select", lambda _w: set_temperature(slider.get_value()))
        set_btn.set_size_request(110, 58)

        close_btn = button("CLOSE", "tc-btn-global", lambda _w: popup.destroy())
        close_btn.set_size_request(110, 48)

        controls.pack_start(off_btn, False, False, 0)
        controls.pack_end(close_btn, False, False, 0)
        controls.pack_end(set_btn, False, False, 0)
        layout.pack_start(controls, False, False, 0)

        popup.add(layout)
        popup.show_all()

    def _show_tool_selector(self, _widget: Gtk.Widget) -> None:
        popup = self._register_popup(popup_window(self._screen))

        inner = box(spacing=15)
        inner.get_style_context().add_class("tc-popup")
        inner.set_margin_top(20)
        inner.set_margin_bottom(20)
        inner.set_margin_start(20)
        inner.set_margin_end(20)

        row = box(Gtk.Orientation.HORIZONTAL, 15)
        row.set_halign(Gtk.Align.CENTER)
        for state in self._tool_states:
            def on_pick(_w: Gtk.Widget, idx: int = state.index) -> None:
                self._select_tool(idx)
                popup.destroy()

            b = button(f"T{state.index}", "tc-btn-select", on_pick)
            b.set_size_request(100, 100)
            row.pack_start(b, False, False, 0)

        inner.pack_start(row, True, True, 0)
        inner.pack_start(button("CANCEL", "tc-btn-global", lambda _w: popup.destroy()), False, False, 0)

        popup.add(inner)
        popup.show_all()

    def _show_spool_assign_popup(self, tool_index: int) -> None:
        popup = self._register_popup(popup_window(self._screen))
        state = self._tool_states[tool_index]

        outer = box(spacing=10)
        outer.get_style_context().add_class("tc-popup")
        outer.set_size_request(560, 440)
        outer.set_margin_top(14)
        outer.set_margin_bottom(14)
        outer.set_margin_start(14)
        outer.set_margin_end(14)

        header = Gtk.Label(label=f"SELECT SPOOL FOR TOOL {tool_index + 1}")
        header.get_style_context().add_class("tc-tool-label")
        outer.pack_start(header, False, False, 0)

        status = Gtk.Label(label="Loading spools from Spoolman...")
        status.get_style_context().add_class("tc-mat-label-empty")
        outer.pack_start(status, False, False, 0)

        search = Gtk.Entry()
        search.set_placeholder_text("Search spools...")
        search.get_style_context().add_class("tc-spool-search")
        outer.pack_start(search, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll.add(list_box)
        outer.pack_start(scroll, True, True, 0)

        button_row = box(Gtk.Orientation.HORIZONTAL, 10)
        button_row.set_halign(Gtk.Align.CENTER)

        clear_btn = button("CLEAR", "tc-spool-clear", lambda _w: self._clear_spool_assignment(tool_index, popup))
        clear_btn.set_size_request(120, 46)
        close_btn = button("CLOSE", "tc-btn-global", lambda _w: popup.destroy())
        close_btn.set_size_request(120, 46)

        button_row.pack_start(clear_btn, False, False, 0)
        button_row.pack_start(close_btn, False, False, 0)
        outer.pack_start(button_row, False, False, 0)

        popup.add(outer)
        popup.show_all()
        search.grab_focus()

        row_refs: List[tuple[Gtk.Button, str]] = []

        def assign_spool(spool_id: int) -> None:
            self._queue_gcode(f"SAVE_VARIABLE VARIABLE=t{tool_index}__spool_id VALUE={spool_id}")
            self._queue_gcode(f"SET_GCODE_VARIABLE MACRO=T{tool_index} VARIABLE=spool_id VALUE={spool_id}")
            self._set_active_spoolman_spool(spool_id)
            popup.destroy()

        def build_row(spool: Dict[str, Any]) -> Gtk.Button:
            spool_id = int(spool.get("id", 0))
            filament = spool.get("filament", {}) or {}
            material = str(filament.get("material", "UNKNOWN")).upper()
            color_hex = normalize_hex(str(filament.get("color_hex") or "#777777"))
            filament_name = str(filament.get("name", "") or "")
            total_weight = float(filament.get("weight", 0) or 0)
            used_weight = float(spool.get("used_weight", 0) or 0)

            vendor_obj = filament.get("vendor")
            vendor = vendor_obj.get("name", "") if isinstance(vendor_obj, dict) else ""

            remaining_pct = None
            remaining_grams = None
            if total_weight > 0:
                remaining_pct = int(clamp01(1.0 - used_weight / total_weight) * 100)
                remaining_grams = max(0, int(round(total_weight - used_weight)))

            row_button = Gtk.Button()
            row_button.get_style_context().add_class("tc-spool-list-btn")
            if state.spool_id == spool_id:
                row_button.get_style_context().add_class("tc-spool-selected")
            row_button.set_size_request(500, 58)
            row_button.connect("clicked", lambda _w, sid=spool_id: assign_spool(sid))

            row = box(Gtk.Orientation.HORIZONTAL, 10)
            row.set_margin_top(6)
            row.set_margin_bottom(6)
            row.set_margin_start(8)
            row.set_margin_end(8)

            color_da = Gtk.DrawingArea()
            color_da.set_size_request(26, 26)

            def draw_color(_widget: Gtk.DrawingArea, cr: cairo.Context, c: str = color_hex) -> bool:
                rgba = hex_to_gdk(c)
                grad = cairo.LinearGradient(0, 0, 26, 26)
                grad.add_color_stop_rgb(0, min(1, rgba.red * 1.08 + 0.06), min(1, rgba.green * 1.08 + 0.06), min(1, rgba.blue * 1.08 + 0.06))
                grad.add_color_stop_rgb(1, max(0, rgba.red * 0.55), max(0, rgba.green * 0.55), max(0, rgba.blue * 0.55))
                cr.set_source(grad)
                cr.arc(13, 13, 11, 0, 2 * math.pi)
                cr.fill()
                cr.set_source_rgba(1, 1, 1, 0.25)
                cr.set_line_width(1.5)
                cr.arc(13, 13, 11, 0, 2 * math.pi)
                cr.stroke()
                return False

            color_da.connect("draw", draw_color)
            row.pack_start(color_da, False, False, 0)

            text_box = box(spacing=2)
            name_label = Gtk.Label()
            name_label.set_xalign(0)
            name_label.get_style_context().add_class("tc-spool-name")
            main_line = material
            if filament_name:
                main_line += f" - {filament_name}"
            name_label.set_text(main_line)

            sub_label = Gtk.Label()
            sub_label.set_xalign(0)
            sub_label.get_style_context().add_class("tc-spool-sub")
            parts = [f"ID {spool_id}"]
            if vendor:
                parts.append(vendor)
            if remaining_pct is not None and remaining_grams is not None:
                parts.append(f"{remaining_pct}% / {remaining_grams}g left")
            sub_label.set_text(" - ".join(parts))

            text_box.pack_start(name_label, False, False, 0)
            text_box.pack_start(sub_label, False, False, 0)
            row.pack_start(text_box, True, True, 0)
            row_button.add(row)

            haystack = " ".join([str(spool_id), material, filament_name, vendor, sub_label.get_text()]).lower()
            row_refs.append((row_button, haystack))
            return row_button

        def filter_rows(entry: Gtk.Entry) -> None:
            query = entry.get_text().strip().lower()
            visible = 0
            for row_button, haystack in row_refs:
                show = (not query) or (query in haystack)
                row_button.set_visible(show)
                if show:
                    visible += 1
            status.set_text("Tap a spool to assign it." if visible else "No matching spools.")

        search.connect("changed", filter_rows)

        def populate(items: List[Dict[str, Any]]) -> bool:
            row_refs.clear()
            for child in list_box.get_children():
                list_box.remove(child)

            if not items:
                status.set_text("No spools returned from Spoolman.")
                list_box.show_all()
                return False

            for spool in items:
                list_box.pack_start(build_row(spool), False, False, 0)
            list_box.show_all()
            filter_rows(search)
            return False

        def fetch_spools() -> None:
            items = self._spoolman_list()
            GLib.idle_add(populate, items)

        threading.Thread(target=fetch_spools, daemon=True).start()

    def _clear_spool_assignment(self, tool_index: int, popup: Gtk.Window) -> None:
        self._queue_gcode(f"SAVE_VARIABLE VARIABLE=t{tool_index}__spool_id VALUE=0")
        self._queue_gcode(f"SET_GCODE_VARIABLE MACRO=T{tool_index} VARIABLE=spool_id VALUE=0")
        self._set_active_spoolman_spool(None)
        popup.destroy()

    def _show_settings(self, _widget: Gtk.Widget) -> None:
        popup = self._register_popup(popup_window(self._screen))

        outer = box(spacing=16)
        outer.get_style_context().add_class("tc-popup")
        outer.set_size_request(520, 260)
        outer.set_margin_top(20)
        outer.set_margin_bottom(20)
        outer.set_margin_start(20)
        outer.set_margin_end(20)

        header = Gtk.Label(label="SETTINGS")
        header.get_style_context().add_class("tc-tool-label")
        outer.pack_start(header, False, False, 0)

        grid = Gtk.Grid()
        grid.set_row_spacing(12)
        grid.set_column_spacing(12)
        grid.set_halign(Gtk.Align.CENTER)

        actions = [
            ("PID TUNE", lambda _w: (popup.destroy(), self._show_pid_select())),
            ("THEME", lambda _w: (popup.destroy(), self._show_theme())),
        ]

        for idx, (label, callback) in enumerate(actions):
            col = idx % 2
            row = idx // 2
            b = button(label, "tc-btn-select", callback)
            b.set_size_request(180, 80)
            grid.attach(b, col, row, 1, 1)

        outer.pack_start(grid, True, True, 0)
        outer.pack_start(button("CLOSE", "tc-btn-global", lambda _w: popup.destroy()), False, False, 0)

        popup.add(outer)
        popup.show_all()

    def _show_pid_select(self) -> None:
        popup = self._register_popup(popup_window(self._screen))

        inner = box(spacing=20)
        inner.get_style_context().add_class("tc-popup")
        inner.set_size_request(360, 240)
        inner.set_margin_top(24)
        inner.set_margin_bottom(24)
        inner.set_margin_start(24)
        inner.set_margin_end(24)

        header = Gtk.Label(label="PID TUNE - SELECT TOOL")
        header.get_style_context().add_class("tc-tool-label")
        inner.pack_start(header, False, False, 0)

        row = box(Gtk.Orientation.HORIZONTAL, 12)
        row.set_halign(Gtk.Align.CENTER)
        for state in self._tool_states:
            b = button(
                f"T{state.index}",
                "tc-btn-select",
                lambda _w, heater=state.heater_name: (popup.destroy(), self._show_pid_temp(heater)),
            )
            b.set_size_request(80, 80)
            row.pack_start(b, False, False, 0)

        inner.pack_start(row, True, True, 0)
        inner.pack_start(button("BACK", "tc-btn-global", lambda _w: (popup.destroy(), self._show_settings(None))), False, False, 0)

        popup.add(inner)
        popup.show_all()

    def _show_pid_temp(self, heater_name: str) -> None:
        popup = self._register_popup(popup_window(self._screen))

        layout = box(Gtk.Orientation.HORIZONTAL, 20)
        layout.get_style_context().add_class("tc-popup")
        layout.set_size_request(320, 360)
        layout.set_margin_top(15)
        layout.set_margin_bottom(15)
        layout.set_margin_start(15)
        layout.set_margin_end(15)

        default = 200
        value_label = Gtk.Label(label=f"{default} C")
        value_label.get_style_context().add_class("tc-temp-label")

        adjustment = Gtk.Adjustment(value=default, lower=0, upper=310, step_increment=1, page_increment=10)
        slider = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=adjustment)
        slider.set_inverted(True)
        slider.set_vexpand(True)
        slider.set_draw_value(False)
        slider.connect("value-changed", lambda s: value_label.set_text(f"{int(s.get_value())} C"))

        left = box(spacing=10)
        left.pack_start(value_label, False, False, 0)
        left.pack_start(slider, True, True, 0)
        layout.pack_start(left, True, True, 0)

        controls = box(spacing=12)
        run = button(
            "RUN PID",
            "tc-btn-select",
            lambda _w: (self._queue_gcode(f"PID_TUNE HEATER={heater_name} TARGET={int(slider.get_value())}"), popup.destroy()),
        )
        run.set_size_request(110, 58)

        cancel = button("CANCEL", "tc-btn-global", lambda _w: popup.destroy())
        cancel.set_size_request(110, 48)

        controls.pack_start(run, False, False, 0)
        controls.pack_end(cancel, False, False, 0)
        layout.pack_start(controls, False, False, 0)

        popup.add(layout)
        popup.show_all()

    def _show_theme(self) -> None:
        popup = self._register_popup(popup_window(self._screen))

        outer = box(spacing=14)
        outer.get_style_context().add_class("tc-popup")
        outer.set_size_request(520, 340)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)

        header = Gtk.Label(label="THEME")
        header.get_style_context().add_class("tc-tool-label")
        outer.pack_start(header, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(8)
        grid.set_halign(Gtk.Align.CENTER)
        swatches: Dict[str, Gtk.DrawingArea] = {}

        for idx, (name, theme) in enumerate(THEMES.items()):
            col, row = idx % 3, idx // 3
            slot = box(spacing=4)
            slot.set_halign(Gtk.Align.CENTER)

            da = Gtk.DrawingArea()
            da.set_size_request(140, 40)

            def draw_swatch(widget: Gtk.DrawingArea, cr: cairo.Context, t: Dict[str, str] = theme, theme_name: str = name) -> bool:
                width = widget.get_allocated_width()
                bg = hex_to_gdk(t["bg"])
                cr.set_source_rgb(bg.red, bg.green, bg.blue)
                cr.rectangle(0, 0, width, 40)
                cr.fill()

                ac = hex_to_gdk(t["accent"])
                cr.set_source_rgb(ac.red, ac.green, ac.blue)
                cr.rectangle(0, 32, width, 8)
                cr.fill()

                card = hex_to_gdk(t["card"])
                cr.set_source_rgb(card.red, card.green, card.blue)
                cr.rectangle(8, 5, 30, 22)
                cr.fill()

                if self._theme_name == theme_name:
                    cr.set_source_rgb(ac.red, ac.green, ac.blue)
                    cr.set_line_width(3)
                    cr.rectangle(1, 1, width - 2, 38)
                    cr.stroke()
                return False

            da.connect("draw", draw_swatch)
            swatches[name] = da

            label = Gtk.Label(label=name)
            label.get_style_context().add_class("tc-mat-label-empty")
            label.set_size_request(140, -1)

            event = Gtk.EventBox()
            event.add(da)
            event.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

            def on_pick(_w: Gtk.Widget, _e: Gdk.EventButton, theme_name: str = name) -> bool:
                self._theme_name = theme_name
                self._custom = None
                self._apply_theme()
                self._save_config()
                for area in swatches.values():
                    area.queue_draw()
                return True

            event.connect("button-press-event", on_pick)
            slot.pack_start(event, False, False, 0)
            slot.pack_start(label, False, False, 0)
            grid.attach(slot, col, row, 1, 1)

        outer.pack_start(grid, True, True, 0)

        bottom = box(Gtk.Orientation.HORIZONTAL, 10)
        bottom.set_halign(Gtk.Align.CENTER)
        custom = button("CUSTOM", "tc-btn-global", lambda _w: (popup.destroy(), self._show_custom_theme()))
        custom.set_size_request(130, 44)
        back = button("BACK", "tc-btn-global", lambda _w: (popup.destroy(), self._show_settings(None)))
        back.set_size_request(130, 44)
        bottom.pack_start(custom, False, False, 0)
        bottom.pack_start(back, False, False, 0)

        outer.pack_start(bottom, False, False, 0)
        popup.add(outer)
        popup.show_all()

    def _show_custom_theme(self) -> None:
        popup = self._register_popup(popup_window(self._screen))

        outer = box(spacing=12)
        outer.get_style_context().add_class("tc-popup")
        outer.set_size_request(460, 420)
        outer.set_margin_top(18)
        outer.set_margin_bottom(18)
        outer.set_margin_start(18)
        outer.set_margin_end(18)

        header = Gtk.Label(label="CUSTOM THEME BUILDER")
        header.get_style_context().add_class("tc-tool-label")
        outer.pack_start(header, False, False, 0)

        preview = Gtk.DrawingArea()
        preview.set_size_request(420, 80)

        base = self._custom if isinstance(self._custom, dict) else BASE_THEMES.get(self._theme_name, BASE_THEMES["Ocean"])

        fields = [
            ("Background", "bg"),
            ("Card", "card"),
            ("Accent", "accent"),
            ("Buttons", "btn_bg"),
            ("Text", "text"),
            ("Bar", "bar_bg"),
        ]

        pickers: Dict[str, Gtk.ColorButton] = {}

        grid = Gtk.Grid()
        grid.set_column_spacing(14)
        grid.set_row_spacing(12)
        grid.set_halign(Gtk.Align.CENTER)

        for row, (label, key) in enumerate(fields):
            lbl = Gtk.Label(label=label)
            lbl.set_halign(Gtk.Align.START)
            lbl.get_style_context().add_class("tc-mat-label")

            picker = Gtk.ColorButton()
            picker.set_rgba(hex_to_gdk(base.get(key, "#ffffff")))
            picker.set_size_request(140, 40)

            pickers[key] = picker

            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(picker, 1, row, 1, 1)

        outer.pack_start(grid, True, True, 0)

        preview_state = {"theme": derive_theme_fields({k: gdk_to_hex(p.get_rgba()) for k, p in pickers.items()})}

        def draw_preview(widget: Gtk.DrawingArea, cr: cairo.Context) -> bool:
            derived = preview_state["theme"]
            w = widget.get_allocated_width()
            h = widget.get_allocated_height()

            bg = hex_to_gdk(derived["bg"])
            cr.set_source_rgb(bg.red, bg.green, bg.blue)
            cr.rectangle(0, 0, w, h)
            cr.fill()

            card = hex_to_gdk(derived["card"])
            cr.set_source_rgb(card.red, card.green, card.blue)
            cr.rectangle(10, 10, w - 20, h - 20)
            cr.fill()

            accent = hex_to_gdk(derived["accent"])
            cr.set_source_rgb(accent.red, accent.green, accent.blue)
            cr.rectangle(10, h - 20, w - 20, 10)
            cr.fill()

            return False

        def redraw_preview(_w=None) -> None:
            theme_preview = {k: gdk_to_hex(p.get_rgba()) for k, p in pickers.items()}
            preview_state["theme"] = derive_theme_fields(theme_preview)
            preview.queue_draw()

        preview.connect("draw", draw_preview)
        for p in pickers.values():
            p.connect("color-set", redraw_preview)

        outer.pack_start(preview, False, False, 0)
        redraw_preview()

        def apply_custom(_w):
            custom = {k: gdk_to_hex(p.get_rgba()) for k, p in pickers.items()}
            self._custom = custom
            self._theme_name = "Custom"
            self._apply_theme()
            self._save_config()
            popup.destroy()

        btn_row = box(Gtk.Orientation.HORIZONTAL, 10)
        btn_row.set_halign(Gtk.Align.CENTER)

        apply_btn = button("APPLY", "tc-btn-select", apply_custom)
        apply_btn.set_size_request(130, 48)

        back_btn = button("BACK", "tc-btn-global", lambda _w: (popup.destroy(), self._show_theme()))
        back_btn.set_size_request(130, 48)

        btn_row.pack_start(apply_btn, False, False, 0)
        btn_row.pack_start(back_btn, False, False, 0)

        outer.pack_start(btn_row, False, False, 0)

        popup.add(outer)
        popup.show_all()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def activate(self) -> None:
        self._poll_stop.clear()
        self._start_command_worker()
        self._start_polling_worker()

    def deactivate(self) -> None:
        self._poll_stop.set()


Panel = ToolchangerPanel
