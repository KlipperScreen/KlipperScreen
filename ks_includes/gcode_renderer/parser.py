from __future__ import annotations

import re
from dataclasses import dataclass

from .model import (
    FLAG_EXTRUSION,
    FLAG_RETRACTION,
    FLAG_TRAVEL,
    Bounds,
    ToolpathModel,
)

COMMAND_RE = re.compile(r"^(?P<command>[GMT]\d+)\b", re.IGNORECASE)
PARAM_RE = re.compile(r"([A-Za-z])([-+]?(?:\d+(?:\.\d*)?|\.\d+))")
LAYER_COMMENT_RES = (
    re.compile(r"^\s*LAYER:\s*(-?\d+)\s*$", re.IGNORECASE),
    re.compile(r"^\s*LAYER\s+(\d+)\s*$", re.IGNORECASE),
    re.compile(r"^\s*BEGIN_LAYER(?:_OBJECT)?\s+(\d+)\s*$", re.IGNORECASE),
)
LAYER_CHANGE_RE = re.compile(r"^\s*LAYER_CHANGE\s*$", re.IGNORECASE)

POSITION_EPSILON = 1e-6
EXTRUSION_EPSILON = 1e-7


@dataclass(slots=True)
class ParserState:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    e: float = 0.0
    feedrate: float = 0.0
    absolute_positioning: bool = True
    absolute_extrusion: bool = True
    current_layer: int = -1
    current_layer_z: float = 0.0
    pending_layer_comment: int = -1
    pending_layer_change: bool = False
    pending_layer_z: float | None = None
    saw_extrusion_layer: bool = False


def parse_gcode(
    data: bytes,
    filename: str,
    file_size: int | None = None,
    modified: float = 0.0,
) -> ToolpathModel:
    model = ToolpathModel(
        filename=filename,
        file_size=len(data) if file_size is None else int(file_size),
        modified=float(modified or 0.0),
        total_bytes=len(data),
    )
    state = ParserState()
    bounds = model.bounds
    layer_starts: dict[int, int] = {}
    layer_ends: dict[int, int] = {}
    offset = 0

    for raw_line in data.splitlines(keepends=True):
        offset += len(raw_line)
        try:
            line = raw_line.decode("utf-8", errors="ignore").strip()
        except Exception:
            model.parser_warnings.append("Unable to decode one G-code line; it was skipped.")
            continue

        if not line:
            continue

        code, _, comment = line.partition(";")
        _track_layer_comment(comment, state)
        code = code.strip()
        if not code:
            continue

        command_match = COMMAND_RE.match(code)
        if not command_match:
            model.parser_warnings.append(f"Ignored malformed line: {line[:60]}")
            continue

        command = command_match.group("command").upper()
        params = _parse_params(code[command_match.end() :])

        if command == "G90":
            state.absolute_positioning = True
            continue
        if command == "G91":
            state.absolute_positioning = False
            continue
        if command == "M82":
            state.absolute_extrusion = True
            continue
        if command == "M83":
            state.absolute_extrusion = False
            continue
        if command == "G92":
            _apply_position_reset(params, state)
            continue
        if command in {"G2", "G3"}:
            model.parser_warnings.append("Arc commands G2/G3 are not rendered in this version.")
            continue
        if command not in {"G0", "G1"}:
            if command.startswith(("G", "M", "T")):
                continue
            model.parser_warnings.append(f"Unsupported command ignored: {command}")
            continue

        _handle_linear_move(params, state, model, bounds, layer_starts, layer_ends, offset)

    if layer_starts:
        layer_count = max(layer_starts) + 1
        model.layer_ranges = [(0, 0)] * layer_count
        model.layer_zs = [0.0] * layer_count
        for layer in range(layer_count):
            if layer not in layer_starts:
                continue
            model.layer_ranges[layer] = (layer_starts[layer], layer_ends[layer])
            model.layer_zs[layer] = model.segments[layer_starts[layer]][4]
    return model


def _track_layer_comment(comment: str, state: ParserState) -> None:
    if not comment:
        return
    stripped = comment.strip()
    for pattern in LAYER_COMMENT_RES:
        match = pattern.match(stripped)
        if match:
            layer_value = int(match.group(1))
            if layer_value >= 0:
                state.pending_layer_comment = layer_value
                state.pending_layer_change = True
            return
    if LAYER_CHANGE_RE.match(stripped):
        state.pending_layer_change = True


def _parse_params(code: str) -> dict[str, float]:
    params = {}
    for key, value in PARAM_RE.findall(code):
        try:
            params[key.upper()] = float(value)
        except ValueError:
            continue
    return params


