from __future__ import annotations

import logging
from dataclasses import dataclass

from .model import RenderMode
from .projection import DisplayViewMode

DEFAULT_ENABLED = False
DEFAULT_SHOW_TRAVEL = False
DEFAULT_MODE = RenderMode.CURRENT_LAYER
DEFAULT_VIEW = DisplayViewMode.MODE_2D
DEFAULT_FPS = 5
DEFAULT_PREVIOUS_LAYERS = 3
MAX_FPS = 10
MAX_PREVIOUS_LAYERS = 10
RENDERER_OPTION_KEYS = (
    "enable_gcode_renderer",
    "gcode_renderer_view",
    "gcode_renderer_show_travel",
    "gcode_renderer_mode",
    "gcode_renderer_fps",
    "gcode_renderer_previous_layers",
)


@dataclass(frozen=True, slots=True)
class RendererSettings:
    enabled: bool = DEFAULT_ENABLED
    view: DisplayViewMode = DEFAULT_VIEW
    show_travel: bool = DEFAULT_SHOW_TRAVEL
    mode: RenderMode = DEFAULT_MODE
    fps: int = DEFAULT_FPS
    previous_layers: int = DEFAULT_PREVIOUS_LAYERS


def get_renderer_settings(config_section, logger=None) -> RendererSettings:
    logger = logger or logging.getLogger(__name__)
    enabled = _parse_bool(
        config_section.get("enable_gcode_renderer", str(DEFAULT_ENABLED)),
        DEFAULT_ENABLED,
        "enable_gcode_renderer",
        logger,
    )
    view = _parse_view(config_section.get("gcode_renderer_view", DEFAULT_VIEW.value), logger)
    show_travel = _parse_bool(
        config_section.get("gcode_renderer_show_travel", str(DEFAULT_SHOW_TRAVEL)),
        DEFAULT_SHOW_TRAVEL,
        "gcode_renderer_show_travel",
        logger,
    )
    mode = _parse_mode(config_section.get("gcode_renderer_mode", DEFAULT_MODE.value), logger)
    fps = _parse_int(
        config_section.get("gcode_renderer_fps", str(DEFAULT_FPS)),
        DEFAULT_FPS,
        1,
        MAX_FPS,
        "gcode_renderer_fps",
        logger,
    )
    previous_layers = _parse_int(
        config_section.get("gcode_renderer_previous_layers", str(DEFAULT_PREVIOUS_LAYERS)),
        DEFAULT_PREVIOUS_LAYERS,
        0,
        MAX_PREVIOUS_LAYERS,
        "gcode_renderer_previous_layers",
        logger,
    )
    return RendererSettings(
        enabled=enabled,
        view=view,
        show_travel=show_travel,
        mode=mode,
        fps=fps,
        previous_layers=previous_layers,
    )


def preview_menu_visible(enabled: bool, filename: str | None) -> bool:
    return bool(enabled and filename)


def preview_access_location() -> str:
    return "print_menu"


def _parse_bool(value, fallback: bool, key: str, logger) -> bool:
    if isinstance(value, bool):
        return value
    if value in ("True", "true", "1"):
        return True
    if value in ("False", "false", "0"):
        return False
    logger.warning("Invalid %s value %r; falling back to %s", key, value, fallback)
    return fallback


def _parse_mode(value: str, logger) -> RenderMode:
    mode = RenderMode.from_value(value, DEFAULT_MODE)
    if mode.value != value:
        logger.warning(
            "Invalid gcode_renderer_mode value %r; falling back to %s",
            value,
            DEFAULT_MODE.value,
        )
    return mode


def _parse_view(value: str, logger) -> DisplayViewMode:
    view = DisplayViewMode.from_value(value, DEFAULT_VIEW)
    if view.value != value:
        logger.warning(
            "Invalid gcode_renderer_view value %r; falling back to %s",
            value,
            DEFAULT_VIEW.value,
        )
    return view


def _parse_int(value, fallback: int, minimum: int, maximum: int, key: str, logger) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid %s value %r; falling back to %s", key, value, fallback)
        return fallback
    if parsed < minimum:
        logger.warning("%s value %s below minimum %s; clamping", key, parsed, minimum)
        return minimum
    if parsed > maximum:
        logger.warning("%s value %s above maximum %s; clamping", key, parsed, maximum)
        return maximum
    return parsed
