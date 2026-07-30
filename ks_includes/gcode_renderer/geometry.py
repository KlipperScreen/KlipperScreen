from __future__ import annotations

import math
from dataclasses import dataclass

from .model import Bounds

DEFAULT_FIT_MARGIN = 0.08
MIN_ZOOM = 0.05
MAX_ZOOM = 1000.0


def normalize_rotation(angle_degrees: float) -> float:
    angle = float(angle_degrees) % 360.0
    if angle >= 180.0:
        angle -= 360.0
    return angle


def rotate_point(x: float, y: float, angle_degrees: float) -> tuple[float, float]:
    radians = math.radians(angle_degrees)
    cos_theta = math.cos(radians)
    sin_theta = math.sin(radians)
    return (x * cos_theta - y * sin_theta, x * sin_theta + y * cos_theta)


def rotated_bounds(bounds: Bounds, angle_degrees: float) -> Bounds:
    if not bounds or not bounds.is_valid:
        return Bounds()
    center_x = (bounds.min_x + bounds.max_x) / 2.0
    center_y = (bounds.min_y + bounds.max_y) / 2.0
    rotated = Bounds()
    for x, y in (
        (bounds.min_x, bounds.min_y),
        (bounds.min_x, bounds.max_y),
        (bounds.max_x, bounds.min_y),
        (bounds.max_x, bounds.max_y),
    ):
        rx, ry = rotate_point(x - center_x, y - center_y, angle_degrees)
        rotated.include(rx, ry)
    return rotated


def choose_fit_scale(
    bounds: Bounds,
    width: int,
    height: int,
    margin_ratio: float = DEFAULT_FIT_MARGIN,
) -> float:
    if not bounds or not bounds.is_valid or width <= 0 or height <= 0:
        return 1.0
    content_width = max(width * (1.0 - (margin_ratio * 2.0)), 1.0)
    content_height = max(height * (1.0 - (margin_ratio * 2.0)), 1.0)
    model_width = max(bounds.width, 1.0)
    model_height = max(bounds.height, 1.0)
    return min(content_width / model_width, content_height / model_height)


@dataclass(slots=True)
class ViewportState:
    scale: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    rotation_deg: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    fitted: bool = False
    user_modified: bool = False

    def fit_bounds(
        self,
        bounds: Bounds,
        width: int,
        height: int,
        margin_ratio: float = DEFAULT_FIT_MARGIN,
    ) -> None:
        if not bounds or not bounds.is_valid or width <= 0 or height <= 0:
            return
        self.center_x = (bounds.min_x + bounds.max_x) / 2.0
        self.center_y = (bounds.min_y + bounds.max_y) / 2.0
        self.scale = choose_fit_scale(rotated_bounds(bounds, self.rotation_deg), width, height, margin_ratio)
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.fitted = True
        self.user_modified = False

    def reset(self, bounds: Bounds, width: int, height: int) -> None:
        self.rotation_deg = 0.0
        self.fit_bounds(bounds, width, height)

    def zoom(self, factor: float) -> None:
        self.scale = min(max(self.scale * factor, MIN_ZOOM), MAX_ZOOM)
        self.user_modified = True
        self.fitted = False

    def pan(self, delta_x: float, delta_y: float) -> None:
        self.pan_x += delta_x
        self.pan_y += delta_y
        self.user_modified = True
        self.fitted = False

    def rotate(self, delta_degrees: float) -> None:
        self.rotation_deg = normalize_rotation(self.rotation_deg + delta_degrees)
        self.user_modified = True
        self.fitted = False

    def to_screen(self, x: float, y: float, width: int, height: int) -> tuple[float, float]:
        rx, ry = rotate_point(x - self.center_x, y - self.center_y, self.rotation_deg)
        canvas_center_x = width / 2.0
        canvas_center_y = height / 2.0
        return (
            canvas_center_x + self.pan_x + (rx * self.scale),
            canvas_center_y + self.pan_y - (ry * self.scale),
        )
