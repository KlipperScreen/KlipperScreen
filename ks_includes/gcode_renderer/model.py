from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence, Tuple

SEGMENT_X0 = 0
SEGMENT_Y0 = 1
SEGMENT_X1 = 2
SEGMENT_Y1 = 3
SEGMENT_Z = 4
SEGMENT_LAYER = 5
SEGMENT_FLAGS = 6
SEGMENT_END_OFFSET = 7
SEGMENT_Z0 = 8

FLAG_EXTRUSION = 1
FLAG_TRAVEL = 2
FLAG_RETRACTION = 4


class RenderMode(str, Enum):
    CURRENT_LAYER = "current_layer"
    CURRENT_AND_PREVIOUS = "current_and_previous"
    FULL_MODEL = "full_model"

    @classmethod
    def from_value(cls, value: str, fallback: "RenderMode" = None) -> "RenderMode":
        fallback = fallback or cls.CURRENT_LAYER
        try:
            return cls(value)
        except ValueError:
            return fallback


@dataclass(slots=True)
class Bounds:
    min_x: float = float("inf")
    min_y: float = float("inf")
    max_x: float = float("-inf")
    max_y: float = float("-inf")

    def include(self, x: float, y: float) -> None:
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.max_x = max(self.max_x, x)
        self.max_y = max(self.max_y, y)

    @property
    def width(self) -> float:
        return 0.0 if not self.is_valid else self.max_x - self.min_x

    @property
    def height(self) -> float:
        return 0.0 if not self.is_valid else self.max_y - self.min_y

    @property
    def is_valid(self) -> bool:
        return self.min_x != float("inf") and self.min_y != float("inf")


@dataclass(slots=True)
class SpatialBounds:
    min_x: float = float("inf")
    min_y: float = float("inf")
    min_z: float = float("inf")
    max_x: float = float("-inf")
    max_y: float = float("-inf")
    max_z: float = float("-inf")

    def include(self, x: float, y: float, z: float) -> None:
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.min_z = min(self.min_z, z)
        self.max_x = max(self.max_x, x)
        self.max_y = max(self.max_y, y)
        self.max_z = max(self.max_z, z)

    @property
    def width(self) -> float:
        return 0.0 if not self.is_valid else self.max_x - self.min_x

    @property
    def height(self) -> float:
        return 0.0 if not self.is_valid else self.max_y - self.min_y

    @property
    def depth(self) -> float:
        return 0.0 if not self.is_valid else self.max_z - self.min_z

    @property
    def is_valid(self) -> bool:
        return (
            self.min_x != float("inf")
            and self.min_y != float("inf")
            and self.min_z != float("inf")
        )

    def corners(self) -> tuple[tuple[float, float, float], ...]:
        if not self.is_valid:
            return ()
        return (
            (self.min_x, self.min_y, self.min_z),
            (self.min_x, self.min_y, self.max_z),
            (self.min_x, self.max_y, self.min_z),
            (self.min_x, self.max_y, self.max_z),
            (self.max_x, self.min_y, self.min_z),
            (self.max_x, self.min_y, self.max_z),
            (self.max_x, self.max_y, self.min_z),
            (self.max_x, self.max_y, self.max_z),
        )


@dataclass(slots=True)
class ProgressInfo:
    file_position: int = 0
    current_segment: int = -1
    executed_segments: int = 0
    current_layer: int = -1
    toolhead: Optional[Tuple[float, float, float]] = None
    print_state: str = "standby"


