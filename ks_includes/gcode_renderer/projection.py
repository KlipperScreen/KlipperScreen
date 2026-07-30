from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .geometry import DEFAULT_FIT_MARGIN, MAX_ZOOM, MIN_ZOOM, normalize_rotation
from .model import SpatialBounds

DEFAULT_YAW = 45.0
DEFAULT_PITCH = 35.0
MIN_PITCH = 5.0
MAX_PITCH = 85.0
DEFAULT_PERSPECTIVE_STRENGTH = 0.0


class DisplayViewMode(str, Enum):
    MODE_2D = "2d"
    MODE_3D = "3d"

    @classmethod
    def from_value(
        cls,
        value: str,
        fallback: "DisplayViewMode" = None,
    ) -> "DisplayViewMode":
        fallback = fallback or cls.MODE_2D
        try:
            return cls(value)
        except ValueError:
            return fallback


class ProjectionMode(str, Enum):
    ORTHOGRAPHIC = "orthographic"
    PERSPECTIVE = "perspective"


@dataclass(frozen=True, slots=True)
class ProjectedPoint:
    x: float
    y: float
    depth: float


@dataclass(frozen=True, slots=True)
class ProjectedBounds:
    min_x: float = float("inf")
    min_y: float = float("inf")
    max_x: float = float("-inf")
    max_y: float = float("-inf")

    @property
    def width(self) -> float:
        return 0.0 if not self.is_valid else self.max_x - self.min_x

    @property
    def height(self) -> float:
        return 0.0 if not self.is_valid else self.max_y - self.min_y

    @property
    def is_valid(self) -> bool:
        return self.min_x != float("inf") and self.min_y != float("inf")

    def include(self, x: float, y: float) -> "ProjectedBounds":
        return ProjectedBounds(
            min(self.min_x, x),
            min(self.min_y, y),
            max(self.max_x, x),
            max(self.max_y, y),
        )


def clamp_pitch(angle_degrees: float) -> float:
    return min(max(float(angle_degrees), MIN_PITCH), MAX_PITCH)


def is_finite_point(x: float, y: float, z: float) -> bool:
    return math.isfinite(x) and math.isfinite(y) and math.isfinite(z)


def rotate_yaw_pitch(
    x: float,
    y: float,
    z: float,
    yaw_degrees: float,
    pitch_degrees: float,
) -> tuple[float, float, float]:
    yaw_radians = math.radians(yaw_degrees)
    cos_yaw = math.cos(yaw_radians)
    sin_yaw = math.sin(yaw_radians)
    yaw_x = (x * cos_yaw) - (y * sin_yaw)
    yaw_y = (x * sin_yaw) + (y * cos_yaw)

    pitch_radians = math.radians(pitch_degrees)
    cos_pitch = math.cos(pitch_radians)
    sin_pitch = math.sin(pitch_radians)
    projected_y = (yaw_y * cos_pitch) + (z * sin_pitch)
    projected_z = (-yaw_y * sin_pitch) + (z * cos_pitch)
    return (yaw_x, projected_y, projected_z)


def project_to_view_plane(
    x: float,
    y: float,
    z: float,
    camera: "CameraState3D",
) -> ProjectedPoint | None:
    if not is_finite_point(x, y, z):
        return None
    rotated_x, rotated_y, depth = rotate_yaw_pitch(
        x - camera.center_x,
        y - camera.center_y,
        z - camera.center_z,
        camera.yaw,
        camera.pitch,
    )
    if camera.projection_mode == ProjectionMode.PERSPECTIVE:
        divisor = 1.0 + (depth * camera.perspective_strength)
        if not math.isfinite(divisor) or abs(divisor) < 1e-6:
            return None
        scale = 1.0 / divisor
        rotated_x *= scale
        rotated_y *= scale
    return ProjectedPoint(rotated_x, rotated_y, depth)


def project_to_screen(
    x: float,
    y: float,
    z: float,
    camera: "CameraState3D",
    width: int,
    height: int,
) -> ProjectedPoint | None:
    projected = project_to_view_plane(x, y, z, camera)
    if projected is None:
        return None
    screen_x = (width / 2.0) + camera.pan_x + (projected.x * camera.zoom)
    screen_y = (height / 2.0) + camera.pan_y - (projected.y * camera.zoom)
    if not math.isfinite(screen_x) or not math.isfinite(screen_y):
        return None
    return ProjectedPoint(screen_x, screen_y, projected.depth)


