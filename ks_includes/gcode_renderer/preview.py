from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import ToolpathModel


class PreviewContext(str, Enum):
    SELECTED_FILE = "selected_file"
    ACTIVE_PRINT = "active_print"


@dataclass(frozen=True, slots=True)
class SelectedPreviewState:
    layer_index: int = -1
    move_index: int = 0


def resolve_preview_context(
    preview_context: str | None,
    filename: str | None = None,
    *,
    default_active_print: bool = False,
) -> PreviewContext | None:
    filename = filename or ""
    if preview_context is None:
        if filename:
            return PreviewContext.SELECTED_FILE
        return PreviewContext.ACTIVE_PRINT if default_active_print else None
    try:
        return PreviewContext(preview_context)
    except ValueError:
        return None


def preview_panel_name(preview_context: PreviewContext | str | None) -> str:
    if isinstance(preview_context, PreviewContext):
        preview_context = preview_context.value
    if preview_context == PreviewContext.SELECTED_FILE.value:
        return "gcode_viewer_selected"
    if preview_context == PreviewContext.ACTIVE_PRINT.value:
        return "gcode_viewer_active"
    return "gcode_viewer"


def initial_selected_preview_state(model: ToolpathModel | None) -> SelectedPreviewState:
    if model is None or model.total_layers <= 0:
        return SelectedPreviewState()
    return SelectedPreviewState(layer_index=model.total_layers - 1, move_index=0)


def clamp_selected_preview_state(
    model: ToolpathModel | None,
    layer_index: int,
    move_index: int,
) -> SelectedPreviewState:
    if model is None or model.total_layers <= 0:
        return SelectedPreviewState()
    layer_index = model.clamp_layer_index(layer_index)
    move_index = model.clamp_layer_move_index(layer_index, move_index)
    return SelectedPreviewState(layer_index=layer_index, move_index=move_index)