@dataclass(slots=True)
class ToolpathModel:
    filename: str
    file_size: int
    modified: float
    total_bytes: int
    segments: list[tuple] = field(default_factory=list)
    segment_end_offsets: list[int] = field(default_factory=list)
    layer_ranges: list[tuple] = field(default_factory=list)
    layer_zs: list[float] = field(default_factory=list)
    bounds: Bounds = field(default_factory=Bounds)
    parser_warnings: list[str] = field(default_factory=list)
    arcs_supported: bool = False

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def total_layers(self) -> int:
        return len(self.layer_ranges)

    @property
    def has_extrusion(self) -> bool:
        return any(segment[SEGMENT_FLAGS] & FLAG_EXTRUSION for segment in self.segments)

    @property
    def has_travel(self) -> bool:
        return any(segment[SEGMENT_FLAGS] & FLAG_TRAVEL for segment in self.segments)

    def progress_for_offset(
        self,
        file_position: int,
        print_state: str = "standby",
        toolhead: Optional[Tuple[float, float, float]] = None,
    ) -> ProgressInfo:
        if not self.segments:
            return ProgressInfo(
                file_position=max(file_position, 0),
                current_segment=-1,
                executed_segments=0,
                current_layer=-1,
                toolhead=toolhead,
                print_state=print_state,
            )

        executed = bisect_right(self.segment_end_offsets, max(file_position, 0))
        current_segment = min(executed, self.segment_count - 1)
        if file_position >= self.segment_end_offsets[-1]:
            executed = self.segment_count
            current_segment = self.segment_count - 1
        current_layer = self.segment_layer(current_segment) if current_segment >= 0 else -1
        return ProgressInfo(
            file_position=max(file_position, 0),
            current_segment=current_segment,
            executed_segments=executed,
            current_layer=current_layer,
            toolhead=toolhead,
            print_state=print_state,
        )

    def segment_layer(self, segment_index: int) -> int:
        if segment_index < 0 or segment_index >= self.segment_count:
            return -1
        return int(self.segments[segment_index][SEGMENT_LAYER])

    def clamp_layer_index(self, layer_index: int) -> int:
        if not self.layer_ranges:
            return -1
        return max(0, min(int(layer_index), self.total_layers - 1))

    def layer_segment_range(self, layer_index: int) -> tuple[int, int]:
        layer_index = self.clamp_layer_index(layer_index)
        if layer_index < 0:
            return (0, 0)
        return tuple(self.layer_ranges[layer_index])

    def layer_segment_count(self, layer_index: int) -> int:
        start, end = self.layer_segment_range(layer_index)
        return max(end - start, 0)

    def layer_z_height(self, layer_index: int) -> float | None:
        layer_index = self.clamp_layer_index(layer_index)
        if layer_index < 0 or layer_index >= len(self.layer_zs):
            return None
        return float(self.layer_zs[layer_index])

    def clamp_layer_move_index(self, layer_index: int, move_index: int) -> int:
        count = self.layer_segment_count(layer_index)
        if count <= 0:
            return 0
        return max(0, min(int(move_index), count - 1))

    def layer_move_segment_index(self, layer_index: int, move_index: int) -> int:
        start, end = self.layer_segment_range(layer_index)
        if end <= start:
            return -1
        return start + self.clamp_layer_move_index(layer_index, move_index)

    def progress_for_layer_move(
        self,
        layer_index: int,
        move_index: int,
        print_state: str = "standby",
    ) -> ProgressInfo:
        layer_index = self.clamp_layer_index(layer_index)
        if layer_index < 0:
            return ProgressInfo(current_layer=-1, print_state=print_state)
        start, end = self.layer_segment_range(layer_index)
        if end <= start:
            return ProgressInfo(
                current_layer=layer_index,
                executed_segments=start,
                current_segment=-1,
                print_state=print_state,
            )
        current_segment = self.layer_move_segment_index(layer_index, move_index)
        file_position = self.segment_end_offsets[current_segment] if current_segment >= 0 else 0
        return ProgressInfo(
            file_position=file_position,
            current_segment=current_segment,
            executed_segments=max(current_segment, 0),
            current_layer=layer_index,
            toolhead=None,
            print_state=print_state,
        )

    def visible_segment_range(
        self, mode: RenderMode, current_layer: int, previous_layers: int
    ) -> tuple[int, int]:
        if not self.segments:
            return (0, 0)
        if mode == RenderMode.FULL_MODEL or current_layer < 0 or not self.layer_ranges:
            return (0, self.segment_count)

        last_layer = min(current_layer, self.total_layers - 1)
        if mode == RenderMode.CURRENT_LAYER:
            first_layer = last_layer
        else:
            first_layer = max(0, last_layer - max(previous_layers, 0))
        start = self.layer_ranges[first_layer][0]
        end = self.layer_ranges[last_layer][1]
        return (start, end)

    def visible_layers(
        self, mode: RenderMode, current_layer: int, previous_layers: int
    ) -> Sequence[int]:
        if not self.layer_ranges:
            return ()
        if mode == RenderMode.FULL_MODEL or current_layer < 0:
            return tuple(range(self.total_layers))
        last_layer = min(current_layer, self.total_layers - 1)
        if mode == RenderMode.CURRENT_LAYER:
            first_layer = last_layer
        else:
            first_layer = max(0, last_layer - max(previous_layers, 0))
        return tuple(range(first_layer, last_layer + 1))

    def visible_bounds(self, mode: RenderMode, current_layer: int, previous_layers: int) -> tuple[Bounds, bool]:
        start, end = self.visible_segment_range(mode, current_layer, previous_layers)
        if start == end:
            return (Bounds(), False)

        extrusion_bounds = Bounds()
        fallback_bounds = Bounds()
        for index in range(start, end):
            segment = self.segments[index]
            flags = int(segment[SEGMENT_FLAGS])
            target_bounds = extrusion_bounds if flags & FLAG_EXTRUSION else fallback_bounds
            target_bounds.include(segment[SEGMENT_X0], segment[SEGMENT_Y0])
            target_bounds.include(segment[SEGMENT_X1], segment[SEGMENT_Y1])

        if extrusion_bounds.is_valid:
            return (extrusion_bounds, True)
        if fallback_bounds.is_valid:
            return (fallback_bounds, False)
        return (Bounds(), False)

    def visible_spatial_bounds(
        self,
        mode: RenderMode,
        current_layer: int,
        previous_layers: int,
        show_travel: bool = True,
    ) -> tuple[SpatialBounds, bool]:
        start, end = self.visible_segment_range(mode, current_layer, previous_layers)
        if start == end:
            return (SpatialBounds(), False)

        extrusion_bounds = SpatialBounds()
        fallback_bounds = SpatialBounds()
        for index in range(start, end):
            segment = self.segments[index]
            flags = int(segment[SEGMENT_FLAGS])
            if flags & FLAG_EXTRUSION:
                target_bounds = extrusion_bounds
            elif flags & FLAG_TRAVEL and show_travel:
                target_bounds = fallback_bounds
            else:
                continue
            target_bounds.include(segment[SEGMENT_X0], segment[SEGMENT_Y0], segment[SEGMENT_Z0])
            target_bounds.include(segment[SEGMENT_X1], segment[SEGMENT_Y1], segment[SEGMENT_Z])

        if extrusion_bounds.is_valid:
            return (extrusion_bounds, True)
        if fallback_bounds.is_valid:
            return (fallback_bounds, False)
        return (SpatialBounds(), False)
