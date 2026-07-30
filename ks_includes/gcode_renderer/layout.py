from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ViewerLayoutSpec:
    mode: str
    controls_collapsed: bool
    controls_width: int


def get_viewer_layout_spec(width: int, height: int, vertical_mode: bool) -> ViewerLayoutSpec:
    width = max(int(width or 0), 1)
    height = max(int(height or 0), 1)

    if vertical_mode or width < int(height * 1.1):
        return ViewerLayoutSpec(
            mode="portrait",
            controls_collapsed=True,
            controls_width=_clamp(int(width * 0.72), 220, 360),
        )

    return ViewerLayoutSpec(
        mode="landscape",
        controls_collapsed=False,
        controls_width=_clamp(int(width * 0.24), 220, 320),
    )


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))