def _apply_position_reset(params: dict[str, float], state: ParserState) -> None:
    for axis in ("X", "Y", "Z", "E"):
        if axis not in params:
            continue
        if axis == "X":
            state.x = params[axis]
        elif axis == "Y":
            state.y = params[axis]
        elif axis == "Z":
            state.z = params[axis]
        else:
            state.e = params[axis]


def _axis_target(current: float, params: dict[str, float], axis: str, absolute: bool) -> float:
    if axis not in params:
        return current
    return params[axis] if absolute else current + params[axis]


def _ensure_layer(state: ParserState, model: ToolpathModel, z_value: float) -> int:
    if state.current_layer < 0:
        state.current_layer = max(state.pending_layer_comment, 0)
        state.current_layer_z = z_value
        state.saw_extrusion_layer = True
        return state.current_layer

    should_advance = False
    if state.pending_layer_comment > state.current_layer:
        should_advance = True
    elif (
        state.pending_layer_change or state.pending_layer_z is not None
    ) and z_value > state.current_layer_z + POSITION_EPSILON:
        should_advance = True

    if should_advance:
        next_layer = (
            state.pending_layer_comment
            if state.pending_layer_comment > state.current_layer
            else state.current_layer + 1
        )
        state.current_layer = next_layer
        state.current_layer_z = z_value
    elif z_value > state.current_layer_z + POSITION_EPSILON and not state.saw_extrusion_layer:
        state.current_layer_z = z_value

    state.pending_layer_comment = -1
    state.pending_layer_change = False
    state.pending_layer_z = None
    state.saw_extrusion_layer = True
    return state.current_layer


def _handle_linear_move(
    params: dict[str, float],
    state: ParserState,
    model: ToolpathModel,
    bounds: Bounds,
    layer_starts: dict[int, int],
    layer_ends: dict[int, int],
    end_offset: int,
) -> None:
    start_x, start_y, start_z, start_e = state.x, state.y, state.z, state.e
    target_x = _axis_target(start_x, params, "X", state.absolute_positioning)
    target_y = _axis_target(start_y, params, "Y", state.absolute_positioning)
    target_z = _axis_target(start_z, params, "Z", state.absolute_positioning)
    target_e = _axis_target(start_e, params, "E", state.absolute_extrusion)
    if "F" in params:
        state.feedrate = params["F"]

    delta_x = target_x - start_x
    delta_y = target_y - start_y
    delta_z = target_z - start_z
    delta_e = target_e - start_e
    has_xy = abs(delta_x) > POSITION_EPSILON or abs(delta_y) > POSITION_EPSILON
    has_motion = has_xy or abs(delta_z) > POSITION_EPSILON
    is_extrusion = delta_e > EXTRUSION_EPSILON and has_xy
    is_retraction = delta_e < -EXTRUSION_EPSILON and not has_xy
    is_travel = has_xy and not is_extrusion

    if abs(delta_z) > POSITION_EPSILON and target_z > state.current_layer_z + POSITION_EPSILON:
        state.pending_layer_z = target_z

    if is_extrusion:
        layer = _ensure_layer(state, model, target_z)
        flags = FLAG_EXTRUSION
        segment = (
            start_x,
            start_y,
            target_x,
            target_y,
            target_z,
            layer,
            flags,
            end_offset,
            start_z,
        )
        model.segments.append(segment)
        model.segment_end_offsets.append(end_offset)
        bounds.include(start_x, start_y)
        bounds.include(target_x, target_y)
        layer_starts.setdefault(layer, len(model.segments) - 1)
        layer_ends[layer] = len(model.segments)
    elif is_travel:
        flags = FLAG_TRAVEL
        layer = state.current_layer if state.current_layer >= 0 else 0
        segment = (
            start_x,
            start_y,
            target_x,
            target_y,
            target_z,
            layer,
            flags,
            end_offset,
            start_z,
        )
        model.segments.append(segment)
        model.segment_end_offsets.append(end_offset)
        bounds.include(start_x, start_y)
        bounds.include(target_x, target_y)
        if layer in layer_starts:
            layer_ends[layer] = len(model.segments)
    elif is_retraction:
        if model.segments:
            previous = model.segments[-1]
            model.segments[-1] = (
                previous[0],
                previous[1],
                previous[2],
                previous[3],
                previous[4],
                previous[5],
                previous[6] | FLAG_RETRACTION,
                previous[7],
                previous[8],
            )

    if has_motion and not is_extrusion:
        state.saw_extrusion_layer = False

    state.x = target_x
    state.y = target_y
    state.z = target_z
    state.e = target_e
