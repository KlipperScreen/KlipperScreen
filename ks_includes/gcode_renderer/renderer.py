from __future__ import annotations

from collections import OrderedDict
import logging
import math
from dataclasses import dataclass
from time import perf_counter

import gi

gi.require_version("Gtk", "3.0")
from cairo import Context as cairoContext
from gi.repository import Gtk

from .geometry import ViewportState
from .model import (
    FLAG_EXTRUSION,
    FLAG_TRAVEL,
    SEGMENT_FLAGS,
    SEGMENT_LAYER,
    SEGMENT_X0,
    SEGMENT_X1,
    SEGMENT_Y0,
    SEGMENT_Y1,
    SEGMENT_Z,
    SEGMENT_Z0,
    ProgressInfo,
    RenderMode,
    SpatialBounds,
    ToolpathModel,
)
from .preview import PreviewContext
from .projection import CameraState3D, DisplayViewMode, project_to_screen, project_to_view_plane


@dataclass(slots=True)
class PreparedGeometry:
    cache_key: tuple
    visible_indices: tuple[int, ...]
    extrusion_indices: tuple[int, ...]
    travel_indices: tuple[int, ...]
    interactive_indices: tuple[int, ...]
    visible_layers: tuple[int, ...]
    planar_bounds: object
    spatial_bounds: SpatialBounds
    used_extrusion_bounds: bool


@dataclass(frozen=True, slots=True)
class ProjectedSegment:
    index: int
    layer: int
    flags: int
    depth: float
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(slots=True)
class ProjectedScene:
    segments: tuple[ProjectedSegment, ...]
    invalid_segments: int
    min_depth: float
    max_depth: float
    sampled: bool
    source_segment_count: int


@dataclass(frozen=True, slots=True)
class ProjectionStats:
    cache_hit: bool
    projection_elapsed: float
    depth_sort_elapsed: float
    source_segment_count: int
    rendered_segment_count: int


def _vector_length(vector: tuple[float, float, float]) -> float:
    return math.sqrt((vector[0] * vector[0]) + (vector[1] * vector[1]) + (vector[2] * vector[2]))


def _has_significant_turn(
    previous: tuple[float, float, float] | None,
    current: tuple[float, float, float],
    cosine_threshold: float,
) -> bool:
    if previous is None:
        return False
    prev_length = _vector_length(previous)
    current_length = _vector_length(current)
    if prev_length <= 1e-9 or current_length <= 1e-9:
        return False
    cosine = (
        (previous[0] * current[0]) + (previous[1] * current[1]) + (previous[2] * current[2])
    ) / (prev_length * current_length)
    return cosine < cosine_threshold


def build_interaction_segment_subset(
    model: ToolpathModel,
    indices,
    *,
    target_count: int = 4000,
    sharp_turn_degrees: float = 16.0,
    significant_z_delta: float = 0.05,
) -> tuple[int, ...]:
    ordered = tuple(indices)
    if len(ordered) <= target_count:
        return ordered

    keep = {ordered[0], ordered[-1]}
    cosine_threshold = math.cos(math.radians(sharp_turn_degrees))
    step = max(int(math.ceil(len(ordered) / float(target_count))), 1)
    previous_index = None
    previous_layer = None
    previous_vector = None

    for position, index in enumerate(ordered):
        segment = model.segments[index]
        layer = int(segment[SEGMENT_LAYER])
        current_vector = (
            float(segment[SEGMENT_X1] - segment[SEGMENT_X0]),
            float(segment[SEGMENT_Y1] - segment[SEGMENT_Y0]),
            float(segment[SEGMENT_Z] - segment[SEGMENT_Z0]),
        )

        if position % step == 0:
            keep.add(index)
        if previous_layer is None or layer != previous_layer:
            keep.add(index)
            if previous_index is not None:
                keep.add(previous_index)
        if abs(current_vector[2]) >= significant_z_delta:
            keep.add(index)
            if previous_index is not None:
                keep.add(previous_index)
        if _has_significant_turn(previous_vector, current_vector, cosine_threshold):
            keep.add(index)
            if previous_index is not None:
                keep.add(previous_index)

        previous_index = index
        previous_layer = layer
        if _vector_length(current_vector) > 1e-9:
            previous_vector = current_vector

    return tuple(index for index in ordered if index in keep)


