# -*- coding: utf-8 -*-
import logging
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from ks_includes.gcode_renderer import (
    CameraState3D,
    DisplayViewMode,
    GcodeRenderCache,
    LoadTracker,
    PreviewContext,
    RenderMode,
    ViewportState,
    get_renderer_settings,
    get_viewer_layout_spec,
    load_local_gcode,
    parse_gcode,
    resolve_preview_context,
)
from ks_includes.gcode_renderer.cache import validate_toolpath_model
from ks_includes.gcode_renderer.model import ProgressInfo
from ks_includes.gcode_renderer.loading import resolve_active_filename, should_clear_active_filename
from ks_includes.gcode_renderer.renderer import ToolpathRenderer
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    BLANKING_INHIBIT_OWNER = "gcode_preview_3d"
    INTERACTION_SETTLE_MS = 250
    ROTATE_STEP = 15.0
    YAW_DRAG_SENSITIVITY = 0.45
    PITCH_DRAG_SENSITIVITY = 0.35
    DRAG_ROTATE = "rotate"
    DRAG_PAN = "pan"

    def __init__(
        self,
        screen,
        title=None,
        filename=None,
        preview_context=None,
        **kwargs,
    ):
        title = title or _("Toolpath")
        super().__init__(screen, title)
        if kwargs:
            logging.debug(
                "Ignoring unknown gcode_viewer panel kwargs: %s",
                ", ".join(sorted(kwargs)),
            )
        self.buttons = {}
        self.explicit_filename = filename or ""
        self.preview_context = resolve_preview_context(
            preview_context,
            self.explicit_filename,
            default_active_print=True,
        )
        self.filename = self.explicit_filename if self.preview_context == PreviewContext.SELECTED_FILE else ""
        self.file_metadata = {}
        self.metadata_requested_for = ""
        self.model = None
        self.progress = ProgressInfo()
        self.viewport = ViewportState()
        self.camera_3d = CameraState3D()
        self.renderer = ToolpathRenderer()
        self.cache = GcodeRenderCache()
        self.load_tracker = LoadTracker(panel_active=True)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ks-gcode-preview")
        self.drag_state = None
        self.panel_active = False
        self.render_dirty = True
        self.refresh_timer = None
        self.print_state = "standby"
        self.panel_state = "idle"
        self.render_message = _("No preview loaded")
        self.enabled = False
        self.refresh_interval = 5
        self.show_travel = False
        self.previous_layers = 3
        self.render_mode = RenderMode.CURRENT_LAYER
        self.view_mode = DisplayViewMode.MODE_2D
        self.drag_mode_3d = self.DRAG_ROTATE
        self.layout_spec = None
        self.last_progress_signature = None
        self.last_canvas_size = (0, 0)
        self.bed_bounds = None
        self.pending_load_result = None
        self._active_print_session_show_travel = None
        self._context_display_state = {}
        self._interaction_restore_timer = None
        self._interaction_active = False
        self.content_margin = max(int(self._gtk.font_size * 0.30), 6)
        self.controls_spacing = max(int(self._gtk.font_size * 0.22), 6)

        self.status_card_title = Gtk.Label(wrap=True, xalign=0.5, justify=Gtk.Justification.CENTER)
        self.status_card_detail = Gtk.Label(wrap=True, xalign=0.5, justify=Gtk.Justification.CENTER)
        self.loading_spinner = Gtk.Spinner(halign=Gtk.Align.CENTER)

        self.canvas = None
        self.canvas_overlay = None
        self.status_card = None
        self.main_layout = None
        self.canvas_column = None
        self.controls_panel = None
        self.controls_scroller = None
        self.controls_revealer = None
        self.controls_toggle_button = None
        self.portrait_toolbar = None
        self.mode_button = None
        self.travel_button = None
        self.retry_button = None
        self.rotate_left_button = None
        self.rotate_right_button = None
        self.drag_mode_box = None
        self.view_mode_box = None
        self.view_buttons = {}
        self.drag_buttons = {}

        self._build_canvas_area()
        self._build_controls_panel()
        self.main_layout = Gtk.Box(spacing=self.content_margin)
        self.main_layout.set_hexpand(True)
        self.main_layout.set_vexpand(True)
        self.content.add(self.main_layout)
        self.content.connect("destroy", self._on_content_destroy)

        self.content.connect("size-allocate", self._on_content_size_allocate)
        self._sync_settings()
        self._apply_responsive_layout(self._screen.width, self._screen.height, force=True)
        if self.enabled:
            self._set_panel_state("idle", _("No active print file"))
        else:
            self._set_panel_state("disabled", _("Enable G-code renderer in Settings"))
        logging.debug(
            "G-code viewer panel initialized enabled=%s mode=%s view=%s fps=%s show_travel=%s previous_layers=%s",
            self.enabled,
            self.render_mode.value,
            self.view_mode.value,
            self.refresh_interval,
            self.show_travel,
            self.previous_layers,
        )

    def activate(self):
        self.panel_active = True
        preview_context = self._get_preview_context()
        resolved_filename = self._resolved_context_filename()
        logging.info(
            "G-code viewer activate context=%s filename=%s resolved=%s load_in_progress=%s panel_active=%s",
            preview_context.value if preview_context else "idle",
            self.filename or "",
            resolved_filename or "",
            self.load_tracker.load_in_progress,
            self.load_tracker.panel_active,
        )
        self.load_tracker.activate(resolved_filename or self.filename)
        self.bed_bounds = self._resolve_bed_reference_bounds()
        self._sync_settings()
        self._sync_blanking_inhibition()
        self._apply_responsive_layout(self._screen.width, self._screen.height)
        if self.refresh_timer is None:
            interval = max(int(1000 / self.refresh_interval), 100)
            self.refresh_timer = GLib.timeout_add(interval, self._refresh_canvas)
        self._refresh_from_printer()

    def deactivate(self):
        self.panel_active = False
        self._cancel_interaction_quality_restore()
        self._release_blanking_inhibition()
        self.load_tracker.deactivate()
        if self.refresh_timer is not None:
            GLib.source_remove(self.refresh_timer)
            self.refresh_timer = None
        if self.controls_revealer is not None:
            self.controls_revealer.set_reveal_child(False)
        self.drag_state = None

    def on_draw(self, da, ctx):
        try:
            if (
                self._get_preview_context() == PreviewContext.SELECTED_FILE
                and self.view_mode == DisplayViewMode.MODE_3D
            ):
                self._draw_selected_file_3d_frame(da, ctx)
            else:
                self._draw_renderer_frame(da, ctx)
        except Exception as exc:
            if self.view_mode != DisplayViewMode.MODE_3D:
                raise
            self._draw_3d_error_fallback(da, ctx, exc)

    def _draw_renderer_frame(
        self,
        da,
        ctx,
        *,
        view_mode=None,
        drag_active=None,
        interaction_active=None,
    ):
        resolved_view_mode = self.view_mode if view_mode is None else view_mode
        resolved_drag_active = (
            self.view_mode == DisplayViewMode.MODE_3D and getattr(self, "drag_state", None) is not None
            if drag_active is None
            else drag_active
        )
        resolved_interaction_active = (
            self._interaction_active if interaction_active is None else interaction_active
        )
        self.renderer.draw(
            da,
            ctx,
            self.model,
            resolved_view_mode,
            self.viewport,
            self.camera_3d,
            self.progress,
            self.render_mode,
            self.previous_layers,
            self.show_travel,
            self.render_message,
            bed_bounds=self.bed_bounds,
            drag_active=resolved_drag_active,
            preview_context=self._get_preview_context(),
            interaction_active=resolved_interaction_active,
        )

    def _draw_selected_file_3d_frame(self, da, ctx):
        self._draw_renderer_frame(
            da,
            ctx,
            view_mode=DisplayViewMode.MODE_3D,
            drag_active=getattr(self, "drag_state", None) is not None,
            interaction_active=self._interaction_active,
        )

    def _draw_3d_error_fallback(self, da, ctx, exc):
        preview_context = self._get_preview_context()
        model = getattr(self, "model", None)
        filename = getattr(self, "filename", "") or getattr(self, "explicit_filename", "")
        logging.error(
            "3D G-code preview draw failed context=%s filename=%s segments=%s size=%sx%s view=%s interaction=%s",
            preview_context.value if preview_context else "idle",
            filename,
            getattr(model, "segment_count", 0) if model is not None else 0,
            da.get_allocated_width(),
            da.get_allocated_height(),
            self.view_mode.value,
            self._interaction_active,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        try:
            self._draw_renderer_frame(
                da,
                ctx,
                view_mode=DisplayViewMode.MODE_2D,
                drag_active=False,
                interaction_active=False,
            )
        except Exception:
            logging.exception("Emergency 2D draw fallback failed after 3D preview error")
            self._draw_3d_error_overlay(ctx, da.get_allocated_width(), da.get_allocated_height(), base_only=True)
            return
        self._draw_3d_error_overlay(ctx, da.get_allocated_width(), da.get_allocated_height())

    def _draw_3d_error_overlay(self, ctx, width, height, base_only=False):
        ctx.save()
        if base_only:
            ctx.set_source_rgba(0.10, 0.10, 0.10, 1.0)
            ctx.rectangle(0, 0, width, height)
            ctx.fill()
        card_width = min(max(width * 0.72, 240.0), max(width - 24.0, 32.0))
        card_height = min(max(height * 0.20, 72.0), max(height - 24.0, 32.0))
        card_x = max((width - card_width) / 2.0, 12.0)
        card_y = max(height - card_height - 12.0, 12.0)
        ctx.set_source_rgba(0.06, 0.06, 0.06, 0.72)
        ctx.rectangle(card_x, card_y, card_width, card_height)
        ctx.fill()
        ctx.set_source_rgba(0.95, 0.95, 0.95, 0.95)
        ctx.select_font_face("Sans", 0, 0)
        ctx.set_font_size(max(min(width, height) * 0.035, 14.0))
        message = _("Unable to load G-code preview")
        extents = ctx.text_extents(message)
        text_x = card_x + max((card_width - extents.width) / 2.0 - extents.x_bearing, 12.0)
        text_y = card_y + max((card_height + extents.height) / 2.0, 28.0)
        ctx.move_to(text_x, text_y)
        ctx.show_text(message)
        ctx.restore()

    def on_press(self, widget, event):
        self.drag_state = (event.x, event.y)
        return True

    def on_release(self, widget, event):
        self.drag_state = None
        self._schedule_interaction_quality_restore()
        self.queue_render()
        return True

    def on_motion(self, widget, event):
        if self.drag_state is None or self.model is None:
            return False
        prev_x, prev_y = self.drag_state
        self.drag_state = (event.x, event.y)
        delta_x = event.x - prev_x
        delta_y = event.y - prev_y
        if self.view_mode == DisplayViewMode.MODE_3D:
            if self.drag_mode_3d == self.DRAG_PAN:
                self.camera_3d.pan_by(delta_x, delta_y)
            else:
                self.camera_3d.rotate_yaw(delta_x * self.YAW_DRAG_SENSITIVITY)
                self.camera_3d.rotate_pitch(-delta_y * self.PITCH_DRAG_SENSITIVITY)
        else:
            self.viewport.pan(delta_x, delta_y)
        self._begin_interaction_render()
        self.queue_render()
        return True

    def zoom(self, widget, factor):
        if self.model is None:
            return
        if self.view_mode == DisplayViewMode.MODE_3D:
            self.camera_3d.zoom_by(factor)
            logging.debug("G-code viewer 3D zoom changed zoom=%.4f", self.camera_3d.zoom)
        else:
            self.viewport.zoom(factor)
            logging.debug("G-code viewer 2D zoom changed scale=%.4f", self.viewport.scale)
        self._begin_interaction_render()
        self.queue_render()

    def fit_view(self, widget=None):
        self._fit_view_to_model(force=True)
        self.queue_render()

    def reset_view(self, widget):
        if self.model is None:
            return
        width = self.canvas.get_allocated_width()
        height = self.canvas.get_allocated_height()
        if width <= 1 or height <= 1:
            return
        if self.view_mode == DisplayViewMode.MODE_3D:
            bounds, used_extrusion = self._visible_spatial_bounds()
            self.camera_3d.reset(bounds, width, height)
            self._log_spatial_fit_details(bounds, used_extrusion, reset=True)
        else:
            bounds, used_extrusion = self._visible_planar_bounds()
            self.viewport.reset(bounds, width, height)
            self._log_planar_fit_details(bounds, used_extrusion, reset=True)
        self.queue_render()

    def rotate_left(self, widget):
        self._rotate_view(-self.ROTATE_STEP)

    def rotate_right(self, widget):
        self._rotate_view(self.ROTATE_STEP)

    def cycle_mode(self, widget):
        if not self._context_allows_mode_control():
            return
        order = [
            RenderMode.CURRENT_LAYER,
            RenderMode.CURRENT_AND_PREVIOUS,
            RenderMode.FULL_MODEL,
        ]
        index = order.index(self.render_mode) if self.render_mode in order else 0
        self.render_mode = order[(index + 1) % len(order)]
        self._config.set("main", "gcode_renderer_mode", self.render_mode.value)
        self._config.save_user_config_options()
        self._update_control_labels()
        self._fit_view_to_model(force=True)
        self.queue_render()

    def set_view_mode(self, widget, target_mode):
        if target_mode == self.view_mode:
            return
        self.view_mode = target_mode
        self._config.set("main", "gcode_renderer_view", self.view_mode.value)
        self._config.save_user_config_options()
        if self.model is not None:
            if self.view_mode == DisplayViewMode.MODE_3D and not self.camera_3d.fitted:
                self._fit_view_to_model(force=True)
            elif self.view_mode == DisplayViewMode.MODE_2D and not self.viewport.fitted:
                self._fit_view_to_model(force=True)
        self._update_control_labels()
        self._sync_blanking_inhibition()
        self.queue_render()

    def set_drag_mode(self, widget, drag_mode):
        if drag_mode == self.drag_mode_3d:
            return
        self.drag_mode_3d = drag_mode
        self._update_control_labels()

    def toggle_travel(self, widget):
        if not self._context_allows_travel_control():
            return
        self.show_travel = not self.show_travel
        if self._get_preview_context() == PreviewContext.ACTIVE_PRINT:
            self._active_print_session_show_travel = self.show_travel
        self._config.set("main", "gcode_renderer_show_travel", str(self.show_travel))
        self._config.save_user_config_options()
        self._update_control_labels()
        self.queue_render()

    def retry_load(self, widget):
        self._load_tracker_reset_for_retry()
        self._schedule_load(force_reload=True)

    def toggle_controls(self, widget=None):
        if self.layout_spec is None or self.layout_spec.mode != "portrait":
            return
        self.controls_revealer.set_reveal_child(not self.controls_revealer.get_reveal_child())

    def process_update(self, action, data):
        if action == "notify_metadata_update" and data.get("filename") == self.filename:
            previous_key = self._metadata_key(self.file_metadata)
            if self._files.file_metadata_exists(self.filename):
                self.file_metadata = self._files.get_file_info(self.filename)
                self.metadata_requested_for = ""
            if self._metadata_key(self.file_metadata) != previous_key:
                logging.info("G-code renderer metadata changed, reloading %s", self.filename)
                self.model = None
                self.viewport.fitted = False
                self.camera_3d.fitted = False
                self.load_tracker.invalidate()
                self._schedule_load(force_reload=True)
            return
        if action != "notify_status_update":
            return
        self._refresh_from_printer(data)

    def _refresh_from_printer(self, data=None):
        preview_context = self._get_preview_context()
        self.print_state = self._printer.get_stat("print_stats", "state") or "standby"
        self._sync_settings(sync_view_mode=False)
        self._sync_blanking_inhibition()

        if not self.enabled:
            self.model = None
            self.render_message = _("Feature disabled")
            self._cancel_interaction_quality_restore()
            self._set_panel_state("disabled", _("Enable G-code renderer in Settings"))
            self.queue_render()
            return

        if preview_context == PreviewContext.ACTIVE_PRINT:
            self._refresh_active_print_context(data)
            return
        if preview_context == PreviewContext.SELECTED_FILE:
            self._refresh_selected_file_context()
            return

        self.filename = ""
        self.model = None
        self.render_message = _("No file selected")
        self._set_panel_state("idle", _("Open Preview from the file list"))
        self.queue_render()

    def _refresh_active_print_context(self, data=None):
        printer_filename = self._printer.get_stat("print_stats", "filename") or ""
        resolved_filename = self._resolve_active_filename(printer_filename, data=data)
        logging.info(
            "G-code viewer active_print refresh printer_filename=%s resolved_filename=%s current_filename=%s print_state=%s",
            printer_filename or "",
            resolved_filename or "",
            self.filename or "",
            self.print_state,
        )
        if resolved_filename and resolved_filename != self.filename:
            logging.info(
                "G-code viewer switching preview file from %s to %s",
                self.filename or "",
                resolved_filename,
            )
            self.filename = resolved_filename
            self._reset_loaded_model(invalidate_tracker=True)
        elif should_clear_active_filename(self.filename, resolved_filename, self.print_state):
            logging.info(
                "G-code viewer clearing preview filename after confirmed reset state=%s previous=%s",
                self.print_state,
                self.filename,
            )
            self.filename = ""
            self._reset_loaded_model(invalidate_tracker=True)
        else:
            self.filename = resolved_filename

        if not self.filename:
            self.model = None
            self.render_message = _("No file selected")
            self._set_panel_state("idle", _("Open Preview while a print is active"))
            self.queue_render()
            return

        self._refresh_metadata()
        if self.model is None:
            if self._apply_pending_load_result():
                changed = self._update_progress()
                self._set_panel_state("ready")
                if changed:
                    self.queue_render()
                return
            self._schedule_load()
            return

        changed = self._update_progress()
        self._set_panel_state("ready")
        if changed:
            self.queue_render()

    def _refresh_selected_file_context(self):
        target_filename = self.explicit_filename or ""
        if target_filename != self.filename:
            self.filename = target_filename
            self._reset_loaded_model(invalidate_tracker=True)
        else:
            self.filename = target_filename
        logging.info(
            "G-code viewer selected_file refresh explicit_filename=%s current_filename=%s print_state=%s",
            self.explicit_filename or "",
            self.filename or "",
            self.print_state,
        )
        if not self.filename:
            self.model = None
            self.render_message = _("No file selected")
            self._set_panel_state("idle", _("Open Preview from the file list"))
            self.queue_render()
            return

        self._refresh_metadata()
        if self.model is None:
            if self._apply_pending_load_result():
                changed = self._update_progress()
                self._set_panel_state("ready")
                if changed:
                    self.queue_render()
                return
            self._schedule_load()
            return

        changed = self._update_progress()
        self._set_panel_state("ready")
        if changed:
            self.queue_render()

    def _schedule_load(self, force_reload=False):
        generation = self.load_tracker.begin(self.filename, force_reload=force_reload)
        if generation is None:
            logging.info(
                "G-code viewer skipped load filename=%s force_reload=%s load_in_progress=%s active=%s",
                self.filename or "",
                force_reload,
                self.load_tracker.load_in_progress,
                self.load_tracker.panel_active,
            )
            return

        filename = self.filename
        metadata = dict(self.file_metadata)
        logging.info(
            "G-code viewer load worker submitted filename=%s generation=%s size=%s modified=%s active=%s",
            filename,
            generation,
            metadata.get("size", 0) or 0,
            metadata.get("modified", 0.0) or 0.0,
            self.load_tracker.panel_active,
        )
        self.render_message = _("Loading G-code preview...")
        self._set_panel_state("loading")
        self.queue_render()

        def _worker():
            started = perf_counter()
            file_size = int(metadata.get("size", 0) or 0)
            modified = float(metadata.get("modified", 0.0) or 0.0)
            cache_entry = (
                self.cache.make_entry(filename, file_size, modified) if file_size > 0 else None
            )

            if cache_entry is not None and not force_reload:
                cached = self.cache.load(cache_entry)
                if cached is not None:
                    logging.info(
                        "G-code viewer load source=cache filename=%s generation=%s segment_count=%s layer_count=%s",
                        filename,
                        generation,
                        cached.segment_count,
                        cached.total_layers,
                    )
                    logging.info(
                        "G-code renderer ready from cache: %s in %.2fs",
                        filename,
                        perf_counter() - started,
                    )
                    return {"source": "cache", "model": cached}

            source = "Moonraker REST"
            local = load_local_gcode(self._files.gcodes_path, filename)
            if local is not None:
                source = "local file"
                local_path, payload = local
                logging.info(
                    "G-code viewer load local path=%s filename=%s bytes=%s",
                    local_path,
                    filename,
                    len(payload),
                )
            else:
                logging.info("G-code viewer load using REST fallback filename=%s", filename)
                payload = self._screen.restApi.get_gcode_stream(filename, timeout=60)
                if payload is False:
                    raise RuntimeError("REST download failed")
                logging.info(
                    "G-code viewer load REST payload filename=%s bytes=%s",
                    filename,
                    len(payload),
                )

            file_size = file_size or len(payload)
            logging.info(
                "G-code viewer parse start filename=%s generation=%s total_bytes=%s",
                filename,
                generation,
                len(payload),
            )
            parse_started = perf_counter()
            model = parse_gcode(payload, filename, file_size=file_size, modified=modified)
            parse_elapsed = perf_counter() - parse_started
            is_valid, reason = validate_toolpath_model(model)
            logging.info(
                "G-code viewer parse finish filename=%s generation=%s segment_count=%s layer_count=%s valid=%s reason=%s",
                filename,
                generation,
                model.segment_count,
                model.total_layers,
                is_valid,
                reason,
            )
            if not is_valid:
                raise RuntimeError(f"Parsed model validation failed: {reason}")
            if cache_entry is None and file_size > 0:
                cache_entry = self.cache.make_entry(filename, file_size, modified)
            if cache_entry is not None:
                self.cache.save(cache_entry, model)
                logging.info(
                    "G-code viewer cache save filename=%s fingerprint=%s",
                    filename,
                    cache_entry.fingerprint,
                )
            logging.info(
                "G-code renderer parsed %s from %s in %.2fs (parse %.2fs)",
                filename,
                source,
                perf_counter() - started,
                parse_elapsed,
            )
            return {"source": source, "model": model}

        def _complete(future):
            exc = future.exception()
            if exc is not None:
                logging.info(
                    "G-code viewer future completion error filename=%s generation=%s",
                    filename,
                    generation,
                )
                GLib.idle_add(self._handle_load_error, generation, filename, exc)
                return
            logging.info(
                "G-code viewer future completion filename=%s generation=%s",
                filename,
                generation,
            )
            GLib.idle_add(self._finish_load, generation, filename, future.result())

        future = self.executor.submit(_worker)
        future.add_done_callback(_complete)

    def _finish_load(self, generation, filename, result):
        decision = self.load_tracker.finish(generation, filename)
        logging.info(
            "G-code viewer finish load filename=%s generation=%s decision=%s",
            filename,
            generation,
            decision,
        )
        if decision == "inactive":
            self.pending_load_result = (generation, filename, result)
            logging.info("G-code viewer retained inactive result for %s", filename)
            return False
        if decision != "accepted":
            logging.debug("Discarding G-code renderer result for %s (%s)", filename, decision)
            return False

        model = result["model"]
        is_valid, reason = validate_toolpath_model(model)
        if not is_valid:
            logging.error("G-code renderer rejected loaded model for %s: %s", filename, reason)
            self.model = None
            self.render_message = _("Unable to load G-code preview")
            self._set_panel_state("error")
            self.queue_render()
            return False
        self.model = model
        self.pending_load_result = None
        if self._files.file_metadata_exists(filename):
            self.file_metadata = self._files.get_file_info(filename)
            self.metadata_requested_for = ""
        self.last_progress_signature = None
        self.viewport.fitted = False
        self.camera_3d.fitted = False
        self._update_progress()
        self._fit_view_to_model(force=True)
        if model.segment_count:
            self.render_message = None
            self._set_panel_state("ready", result["source"])
        else:
            self.render_message = _("No renderable toolpath found")
            self._set_panel_state("empty")
        self.queue_render()
        return False

    def _handle_load_error(self, generation, filename, exc):
        decision = self.load_tracker.finish(generation, filename)
        logging.info(
            "G-code viewer finish error filename=%s generation=%s decision=%s",
            filename,
            generation,
            decision,
        )
        if decision != "accepted":
            logging.debug("Discarding G-code renderer error for %s (%s)", filename, decision)
            return False

        logging.error("G-code renderer load failure for %s: %s", filename, exc)
        self.model = None
        self.render_message = _("Unable to load G-code preview")
        self._set_panel_state("error")
        self.queue_render()
        return False

    def _update_progress(self):
        if self.model is None:
            return False
        if self._get_preview_context() == PreviewContext.SELECTED_FILE:
            file_position = (
                self.model.segment_end_offsets[-1]
                if self.model.segment_end_offsets
                else self.model.total_bytes
            )
            new_progress = self.model.progress_for_offset(
                file_position=file_position,
                print_state=self.print_state,
            )
        else:
            file_position = int(self._printer.get_stat("virtual_sdcard", "file_position") or 0)
            toolhead = None
            live_position = self._printer.get_stat("motion_report", "live_position")
            if live_position and len(live_position) >= 3:
                toolhead = (live_position[0], live_position[1], live_position[2])
            new_progress = self.model.progress_for_offset(
                file_position=file_position,
                print_state=self.print_state,
                toolhead=toolhead,
            )
        signature = (
            new_progress.current_segment,
            new_progress.executed_segments,
            new_progress.current_layer,
            new_progress.toolhead,
            new_progress.print_state,
        )
        changed = signature != self.last_progress_signature
        self.progress = new_progress
        self.last_progress_signature = signature
        return changed

    def _update_control_labels(self):
        mode_labels = {
            RenderMode.CURRENT_LAYER: _("Current"),
            RenderMode.CURRENT_AND_PREVIOUS: _("Current + Prev"),
            RenderMode.FULL_MODEL: _("Full Model"),
        }
        self.mode_button.set_label(mode_labels[self.render_mode])
        self.travel_button.set_label(_("Travel On") if self.show_travel else _("Travel Off"))
        self._sync_context_display_controls()
        self._set_button_selected(self.view_buttons[DisplayViewMode.MODE_2D], self.view_mode == DisplayViewMode.MODE_2D)
        self._set_button_selected(self.view_buttons[DisplayViewMode.MODE_3D], self.view_mode == DisplayViewMode.MODE_3D)
        show_drag_modes = self.view_mode == DisplayViewMode.MODE_3D
        self.drag_mode_box.set_visible(show_drag_modes)
        self._set_button_selected(self.drag_buttons[self.DRAG_ROTATE], self.drag_mode_3d == self.DRAG_ROTATE)
        self._set_button_selected(self.drag_buttons[self.DRAG_PAN], self.drag_mode_3d == self.DRAG_PAN)

    def _refresh_canvas(self):
        if self.render_dirty:
            self.canvas.queue_draw()
            self.render_dirty = False
        return True

    def queue_render(self):
        self.render_dirty = True

    def _refresh_metadata(self):
        if self._files.file_metadata_exists(self.filename):
            self.file_metadata = self._files.get_file_info(self.filename)
            self.metadata_requested_for = ""
            return
        if self.metadata_requested_for != self.filename:
            self.metadata_requested_for = self.filename
            logging.debug("Requesting metadata for %s", self.filename)
            self._files.request_metadata(self.filename)

    def _set_panel_state(self, state, detail=None):
        self.panel_state = state
        self.retry_button.set_visible(state == "error")
        self.retry_button.set_sensitive(state == "error")

        show_status_card = state != "ready"
        self.status_card.set_visible(show_status_card)
        spinner_visible = state == "loading"
        self.loading_spinner.set_visible(spinner_visible)
        if spinner_visible:
            self.loading_spinner.start()
        else:
            self.loading_spinner.stop()

        if state == "disabled":
            title = _("Feature disabled")
            detail = detail or _("Enable G-code renderer in Settings")
            self.render_message = _("Feature disabled")
        elif state == "idle":
            title = _("No active print file")
            detail = detail or _("Open Preview while a print is active")
            self.render_message = _("No file selected")
        elif state == "loading":
            title = _("Loading G-code preview...")
            detail = _("This can take a moment for large files")
        elif state == "ready":
            title = ""
            self.render_message = None if self.model and self.model.segment_count else self.render_message
        elif state == "empty":
            title = _("No renderable toolpath found")
            detail = detail or _("This file does not contain previewable motion")
            self.render_message = _("No renderable toolpath found")
        elif state == "error":
            title = _("Unable to load G-code preview")
            detail = detail or _("Retry or check renderer settings")
            self.render_message = _("Unable to load G-code preview")
        else:
            title = _("Toolpath")
            detail = detail or ""

        self.status_card_title.set_label(title)
        self.status_card_detail.set_label(detail or "")

    def _sync_settings(self, sync_view_mode=True):
        settings = get_renderer_settings(self._config.get_main_config(), logging.getLogger(__name__))
        self.enabled = settings.enabled
        if sync_view_mode:
            self.view_mode = settings.view
        self.refresh_interval = settings.fps
        self.previous_layers = settings.previous_layers
        self._apply_context_display_state(self._resolve_context_display_state(settings))
        if self.mode_button is not None and self.travel_button is not None:
            self._update_control_labels()

    def _resolve_context_display_state(self, settings):
        preview_context = self._get_preview_context()
        if preview_context == PreviewContext.SELECTED_FILE:
            return {
                "show_travel": False,
                "render_mode": RenderMode.FULL_MODEL,
                "show_travel_control": False,
                "show_mode_control": False,
            }

        show_travel = settings.show_travel
        if preview_context == PreviewContext.ACTIVE_PRINT:
            show_travel = True if self._active_print_session_show_travel is None else self._active_print_session_show_travel
        return {
            "show_travel": show_travel,
            "render_mode": settings.mode,
            "show_travel_control": preview_context == PreviewContext.ACTIVE_PRINT,
            "show_mode_control": preview_context == PreviewContext.ACTIVE_PRINT,
        }

    def _apply_context_display_state(self, state):
        self._context_display_state = dict(state)
        self.show_travel = bool(state["show_travel"])
        self.render_mode = state["render_mode"]
        if self._get_preview_context() != PreviewContext.SELECTED_FILE:
            self._cancel_interaction_quality_restore()
        self._sync_context_display_controls()

    def _sync_context_display_controls(self):
        if self.mode_button is None or self.travel_button is None:
            return
        self.mode_button.set_visible(bool(self._context_display_state.get("show_mode_control", True)))
        self.travel_button.set_visible(bool(self._context_display_state.get("show_travel_control", True)))

    def _context_allows_mode_control(self):
        return bool(self._context_display_state.get("show_mode_control", True))

    def _context_allows_travel_control(self):
        return bool(self._context_display_state.get("show_travel_control", True))

    def _load_tracker_reset_for_retry(self):
        self.load_tracker.invalidate()
        self._reset_loaded_model(invalidate_tracker=False)

    def _resolved_context_filename(self, printer_filename=None, data=None) -> str:
        preview_context = self._get_preview_context()
        if preview_context == PreviewContext.SELECTED_FILE:
            return self.explicit_filename or ""
        if preview_context == PreviewContext.ACTIVE_PRINT:
            return self._resolve_active_filename(printer_filename, data=data)
        return ""

    def _get_preview_context(self):
        preview_context = getattr(self, "preview_context", None)
        explicit_filename = getattr(self, "explicit_filename", "")
        return resolve_preview_context(
            preview_context.value if isinstance(preview_context, PreviewContext) else preview_context,
            explicit_filename,
            default_active_print=True,
        )

    def _resolve_active_filename(self, printer_filename=None, data=None) -> str:
        virtual_sdcard_status = data.get("virtual_sdcard") if isinstance(data, dict) else None
        if virtual_sdcard_status is None:
            virtual_sdcard_status = self._printer.get_stat("virtual_sdcard")
        return resolve_active_filename(
            printer_filename=printer_filename,
            explicit_filename=self.explicit_filename,
            current_filename=self.filename,
            virtual_sdcard_status=virtual_sdcard_status,
        )

    def _reset_loaded_model(self, invalidate_tracker=True):
        if invalidate_tracker:
            self.load_tracker.invalidate()
        self.file_metadata = {}
        self.metadata_requested_for = ""
        self.model = None
        self.progress = ProgressInfo()
        self.viewport.fitted = False
        self.camera_3d.fitted = False
        self.last_progress_signature = None
        self.pending_load_result = None
        self._cancel_interaction_quality_restore()

    def _apply_pending_load_result(self):
        if self.pending_load_result is None:
            return False
        generation, filename, result = self.pending_load_result
        if filename != self.filename:
            self.pending_load_result = None
            return False
        logging.info(
            "G-code viewer applying retained inactive result filename=%s generation=%s",
            filename,
            generation,
        )
        self.load_tracker.activate(filename)
        had_model = self.model is not None
        self._finish_load(generation, filename, result)
        return self.model is not None or (not had_model and result["model"].segment_count == 0)

    def _build_canvas_area(self):
        self.canvas = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.canvas.connect("draw", self.on_draw)
        self.canvas.connect("size-allocate", self._on_canvas_size_allocate)
        self.canvas.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.BUTTON1_MOTION_MASK
        )
        self.canvas.connect("button-press-event", self.on_press)
        self.canvas.connect("button-release-event", self.on_release)
        self.canvas.connect("motion-notify-event", self.on_motion)
        self.labels["canvas"] = self.canvas

        self.canvas_overlay = Gtk.Overlay(hexpand=True, vexpand=True)
        self.canvas_overlay.add(self.canvas)

        self.status_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.status_card.set_halign(Gtk.Align.CENTER)
        self.status_card.set_valign(Gtk.Align.CENTER)
        self.status_card.set_margin_start(self.content_margin * 2)
        self.status_card.set_margin_end(self.content_margin * 2)
        self.status_card.set_margin_top(self.content_margin * 2)
        self.status_card.set_margin_bottom(self.content_margin * 2)
        self.status_card.get_style_context().add_class("frame-item")

        self.retry_button = self._make_compact_button(None, _("Retry"), "color1")
        self.retry_button.connect("clicked", self.retry_load)
        self.retry_button.set_visible(False)

        self.status_card.add(self.loading_spinner)
        self.status_card.add(self.status_card_title)
        self.status_card.add(self.status_card_detail)
        self.status_card.add(self.retry_button)
        self.canvas_overlay.add_overlay(self.status_card)
        self.canvas_overlay.set_overlay_pass_through(self.status_card, False)

        self.canvas_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.canvas_column.set_hexpand(True)
        self.canvas_column.set_vexpand(True)
        self.canvas_column.pack_start(self.canvas_overlay, True, True, 0)

    def _build_controls_panel(self):
        self.rotate_left_button = self._make_compact_button("arrow-left", None, "color1")
        self.rotate_right_button = self._make_compact_button("arrow-right", None, "color2")
        self.mode_button = self._make_compact_button(None, _("Current"), "color3")
        self.travel_button = self._make_compact_button(None, _("Travel Off"), "color4")
        self.view_buttons = {
            DisplayViewMode.MODE_2D: self._make_compact_button(None, _("2D"), "color1"),
            DisplayViewMode.MODE_3D: self._make_compact_button(None, _("3D"), "color2"),
        }
        self.drag_buttons = {
            self.DRAG_ROTATE: self._make_compact_button(None, _("Rotate"), "color1"),
            self.DRAG_PAN: self._make_compact_button(None, _("Pan"), "color2"),
        }
        self.buttons = {
            "zoom_out": self._make_compact_button("decrease", None, "color1"),
            "zoom_in": self._make_compact_button("increase", None, "color2"),
            "fit": self._make_compact_button("refresh", None, "color3"),
            "reset": self._make_compact_button("complete", None, "color4"),
            "rotate_left": self.rotate_left_button,
            "rotate_right": self.rotate_right_button,
            "mode": self.mode_button,
            "travel": self.travel_button,
            "retry": self.retry_button,
        }
        self.buttons["zoom_out"].connect("clicked", self.zoom, 0.8)
        self.buttons["zoom_in"].connect("clicked", self.zoom, 1.25)
        self.buttons["fit"].connect("clicked", self.fit_view)
        self.buttons["reset"].connect("clicked", self.reset_view)
        self.rotate_left_button.connect("clicked", self.rotate_left)
        self.rotate_right_button.connect("clicked", self.rotate_right)
        self.mode_button.connect("clicked", self.cycle_mode)
        self.travel_button.connect("clicked", self.toggle_travel)
        self.view_buttons[DisplayViewMode.MODE_2D].connect("clicked", self.set_view_mode, DisplayViewMode.MODE_2D)
        self.view_buttons[DisplayViewMode.MODE_3D].connect("clicked", self.set_view_mode, DisplayViewMode.MODE_3D)
        self.drag_buttons[self.DRAG_ROTATE].connect("clicked", self.set_drag_mode, self.DRAG_ROTATE)
        self.drag_buttons[self.DRAG_PAN].connect("clicked", self.set_drag_mode, self.DRAG_PAN)

        self.controls_panel = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=self.controls_spacing,
            margin_top=self.content_margin,
            margin_bottom=self.content_margin,
            margin_start=self.content_margin,
            margin_end=self.content_margin,
        )
        self.controls_panel.set_hexpand(True)
        self.controls_panel.set_vexpand(True)

        view_grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, column_spacing=6, row_spacing=6)
        view_grid.attach(self.rotate_left_button, 0, 0, 1, 1)
        view_grid.attach(self.rotate_right_button, 1, 0, 1, 1)
        view_grid.attach(self.buttons["zoom_out"], 0, 1, 1, 1)
        view_grid.attach(self.buttons["zoom_in"], 1, 1, 1, 1)
        view_grid.attach(self.buttons["fit"], 0, 2, 1, 1)
        view_grid.attach(self.buttons["reset"], 1, 2, 1, 1)

        self.drag_mode_box = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, column_spacing=6, row_spacing=6)
        self.drag_mode_box.attach(self.drag_buttons[self.DRAG_ROTATE], 0, 0, 1, 1)
        self.drag_mode_box.attach(self.drag_buttons[self.DRAG_PAN], 1, 0, 1, 1)

        view_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        view_box.add(view_grid)
        view_box.add(self.drag_mode_box)
        self.controls_panel.add(self._wrap_control_section(_("View"), view_box))

        self.view_mode_box = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, column_spacing=6, row_spacing=6)
        self.view_mode_box.attach(self.view_buttons[DisplayViewMode.MODE_2D], 0, 0, 1, 1)
        self.view_mode_box.attach(self.view_buttons[DisplayViewMode.MODE_3D], 1, 0, 1, 1)

        display_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        display_box.add(self.view_mode_box)
        display_box.add(self.mode_button)
        display_box.add(self.travel_button)
        self.controls_panel.add(self._wrap_control_section(_("Display"), display_box))

        self.controls_scroller = self._gtk.ScrolledWindow(steppers=False)
        self.controls_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.controls_scroller.set_hexpand(False)
        self.controls_scroller.set_vexpand(True)
        self.controls_scroller.add(self.controls_panel)

        self.controls_revealer = Gtk.Revealer()
        self.controls_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.controls_revealer.set_halign(Gtk.Align.END)
        self.controls_revealer.set_valign(Gtk.Align.FILL)
        self.controls_revealer.set_vexpand(True)
        self.controls_revealer.set_hexpand(False)
        self.controls_revealer.set_margin_end(self.content_margin)
        self.controls_revealer.set_margin_top(self.content_margin)
        self.controls_revealer.set_margin_bottom(self.content_margin)
        self.controls_revealer.add(self.controls_scroller)

        self.controls_toggle_button = self._make_header_button()
        self.controls_toggle_button.connect("clicked", self.toggle_controls)
        self.portrait_toolbar = Gtk.Box(spacing=6)
        self.portrait_toolbar.set_hexpand(True)
        self.portrait_toolbar.add(Gtk.Label(hexpand=True))
        self.portrait_toolbar.add(self.controls_toggle_button)

    def _apply_responsive_layout(self, width, height, force=False):
        spec = get_viewer_layout_spec(width, height, self._screen.vertical_mode)
        if not force and spec == self.layout_spec:
            return

        self.layout_spec = spec
        self.controls_scroller.set_size_request(spec.controls_width, -1)
        self._detach_widget(self.controls_scroller)
        self._detach_widget(self.controls_revealer)
        self._detach_widget(self.portrait_toolbar)
        self._detach_widget(self.canvas_column)
        self._clear_container(self.main_layout)
        self.canvas_overlay.set_overlay_pass_through(self.controls_revealer, False)

        if spec.mode == "landscape":
            self.main_layout.set_orientation(Gtk.Orientation.HORIZONTAL)
            self.main_layout.pack_start(self.canvas_column, True, True, 0)
            self.main_layout.pack_start(self.controls_scroller, False, False, 0)
            self.controls_revealer.set_reveal_child(False)
        else:
            self.main_layout.set_orientation(Gtk.Orientation.VERTICAL)
            self.controls_revealer.add(self.controls_scroller)
            self.main_layout.pack_start(self.portrait_toolbar, False, False, 0)
            self.main_layout.pack_start(self.canvas_column, True, True, 0)
            self.controls_revealer.set_reveal_child(False)
            self.canvas_overlay.add_overlay(self.controls_revealer)

        self.main_layout.show_all()
        self._update_control_labels()
        self.retry_button.set_visible(self.panel_state == "error")

    def _fit_view_to_model(self, force=False):
        if self.model is None:
            return
        width = self.canvas.get_allocated_width()
        height = self.canvas.get_allocated_height()
        if width <= 1 or height <= 1:
            return
        if self.view_mode == DisplayViewMode.MODE_3D:
            if not force and self.camera_3d.user_modified:
                return
            bounds, used_extrusion = self._visible_spatial_bounds()
            self.camera_3d.fit_bounds(bounds, width, height)
            self._log_spatial_fit_details(bounds, used_extrusion)
        else:
            if not force and self.viewport.user_modified:
                return
            bounds, used_extrusion = self._visible_planar_bounds()
            self.viewport.fit_bounds(bounds, width, height)
            self._log_planar_fit_details(bounds, used_extrusion)

    def _rotate_view(self, delta):
        if self.model is None:
            return
        if self.view_mode == DisplayViewMode.MODE_3D:
            self.camera_3d.rotate_yaw(delta)
            logging.debug("G-code viewer 3D yaw changed angle=%.1f", self.camera_3d.yaw)
        else:
            self.viewport.rotate(delta)
            logging.debug("G-code viewer 2D rotation changed angle=%.1f", self.viewport.rotation_deg)
        self.queue_render()

    def _visible_planar_bounds(self):
        if self._get_preview_context() == PreviewContext.SELECTED_FILE:
            prepared = self.renderer._prepare_geometry(
                self.model,
                RenderMode.FULL_MODEL,
                0,
                0,
                False,
            )
            if prepared.planar_bounds.is_valid:
                return (prepared.planar_bounds, prepared.used_extrusion_bounds)
        bounds, used_extrusion = self.model.visible_bounds(
            self.render_mode,
            self.progress.current_layer,
            self.previous_layers,
        )
        if bounds.is_valid:
            return (bounds, used_extrusion)
        return (self.model.bounds, False)

    def _visible_spatial_bounds(self):
        if self._get_preview_context() == PreviewContext.SELECTED_FILE:
            prepared = self.renderer._prepare_geometry(
                self.model,
                RenderMode.FULL_MODEL,
                0,
                0,
                False,
            )
            if prepared.spatial_bounds.is_valid:
                return (prepared.spatial_bounds, prepared.used_extrusion_bounds)
        bounds, used_extrusion = self.model.visible_spatial_bounds(
            self.render_mode,
            self.progress.current_layer,
            self.previous_layers,
            show_travel=self.show_travel,
        )
        if bounds.is_valid:
            return (bounds, used_extrusion)
        bounds, _ = self.model.visible_spatial_bounds(
            RenderMode.FULL_MODEL,
            self.progress.current_layer,
            self.previous_layers,
            show_travel=True,
        )
        return (bounds, False)

    def _sync_blanking_inhibition(self):
        if (
            getattr(self, "panel_active", False)
            and getattr(self, "enabled", False)
            and self._get_preview_context() == PreviewContext.ACTIVE_PRINT
            and getattr(self, "view_mode", DisplayViewMode.MODE_2D) == DisplayViewMode.MODE_3D
        ):
            self._screen.screensaver.inhibit(self.BLANKING_INHIBIT_OWNER)
        else:
            self._release_blanking_inhibition()

    def _release_blanking_inhibition(self):
        screen = getattr(self, "_screen", None)
        screensaver = getattr(screen, "screensaver", None)
        if screensaver is not None:
            screensaver.release(self.BLANKING_INHIBIT_OWNER)

    def _on_content_destroy(self, *args):
        self.panel_active = False
        self._cancel_interaction_quality_restore()
        self._release_blanking_inhibition()

    def _begin_interaction_render(self):
        if self._get_preview_context() != PreviewContext.SELECTED_FILE:
            return
        self._interaction_active = True
        self._schedule_interaction_quality_restore()

    def _schedule_interaction_quality_restore(self):
        if self._get_preview_context() != PreviewContext.SELECTED_FILE:
            self._cancel_interaction_quality_restore()
            return
        if self._interaction_restore_timer is not None:
            GLib.source_remove(self._interaction_restore_timer)
            self._interaction_restore_timer = None
        self._interaction_restore_timer = GLib.timeout_add(
            self.INTERACTION_SETTLE_MS,
            self._restore_interaction_quality,
        )

    def _restore_interaction_quality(self):
        self._interaction_restore_timer = None
        if not self.panel_active or self._get_preview_context() != PreviewContext.SELECTED_FILE:
            self._interaction_active = False
            return False
        self._interaction_active = False
        self.queue_render()
        return False

    def _cancel_interaction_quality_restore(self):
        restore_timer = getattr(self, "_interaction_restore_timer", None)
        if restore_timer is not None:
            GLib.source_remove(restore_timer)
            self._interaction_restore_timer = None
        self._interaction_active = False

    def _resolve_bed_reference_bounds(self):
        for getter in (self._bed_bounds_from_bed_mesh, self._bed_bounds_from_steppers):
            bounds = getter()
            if bounds is not None:
                return bounds
        return None

    def _bed_bounds_from_bed_mesh(self):
        section = self._printer.get_config_section("bed_mesh")
        if not section:
            return None
        try:
            return (
                float(section["min_x"]),
                float(section["min_y"]),
                float(section["max_x"]),
                float(section["max_y"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _bed_bounds_from_steppers(self):
        stepper_x = self._printer.get_config_section("stepper_x")
        stepper_y = self._printer.get_config_section("stepper_y")
        if not stepper_x or not stepper_y:
            return None
        try:
            return (
                float(stepper_x.get("position_min", 0.0)),
                float(stepper_y.get("position_min", 0.0)),
                float(stepper_x["position_max"]),
                float(stepper_y["position_max"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _on_content_size_allocate(self, widget, allocation):
        self._apply_responsive_layout(allocation.width, allocation.height)

    def _on_canvas_size_allocate(self, widget, allocation):
        current_size = (allocation.width, allocation.height)
        if current_size == self.last_canvas_size:
            return
        self.last_canvas_size = current_size
        if self.model is None:
            return
        if self.view_mode == DisplayViewMode.MODE_3D:
            if not self.camera_3d.user_modified or not self.camera_3d.fitted:
                self._fit_view_to_model(force=True)
                self.queue_render()
        else:
            if not self.viewport.user_modified or not self.viewport.fitted:
                self._fit_view_to_model(force=True)
                self.queue_render()

    def _wrap_control_section(self, title, child):
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        section.get_style_context().add_class("frame-item")
        heading = Gtk.Label(halign=Gtk.Align.START, xalign=0)
        heading.set_markup(f"<b>{title}</b>")
        section.add(heading)
        section.add(child)
        return section

    def _make_compact_button(self, icon_name=None, label=None, style=None):
        button = self._gtk.Button(icon_name, label, style, scale=0.70, lines=1)
        button.set_hexpand(False)
        button.set_vexpand(False)
        button.set_halign(Gtk.Align.FILL)
        button.set_valign(Gtk.Align.CENTER)
        button.set_size_request(self._gtk.font_size * 4, self._gtk.font_size * 3)
        return button

    def _make_header_button(self):
        button = Gtk.Button()
        button.set_hexpand(False)
        button.set_vexpand(False)
        button.set_can_focus(False)
        button.set_image(self._gtk.Image("settings", self._gtk.img_scale * 0.8, self._gtk.img_scale * 0.8))
        button.set_always_show_image(True)
        button.set_size_request(self._gtk.font_size * 2, self._gtk.font_size * 2)
        button.connect("clicked", self._screen.screensaver.reset_timeout)
        button.connect("clicked", self._screen.lock_screen.reset_timeout)
        return button

    @staticmethod
    def _set_button_selected(button, selected):
        context = button.get_style_context()
        if selected:
            context.add_class("suggested-action")
            button.set_sensitive(False)
        else:
            context.remove_class("suggested-action")
            button.set_sensitive(True)

    def _log_planar_fit_details(self, bounds, used_extrusion, reset=False):
        logging.debug(
            "G-code viewer 2D %s bounds=(%.3f, %.3f)-(%.3f, %.3f) rotation=%.1f using=%s",
            "reset" if reset else "fit",
            bounds.min_x,
            bounds.min_y,
            bounds.max_x,
            bounds.max_y,
            self.viewport.rotation_deg,
            "extrusion" if used_extrusion else "travel/fallback",
        )
        if used_extrusion and self.model is not None and self.model.bounds.is_valid:
            full_width = max(self.model.bounds.width, 1.0)
            full_height = max(self.model.bounds.height, 1.0)
            if bounds.width < (full_width * 0.6) or bounds.height < (full_height * 0.6):
                logging.debug(
                    "Ignored travel outlier bounds full=(%.3f, %.3f) extrusion=(%.3f, %.3f)",
                    self.model.bounds.width,
                    self.model.bounds.height,
                    bounds.width,
                    bounds.height,
                )

    def _log_spatial_fit_details(self, bounds, used_extrusion, reset=False):
        logging.debug(
            "G-code viewer 3D %s bounds=(%.3f, %.3f, %.3f)-(%.3f, %.3f, %.3f) yaw=%.1f pitch=%.1f using=%s",
            "reset" if reset else "fit",
            bounds.min_x,
            bounds.min_y,
            bounds.min_z,
            bounds.max_x,
            bounds.max_y,
            bounds.max_z,
            self.camera_3d.yaw,
            self.camera_3d.pitch,
            "extrusion" if used_extrusion else "travel/fallback",
        )

    @staticmethod
    def _detach_widget(widget):
        parent = widget.get_parent()
        if parent is not None:
            parent.remove(widget)

    @staticmethod
    def _clear_container(container):
        for child in container.get_children():
            container.remove(child)

    @staticmethod
    def _metadata_key(metadata):
        return (
            metadata.get("path"),
            metadata.get("size"),
            metadata.get("modified"),
        ) if metadata else None