def project_bounds(
    bounds: SpatialBounds,
    camera: "CameraState3D",
) -> ProjectedBounds:
    projected_bounds = ProjectedBounds()
    for corner in bounds.corners():
        projected = project_to_view_plane(*corner, camera)
        if projected is None:
            continue
        projected_bounds = projected_bounds.include(projected.x, projected.y)
    return projected_bounds


@dataclass(slots=True)
class CameraState3D:
    yaw: float = DEFAULT_YAW
    pitch: float = DEFAULT_PITCH
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    projection_mode: ProjectionMode = ProjectionMode.ORTHOGRAPHIC
    perspective_strength: float = DEFAULT_PERSPECTIVE_STRENGTH
    fitted: bool = False
    user_modified: bool = False

    def fit_bounds(
        self,
        bounds: SpatialBounds,
        width: int,
        height: int,
        margin_ratio: float = DEFAULT_FIT_MARGIN,
    ) -> None:
        if not bounds or not bounds.is_valid or width <= 0 or height <= 0:
            return
        self.center_x = (bounds.min_x + bounds.max_x) / 2.0
        self.center_y = (bounds.min_y + bounds.max_y) / 2.0
        self.center_z = (bounds.min_z + bounds.max_z) / 2.0
        projected = project_bounds(bounds, self)
        content_width = max(width * (1.0 - (margin_ratio * 2.0)), 1.0)
        content_height = max(height * (1.0 - (margin_ratio * 2.0)), 1.0)
        span_x = max(projected.width, 1.0)
        span_y = max(projected.height, 1.0)
        self.zoom = min(max(min(content_width / span_x, content_height / span_y), MIN_ZOOM), MAX_ZOOM)
        projected_center_x = (projected.min_x + projected.max_x) / 2.0 if projected.is_valid else 0.0
        projected_center_y = (projected.min_y + projected.max_y) / 2.0 if projected.is_valid else 0.0
        self.pan_x = -(projected_center_x * self.zoom)
        self.pan_y = projected_center_y * self.zoom
        self.fitted = True
        self.user_modified = False

    def reset(self, bounds: SpatialBounds, width: int, height: int) -> None:
        self.yaw = DEFAULT_YAW
        self.pitch = DEFAULT_PITCH
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.projection_mode = ProjectionMode.ORTHOGRAPHIC
        self.perspective_strength = DEFAULT_PERSPECTIVE_STRENGTH
        self.fit_bounds(bounds, width, height)

    def zoom_by(self, factor: float) -> None:
        self.zoom = min(max(self.zoom * factor, MIN_ZOOM), MAX_ZOOM)
        self.user_modified = True
        self.fitted = False

    def pan_by(self, delta_x: float, delta_y: float) -> None:
        self.pan_x += delta_x
        self.pan_y += delta_y
        self.user_modified = True
        self.fitted = False

    def rotate_yaw(self, delta_degrees: float) -> None:
        self.yaw = normalize_rotation(self.yaw + delta_degrees)
        self.user_modified = True
        self.fitted = False

    def rotate_pitch(self, delta_degrees: float) -> None:
        self.pitch = clamp_pitch(self.pitch + delta_degrees)
        self.user_modified = True
        self.fitted = False

    def projection_cache_key(self, width: int, height: int) -> tuple:
        return (
            round(self.yaw, 4),
            round(self.pitch, 4),
            round(self.zoom, 6),
            round(self.pan_x, 4),
            round(self.pan_y, 4),
            round(self.center_x, 4),
            round(self.center_y, 4),
            round(self.center_z, 4),
            self.projection_mode.value,
            round(self.perspective_strength, 6),
            int(width),
            int(height),
        )

    def scene_cache_key(self) -> tuple:
        return (
            round(self.yaw, 4),
            round(self.pitch, 4),
            round(self.center_x, 4),
            round(self.center_y, 4),
            round(self.center_z, 4),
            self.projection_mode.value,
            round(self.perspective_strength, 6),
        )