class ToolpathRenderer:
    def __init__(self):
        self._geometry_cache: dict[tuple, PreparedGeometry] = {}
        self._projection_cache: OrderedDict[tuple, ProjectedScene] = OrderedDict()
        self._selected_projection_cache: OrderedDict[tuple, ProjectedScene] = OrderedDict()
        self._selected_projection_model_key = None
        self._last_slow_render_log = 0.0
        self._last_invalid_geometry_log = 0.0

    def draw(
        self,
        da: Gtk.DrawingArea,
        ctx: cairoContext,
        model: ToolpathModel | None,
        view_mode: DisplayViewMode,
        viewport: ViewportState,
        camera: CameraState3D,
        progress: ProgressInfo | None,
        mode: RenderMode,
        previous_layers: int,
        show_travel: bool,
        message: str | None = None,
        bed_bounds: tuple[float, float, float, float] | None = None,
        drag_active: bool = False,
        preview_context: PreviewContext | None = None,
        interaction_active: bool = False,
    ) -> None:
        width = da.get_allocated_width()
        height = da.get_allocated_height()
        style_context = da.get_style_context()
        Gtk.render_background(style_context, ctx, 0, 0, width, height)
        self._draw_border(
            ctx,
            width,
            height,
            self._lookup(style_context, "borders", (0.3, 0.3, 0.3, 1.0)),
        )

        if message:
            self._draw_message(
                ctx,
                width,
                height,
                message,
                self._lookup(style_context, "text_color", (0.8, 0.8, 0.8, 1.0)),
            )
            return
        if model is None or model.segment_count == 0 or not model.bounds.is_valid:
            self._draw_message(
                ctx,
                width,
                height,
                _("No toolpath data available"),
                self._lookup(style_context, "text_color", (0.8, 0.8, 0.8, 1.0)),
            )
            return

        progress = progress or ProgressInfo()
        started = perf_counter()
        selected_file = preview_context == PreviewContext.SELECTED_FILE
        prepared = self._prepare_geometry(
            model,
            RenderMode.FULL_MODEL if selected_file else mode,
            0 if selected_file else progress.current_layer,
            0 if selected_file else previous_layers,
            False if selected_file else show_travel,
        )
        geometry_elapsed = perf_counter() - started
        if not prepared.visible_indices:
            self._draw_message(
                ctx,
                width,
                height,
                _("No toolpath data available"),
                self._lookup(style_context, "text_color", (0.8, 0.8, 0.8, 1.0)),
            )
            return

        projection_stats = None
        if selected_file and view_mode == DisplayViewMode.MODE_3D:
            projection_stats = self._draw_selected_file_3d(
                ctx,
                width,
                height,
                model,
                camera,
                prepared,
                bed_bounds,
                interaction_active,
            )
        elif selected_file:
            self._draw_selected_file_2d(
                ctx,
                width,
                height,
                model,
                viewport,
                prepared,
                interaction_active,
            )
        elif view_mode == DisplayViewMode.MODE_3D:
            projection_stats = self._draw_3d(
                ctx,
                width,
                height,
                model,
                camera,
                progress,
                prepared,
                show_travel,
                bed_bounds,
                drag_active,
            )
        else:
            self._draw_2d(ctx, width, height, model, viewport, progress, prepared)

        elapsed = perf_counter() - started
        if elapsed > 0.1 and perf_counter() - self._last_slow_render_log > 2.0:
            self._last_slow_render_log = perf_counter()
            if selected_file:
                projection_ms = projection_stats.projection_elapsed * 1000.0 if projection_stats else 0.0
                depth_ms = projection_stats.depth_sort_elapsed * 1000.0 if projection_stats else 0.0
                cache_state = "hit" if projection_stats and projection_stats.cache_hit else "miss"
                logging.warning(
                    "Slow selected-file %s render: %.0f ms geometry=%.0f ms projection=%.0f ms depth=%.0f ms "
                    "visible=%s interactive=%s final=%s cache=%s",
                    view_mode.value,
                    elapsed * 1000.0,
                    geometry_elapsed * 1000.0,
                    projection_ms,
                    depth_ms,
                    len(prepared.visible_indices),
                    len(prepared.interactive_indices),
                    len(prepared.extrusion_indices),
                    cache_state,
                )
            else:
                logging.warning(
                    "Slow G-code %s render: %.0f ms segments=%s mode=%s layer=%s",
                    view_mode.value,
                    elapsed * 1000.0,
                    len(prepared.visible_indices),
                    mode.value,
                    progress.current_layer,
                )

    def _draw_2d(
        self,
        ctx: cairoContext,
        width: int,
        height: int,
        model: ToolpathModel,
        viewport: ViewportState,
        progress: ProgressInfo,
        prepared: PreparedGeometry,
    ) -> None:
        self._draw_grid(
            ctx,
            width,
            height,
            viewport,
            prepared.planar_bounds if prepared.planar_bounds.is_valid else model.bounds,
            (0.35, 0.35, 0.35, 1.0),
        )

        current_index = progress.current_segment if progress.current_segment >= 0 else None
        current_done = []
        current_pending = []
        previous_done = []
        previous_pending = []
        travel_done = []
        travel_pending = []

        for index in prepared.extrusion_indices:
            if index == current_index:
                continue
            layer = int(model.segments[index][SEGMENT_LAYER])
            if layer == progress.current_layer:
                if index < progress.executed_segments:
                    current_done.append(index)
                else:
                    current_pending.append(index)
            else:
                if index < progress.executed_segments:
                    previous_done.append(index)
                else:
                    previous_pending.append(index)

        for index in prepared.travel_indices:
            if index == current_index:
                continue
            if index < progress.executed_segments:
                travel_done.append(index)
            else:
                travel_pending.append(index)

        self._stroke_segments_2d(ctx, model, viewport, width, height, previous_pending, (0.42, 0.42, 0.42, 0.28), 1.0)
        self._stroke_segments_2d(ctx, model, viewport, width, height, previous_done, (0.12, 0.62, 0.46, 0.32), 1.2)
        self._stroke_segments_2d(ctx, model, viewport, width, height, current_pending, (0.70, 0.70, 0.70, 0.78), 1.5)
        self._stroke_segments_2d(ctx, model, viewport, width, height, current_done, (0.12, 0.70, 0.46, 0.95), 2.0)
        self._stroke_segments_2d(
            ctx,
            model,
            viewport,
            width,
            height,
            travel_pending,
            (0.44, 0.44, 0.44, 0.26),
            0.9,
            dash=(4.0, 5.0),
        )
        self._stroke_segments_2d(
            ctx,
            model,
            viewport,
            width,
            height,
            travel_done,
            (0.32, 0.48, 0.72, 0.42),
            0.9,
            dash=(4.0, 5.0),
        )

        if current_index is not None and 0 <= current_index < model.segment_count:
            self._stroke_segments_2d(
                ctx,
                model,
                viewport,
                width,
                height,
                [current_index],
                (0.98, 0.62, 0.16, 1.0),
                2.8,
            )

        if progress.toolhead is not None:
            tool_x, tool_y, _ = progress.toolhead
            sx, sy = viewport.to_screen(tool_x, tool_y, width, height)
            ctx.set_source_rgba(0.95, 0.95, 0.95, 0.95)
            ctx.arc(sx, sy, 4.0, 0, math.tau)
            ctx.fill()

    def _draw_selected_file_2d(
        self,
        ctx: cairoContext,
        width: int,
        height: int,
        model: ToolpathModel,
        viewport: ViewportState,
        prepared: PreparedGeometry,
        interaction_active: bool,
    ) -> None:
        bounds = prepared.planar_bounds if prepared.planar_bounds.is_valid else model.bounds
        self._draw_grid(
            ctx,
            width,
            height,
            viewport,
            bounds,
            (0.35, 0.35, 0.35, 1.0),
            interactive=interaction_active,
        )
        indices = prepared.interactive_indices if interaction_active else prepared.extrusion_indices
        self._stroke_segments_2d(
            ctx,
            model,
            viewport,
            width,
            height,
            indices,
            (0.12, 0.70, 0.46, 0.95 if not interaction_active else 0.82),
            1.8 if not interaction_active else 1.25,
        )

    def _draw_3d(
        self,
        ctx: cairoContext,
        width: int,
        height: int,
        model: ToolpathModel,
        camera: CameraState3D,
        progress: ProgressInfo,
        prepared: PreparedGeometry,
        show_travel: bool,
        bed_bounds: tuple[float, float, float, float] | None,
        drag_active: bool,
    ) -> ProjectionStats:
        scene, stats = self._prepare_projected_scene(
            model,
            prepared,
            camera,
            width,
            height,
            show_travel,
            bed_bounds,
            drag_active,
        )
        if scene.invalid_segments and perf_counter() - self._last_invalid_geometry_log > 2.0:
            self._last_invalid_geometry_log = perf_counter()
            logging.warning("Skipped %s invalid 3D toolpath segments during projection", scene.invalid_segments)

        reference_bounds = bed_bounds or self._derive_bed_bounds(prepared.spatial_bounds, model.bounds)
        if reference_bounds is not None:
            self._draw_3d_bed(ctx, width, height, camera, reference_bounds)

        current_index = progress.current_segment if progress.current_segment >= 0 else None
        current_segment = None
        current_style = None

        for projected in scene.segments:
            if projected.index == current_index:
                current_segment = projected
                continue
            style = self._style_for_projected_segment(projected, progress, scene)
            if style is None:
                continue
            self._stroke_projected_segment(ctx, projected, style, current_style, width, height, camera)
            current_style = style
        if current_style is not None:
            ctx.stroke()
            ctx.set_dash([])

        if current_segment is not None:
            self._stroke_projected_highlight(ctx, current_segment, (0.98, 0.62, 0.16, 1.0), 2.8, width, height, camera)

        if progress.toolhead is not None:
            projected_tool = project_to_screen(
                progress.toolhead[0],
                progress.toolhead[1],
                progress.toolhead[2],
                camera,
                width,
                height,
            )
            if projected_tool is not None:
                ctx.set_source_rgba(0.95, 0.95, 0.95, 0.95)
                ctx.arc(projected_tool.x, projected_tool.y, 4.0, 0, math.tau)
                ctx.fill()
        return stats

    def _draw_selected_file_3d(
        self,
        ctx: cairoContext,
        width: int,
        height: int,
        model: ToolpathModel,
        camera: CameraState3D,
        prepared: PreparedGeometry,
        bed_bounds: tuple[float, float, float, float] | None,
        interaction_active: bool,
    ) -> ProjectionStats:
        projection_indices = prepared.interactive_indices if interaction_active else prepared.extrusion_indices
        scene, stats = self._prepare_projected_scene(
            model,
            prepared,
            camera,
            width,
            height,
            False,
            bed_bounds,
            interaction_active,
            preview_context=PreviewContext.SELECTED_FILE,
            projection_indices=projection_indices,
        )
        if scene.invalid_segments and perf_counter() - self._last_invalid_geometry_log > 2.0:
            self._last_invalid_geometry_log = perf_counter()
            logging.warning("Skipped %s invalid 3D toolpath segments during projection", scene.invalid_segments)

        reference_bounds = bed_bounds or self._derive_bed_bounds(prepared.spatial_bounds, model.bounds)
        if reference_bounds is not None:
            self._draw_3d_bed(ctx, width, height, camera, reference_bounds, interactive=interaction_active)

        current_style = None
        for projected in scene.segments:
            style = self._style_for_selected_projected_segment(projected, scene, sampled=interaction_active)
            self._stroke_projected_segment(ctx, projected, style, current_style, width, height, camera)
            current_style = style
        if current_style is not None:
            ctx.stroke()
            ctx.set_dash([])
        return stats

    def _prepare_geometry(
        self,
        model: ToolpathModel,
        mode: RenderMode,
        current_layer: int,
        previous_layers: int,
        show_travel: bool,
    ) -> PreparedGeometry:
        key = (id(model), model.segment_count, mode.value, current_layer, previous_layers, show_travel)
        cached = self._geometry_cache.get(key)
        if cached is not None:
            return cached

        start, end = model.visible_segment_range(mode, current_layer, previous_layers)
        visible_indices = []
        extrusion_indices = []
        travel_indices = []
        for index in range(start, end):
            segment = model.segments[index]
            flags = int(segment[SEGMENT_FLAGS])
            if flags & FLAG_EXTRUSION:
                extrusion_indices.append(index)
                visible_indices.append(index)
            elif flags & FLAG_TRAVEL and show_travel:
                travel_indices.append(index)
                visible_indices.append(index)

        planar_bounds, used_extrusion_bounds = model.visible_bounds(mode, current_layer, previous_layers)
        spatial_bounds, _ = model.visible_spatial_bounds(
            mode,
            current_layer,
            previous_layers,
            show_travel=show_travel,
        )
        interactive_indices = build_interaction_segment_subset(model, extrusion_indices)
        prepared = PreparedGeometry(
            cache_key=key,
            visible_indices=tuple(visible_indices),
            extrusion_indices=tuple(extrusion_indices),
            travel_indices=tuple(travel_indices),
            interactive_indices=interactive_indices,
            visible_layers=tuple(model.visible_layers(mode, current_layer, previous_layers)),
            planar_bounds=planar_bounds,
            spatial_bounds=spatial_bounds,
            used_extrusion_bounds=used_extrusion_bounds,
        )
        self._geometry_cache[key] = prepared
        return prepared

    def _prepare_projected_scene(
        self,
        model: ToolpathModel,
        prepared: PreparedGeometry,
        camera: CameraState3D,
        width: int,
        height: int,
        show_travel: bool,
        bed_bounds: tuple[float, float, float, float] | None,
        drag_active: bool,
        preview_context: PreviewContext | None = None,
        projection_indices: tuple[int, ...] | None = None,
    ) -> tuple[ProjectedScene, ProjectionStats]:
        selected_file = preview_context == PreviewContext.SELECTED_FILE
        indices = projection_indices if projection_indices is not None else prepared.visible_indices
        cache_key = (
            prepared.cache_key,
            len(indices),
            camera.scene_cache_key(),
            "interactive" if drag_active else "full",
        )
        if selected_file:
            self._ensure_selected_projection_cache(model, prepared)
            cached = self._selected_projection_cache.get(cache_key)
            if cached is not None:
                self._selected_projection_cache.move_to_end(cache_key)
                return (
                    cached,
                    ProjectionStats(
                        cache_hit=True,
                        projection_elapsed=0.0,
                        depth_sort_elapsed=0.0,
                        source_segment_count=cached.source_segment_count,
                        rendered_segment_count=len(cached.segments),
                    ),
                )
        else:
            cached = self._projection_cache.get(cache_key)
            if cached is not None:
                self._projection_cache.move_to_end(cache_key)
                return (
                    cached,
                    ProjectionStats(
                        cache_hit=True,
                        projection_elapsed=0.0,
                        depth_sort_elapsed=0.0,
                        source_segment_count=cached.source_segment_count,
                        rendered_segment_count=len(cached.segments),
                    ),
                )

        projected_segments = []
        invalid_segments = 0
        projection_started = perf_counter()
        for index in indices:
            segment = model.segments[index]
            start = project_to_view_plane(
                segment[SEGMENT_X0],
                segment[SEGMENT_Y0],
                segment[SEGMENT_Z0],
                camera,
            )
            end = project_to_view_plane(
                segment[SEGMENT_X1],
                segment[SEGMENT_Y1],
                segment[SEGMENT_Z],
                camera,
            )
            if start is None or end is None:
                invalid_segments += 1
                continue
            projected_segments.append(
                ProjectedSegment(
                    index=index,
                    layer=int(segment[SEGMENT_LAYER]),
                    flags=int(segment[SEGMENT_FLAGS]),
                    depth=(start.depth + end.depth) / 2.0,
                    x0=start.x,
                    y0=start.y,
                    x1=end.x,
                    y1=end.y,
                )
            )
        projection_elapsed = perf_counter() - projection_started

        depth_started = perf_counter()
        projected_segments.sort(key=lambda item: item.depth)
        depth_sort_elapsed = perf_counter() - depth_started
        min_depth = projected_segments[0].depth if projected_segments else 0.0
        max_depth = projected_segments[-1].depth if projected_segments else 0.0
        scene = ProjectedScene(
            segments=tuple(projected_segments),
            invalid_segments=invalid_segments,
            min_depth=min_depth,
            max_depth=max_depth,
            sampled=drag_active,
            source_segment_count=len(indices),
        )
        if selected_file:
            self._selected_projection_cache[cache_key] = scene
            self._selected_projection_cache.move_to_end(cache_key)
            while len(self._selected_projection_cache) > 6:
                self._selected_projection_cache.popitem(last=False)
            logging.debug(
                "Selected preview projection cache store model=%s detail=%s source=%s rendered=%s entries=%s",
                model.filename,
                "interactive" if drag_active else "full",
                len(indices),
                len(scene.segments),
                len(self._selected_projection_cache),
            )
        else:
            self._projection_cache[cache_key] = scene
            self._projection_cache.move_to_end(cache_key)
            while len(self._projection_cache) > 4:
                self._projection_cache.popitem(last=False)
        return (
            scene,
            ProjectionStats(
                cache_hit=False,
                projection_elapsed=projection_elapsed,
                depth_sort_elapsed=depth_sort_elapsed,
                source_segment_count=len(indices),
                rendered_segment_count=len(scene.segments),
            ),
        )

    def _stroke_segments_2d(
        self,
        ctx: cairoContext,
        model: ToolpathModel,
        viewport: ViewportState,
        width: int,
        height: int,
        indices,
        color: tuple[float, float, float, float],
        line_width: float,
        dash: tuple[float, float] | None = None,
    ) -> None:
        if not indices:
            return
        self._apply_viewport_transform(ctx, width, height, viewport)
        ctx.set_source_rgba(*color)
        effective_scale = max(abs(viewport.scale), 0.001)
        ctx.set_line_width(line_width / effective_scale)
        ctx.set_dash([value / effective_scale for value in dash] if dash else [])
        for index in indices:
            segment = model.segments[index]
            ctx.move_to(segment[SEGMENT_X0], segment[SEGMENT_Y0])
            ctx.line_to(segment[SEGMENT_X1], segment[SEGMENT_Y1])
        ctx.stroke()
        if dash:
            ctx.set_dash([])
        ctx.restore()

    def _draw_grid(
        self,
        ctx: cairoContext,
        width: int,
        height: int,
        viewport: ViewportState,
        bounds,
        color: tuple[float, float, float, float],
        interactive: bool = False,
    ) -> None:
        if not bounds or not bounds.is_valid or viewport.scale <= 0:
            return
        target_px = 120.0 if interactive else 80.0
        step = self._nice_step(target_px / max(viewport.scale, 0.001))
        extent_x = max(int(math.ceil(bounds.width / step)) + 4, 2)
        extent_y = max(int(math.ceil(bounds.height / step)) + 4, 2)
        max_lines = 12 if interactive else 32
        while extent_x > max_lines or extent_y > max_lines:
            step *= 2.0
            extent_x = max(int(math.ceil(bounds.width / step)) + 4, 2)
            extent_y = max(int(math.ceil(bounds.height / step)) + 4, 2)

        min_x = math.floor(bounds.min_x / step) * step
        max_x = math.ceil(bounds.max_x / step) * step
        min_y = math.floor(bounds.min_y / step) * step
        max_y = math.ceil(bounds.max_y / step) * step
        padding = step * 1.5

        self._apply_viewport_transform(ctx, width, height, viewport)
        ctx.set_source_rgba(color[0], color[1], color[2], 0.14)
        ctx.set_line_width(1.0 / max(abs(viewport.scale), 0.001))
        x = min_x
        while x <= max_x + 0.0001:
            ctx.move_to(x, min_y - padding)
            ctx.line_to(x, max_y + padding)
            x += step
        y = min_y
        while y <= max_y + 0.0001:
            ctx.move_to(min_x - padding, y)
            ctx.line_to(max_x + padding, y)
            y += step
        ctx.stroke()
        ctx.restore()

    def _draw_3d_bed(
        self,
        ctx: cairoContext,
        width: int,
        height: int,
        camera: CameraState3D,
        bed_bounds: tuple[float, float, float, float],
        interactive: bool = False,
    ) -> None:
        min_x, min_y, max_x, max_y = bed_bounds
        outline = [
            (min_x, min_y, 0.0),
            (max_x, min_y, 0.0),
            (max_x, max_y, 0.0),
            (min_x, max_y, 0.0),
            (min_x, min_y, 0.0),
        ]
        self._stroke_polyline_3d(ctx, outline, camera, width, height, (0.45, 0.45, 0.45, 0.35), 1.1)

        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        step = self._nice_step(max(span_x, span_y) / (5.0 if interactive else 8.0))
        lines_x = int(math.ceil(span_x / step))
        lines_y = int(math.ceil(span_y / step))
        max_lines = 8 if interactive else 16
        while lines_x > max_lines or lines_y > max_lines:
            step *= 2.0
            lines_x = int(math.ceil(span_x / step))
            lines_y = int(math.ceil(span_y / step))

        ctx.set_source_rgba(0.45, 0.45, 0.45, 0.12)
        ctx.set_line_width(0.9)
        x = math.floor(min_x / step) * step
        while x <= max_x + 0.0001:
            self._path_segment_3d(ctx, (x, min_y, 0.0), (x, max_y, 0.0), camera, width, height)
            x += step
        y = math.floor(min_y / step) * step
        while y <= max_y + 0.0001:
            self._path_segment_3d(ctx, (min_x, y, 0.0), (max_x, y, 0.0), camera, width, height)
            y += step
        ctx.stroke()

    def _stroke_polyline_3d(
        self,
        ctx: cairoContext,
        points,
        camera: CameraState3D,
        width: int,
        height: int,
        color: tuple[float, float, float, float],
        line_width: float,
    ) -> None:
        projected_points = []
        for point in points:
            projected = project_to_screen(point[0], point[1], point[2], camera, width, height)
            if projected is None:
                return
            projected_points.append(projected)
        if len(projected_points) < 2:
            return
        ctx.set_source_rgba(*color)
        ctx.set_line_width(line_width)
        ctx.move_to(projected_points[0].x, projected_points[0].y)
        for projected in projected_points[1:]:
            ctx.line_to(projected.x, projected.y)
        ctx.stroke()

    def _path_segment_3d(
        self,
        ctx: cairoContext,
        start: tuple[float, float, float],
        end: tuple[float, float, float],
        camera: CameraState3D,
        width: int,
        height: int,
    ) -> bool:
        projected_start = project_to_screen(start[0], start[1], start[2], camera, width, height)
        projected_end = project_to_screen(end[0], end[1], end[2], camera, width, height)
        if projected_start is None or projected_end is None:
            return False
        ctx.move_to(projected_start.x, projected_start.y)
        ctx.line_to(projected_end.x, projected_end.y)
        return True

    def _style_for_projected_segment(
        self,
        projected: ProjectedSegment,
        progress: ProgressInfo,
        scene: ProjectedScene,
    ):
        if projected.flags & FLAG_TRAVEL:
            if projected.index < progress.executed_segments:
                base_color = (0.32, 0.48, 0.72, 0.42)
            else:
                base_color = (0.44, 0.44, 0.44, 0.26)
            return self._depth_adjusted_style(base_color, 0.9, (4.0, 5.0), projected.depth, scene)

        if projected.layer == progress.current_layer:
            if projected.index < progress.executed_segments:
                base_color = (0.12, 0.70, 0.46, 0.95)
                line_width = 2.0
            else:
                base_color = (0.70, 0.70, 0.70, 0.78)
                line_width = 1.5
        else:
            if projected.index < progress.executed_segments:
                base_color = (0.12, 0.62, 0.46, 0.32)
                line_width = 1.2
            else:
                base_color = (0.42, 0.42, 0.42, 0.28)
                line_width = 1.0
        return self._depth_adjusted_style(base_color, line_width, None, projected.depth, scene)

    @staticmethod
    def _depth_adjusted_style(base_color, line_width, dash, depth: float, scene: ProjectedScene):
        depth_span = max(scene.max_depth - scene.min_depth, 1e-6)
        near_factor = (depth - scene.min_depth) / depth_span
        shade = 0.78 + (near_factor * 0.22)
        return (
            min(base_color[0] * shade, 1.0),
            min(base_color[1] * shade, 1.0),
            min(base_color[2] * shade, 1.0),
            min(max(base_color[3] * (0.82 + (near_factor * 0.18)), 0.04), 1.0),
            line_width,
            dash,
        )

    def _stroke_projected_segment(
        self,
        ctx: cairoContext,
        projected: ProjectedSegment,
        style,
        current_style,
        width: int,
        height: int,
        camera: CameraState3D,
    ) -> None:
        if current_style != style:
            if current_style is not None:
                ctx.stroke()
            ctx.set_source_rgba(style[0], style[1], style[2], style[3])
            ctx.set_line_width(style[4])
            ctx.set_dash(list(style[5]) if style[5] else [])
        x0, y0 = self._projected_to_screen(projected.x0, projected.y0, camera, width, height)
        x1, y1 = self._projected_to_screen(projected.x1, projected.y1, camera, width, height)
        ctx.move_to(x0, y0)
        ctx.line_to(x1, y1)

    @staticmethod
    def _stroke_projected_highlight(
        ctx: cairoContext,
        projected: ProjectedSegment,
        color: tuple[float, float, float, float],
        line_width: float,
        width: int,
        height: int,
        camera: CameraState3D,
    ) -> None:
        ctx.set_dash([])
        ctx.set_source_rgba(*color)
        ctx.set_line_width(line_width)
        x0, y0 = ToolpathRenderer._projected_to_screen(projected.x0, projected.y0, camera, width, height)
        x1, y1 = ToolpathRenderer._projected_to_screen(projected.x1, projected.y1, camera, width, height)
        ctx.move_to(x0, y0)
        ctx.line_to(x1, y1)
        ctx.stroke()

    def _style_for_selected_projected_segment(
        self,
        projected: ProjectedSegment,
        scene: ProjectedScene,
        *,
        sampled: bool,
    ):
        base_color = (0.12, 0.70, 0.46, 0.92 if not sampled else 0.78)
        line_width = 1.7 if not sampled else 1.2
        return self._depth_adjusted_style(base_color, line_width, None, projected.depth, scene)

    @staticmethod
    def _projected_to_screen(
        x: float,
        y: float,
        camera: CameraState3D,
        width: int,
        height: int,
    ) -> tuple[float, float]:
        return (
            (width / 2.0) + camera.pan_x + (x * camera.zoom),
            (height / 2.0) + camera.pan_y - (y * camera.zoom),
        )

    @staticmethod
    def _apply_viewport_transform(
        ctx: cairoContext,
        width: int,
        height: int,
        viewport: ViewportState,
    ) -> None:
        ctx.save()
        ctx.translate((width / 2.0) + viewport.pan_x, (height / 2.0) + viewport.pan_y)
        ctx.scale(viewport.scale, -viewport.scale)
        ctx.rotate(math.radians(viewport.rotation_deg))
        ctx.translate(-viewport.center_x, -viewport.center_y)

    def _ensure_selected_projection_cache(self, model: ToolpathModel, prepared: PreparedGeometry) -> None:
        model_key = (id(model), model.filename, model.modified, prepared.cache_key)
        if model_key == self._selected_projection_model_key:
            return
        self._selected_projection_model_key = model_key
        self._selected_projection_cache.clear()

    @staticmethod
    def _derive_bed_bounds(spatial_bounds: SpatialBounds, planar_bounds) -> tuple[float, float, float, float] | None:
        if spatial_bounds.is_valid:
            min_x = spatial_bounds.min_x
            min_y = spatial_bounds.min_y
            max_x = spatial_bounds.max_x
            max_y = spatial_bounds.max_y
        elif planar_bounds and planar_bounds.is_valid:
            min_x = planar_bounds.min_x
            min_y = planar_bounds.min_y
            max_x = planar_bounds.max_x
            max_y = planar_bounds.max_y
        else:
            return None
        padding = max(max(max_x - min_x, max_y - min_y) * 0.1, 5.0)
        return (min_x - padding, min_y - padding, max_x + padding, max_y + padding)

    @staticmethod
    def _nice_step(raw_step: float) -> float:
        if raw_step <= 0:
            return 1.0
        exponent = math.floor(math.log10(raw_step))
        fraction = raw_step / (10**exponent)
        if fraction <= 1:
            nice_fraction = 1
        elif fraction <= 2:
            nice_fraction = 2
        elif fraction <= 5:
            nice_fraction = 5
        else:
            nice_fraction = 10
        return nice_fraction * (10**exponent)

    @staticmethod
    def _draw_border(ctx: cairoContext, width: int, height: int, color: tuple[float, float, float, float]) -> None:
        ctx.set_source_rgba(*color)
        ctx.set_line_width(1.0)
        ctx.rectangle(0.5, 0.5, max(width - 1.0, 0), max(height - 1.0, 0))
        ctx.stroke()

    @staticmethod
    def _draw_message(
        ctx: cairoContext,
        width: int,
        height: int,
        message: str,
        color: tuple[float, float, float, float],
    ) -> None:
        ctx.set_source_rgba(*color)
        ctx.set_font_size(18)
        text = message[:160]
        _, _, text_width, text_height, _, _ = ctx.text_extents(text)
        ctx.move_to((width - text_width) / 2.0, (height + text_height) / 2.0)
        ctx.show_text(text)
        ctx.stroke()

    @staticmethod
    def _lookup(
        style_context: Gtk.StyleContext,
        name: str,
        fallback: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        success, color = style_context.lookup_color(name)
        if not success:
            return fallback
        return (color.red, color.green, color.blue, color.alpha)
