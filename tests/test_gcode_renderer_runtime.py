import ast
import importlib
import os
import pickle
import sys
import tempfile
import types
import unittest

sys.modules.setdefault("requests", types.SimpleNamespace())

from ks_includes.config import KlipperScreenConfig
from ks_includes.gcode_renderer import (
    DisplayViewMode,
    GcodeRenderCache,
    LoadTracker,
    PreviewContext,
    RenderMode,
    ViewportState,
    clamp_selected_preview_state,
    get_renderer_settings,
    get_viewer_layout_spec,
    initial_selected_preview_state,
    load_local_gcode,
    preview_access_location,
    preview_menu_visible,
    preview_panel_name,
    resolve_local_gcode_path,
    resolve_preview_context,
    rotate_point,
    rotated_bounds,
)
from ks_includes.gcode_renderer.cache import validate_toolpath_model
from ks_includes.gcode_renderer.loading import resolve_active_filename, should_clear_active_filename
from ks_includes.gcode_renderer.model import Bounds, ProgressInfo
from ks_includes.gcode_renderer.parser import parse_gcode
from ks_includes.KlippyRest import KlippyRest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))


class _ScreenStub:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _CaptureRest(KlippyRest):
    def __init__(self):
        super().__init__("127.0.0.1")
        self.calls = []

    def _do_request(
        self, method, request_method, data=None, json=None, json_response=True, timeout=3
    ):
        self.calls.append(
            {
                "method": method,
                "request_method": request_method,
                "json_response": json_response,
                "timeout": timeout,
            }
        )
        return {"result": {}} if json_response else b"ok"


class _ImmediateFuture:
    def __init__(self, fn):
        self._exception = None
        self._result = None
        try:
            self._result = fn()
        except Exception as exc:
            self._exception = exc

    def exception(self):
        return self._exception

    def result(self):
        if self._exception is not None:
            raise self._exception
        return self._result

    def add_done_callback(self, callback):
        callback(self)


class _ImmediateExecutor:
    def __init__(self):
        self.submit_count = 0

    def submit(self, fn):
        self.submit_count += 1
        return _ImmediateFuture(fn)


class _PanelPrinterStub:
    def __init__(self, print_state="printing", print_filename="", virtual_sdcard=None):
        self.print_state = print_state
        self.print_filename = print_filename
        self.virtual_sdcard = virtual_sdcard or {}

    def get_stat(self, section, substat=None):
        if section == "print_stats":
            values = {"state": self.print_state, "filename": self.print_filename}
            return values.get(substat, values if substat is None else None)
        if section == "virtual_sdcard":
            if substat is None:
                return self.virtual_sdcard
            return self.virtual_sdcard.get(substat)
        if section == "motion_report" and substat == "live_position":
            return None
        return None


class _PanelFilesStub:
    def __init__(self, gcodes_path, metadata=None):
        self.gcodes_path = gcodes_path
        self.metadata = metadata or {}
        self.requests = []

    def file_metadata_exists(self, filename):
        return filename in self.metadata

    def get_file_info(self, filename):
        return dict(self.metadata.get(filename, {}))

    def request_metadata(self, filename):
        self.requests.append(filename)


class _PanelRestStub:
    def get_gcode_stream(self, filename, timeout=60):
        raise AssertionError(f"REST fallback should not be used in this test for {filename}")


class _PanelScreensaverStub:
    def __init__(self):
        self.calls = []

    def inhibit(self, owner):
        self.calls.append(("inhibit", owner))

    def release(self, owner):
        self.calls.append(("release", owner))


class _StyleContextStub:
    def add_class(self, *args, **kwargs):
        return None

    def remove_class(self, *args, **kwargs):
        return None


class _GtkWidgetStub:
    def __init__(self, *args, **kwargs):
        self.children = []
        self.visible = True
        self.parent = None
        self.image = None
        self.label = kwargs.get("label")

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def add(self, child):
        if hasattr(child, "parent"):
            child.parent = self
        self.children.append(child)

    def pack_start(self, child, *args, **kwargs):
        if hasattr(child, "parent"):
            child.parent = self
        self.children.append(child)

    def attach(self, child, *args, **kwargs):
        if hasattr(child, "parent"):
            child.parent = self
        self.children.append(child)

    def connect(self, *args, **kwargs):
        return None

    def get_style_context(self):
        return _StyleContextStub()

    def get_children(self):
        return list(self.children)

    def remove(self, child):
        if child in self.children:
            self.children.remove(child)

    def set_visible(self, visible):
        self.visible = visible

    def show_all(self):
        self.visible = True
        for child in self.children:
            show_all = getattr(child, "show_all", None)
            if callable(show_all):
                show_all()
            elif hasattr(child, "visible"):
                child.visible = True

    def get_parent(self):
        return self.parent

    def set_image(self, image):
        self.image = image

    def set_label(self, value):
        self.label = value


class _PrintListItemStub(_GtkWidgetStub):
    def __init__(self):
        super().__init__()
        self._date = 0
        self._size = 0
        self._is_dir = False
        self._path = ""
        self._name = ""

    def set_date(self, value):
        self._date = value

    def set_size(self, value):
        self._size = value

    def set_as_dir(self, value):
        self._is_dir = value

    def set_path(self, value):
        self._path = value

    def set_name(self, value):
        self._name = value

    def get_date(self):
        return self._date

    def get_size(self):
        return self._size

    def get_is_dir(self):
        return self._is_dir

    def get_path(self):
        return self._path

    def get_name(self):
        return self._name


class _PanelCtorScreenStub:
    def __init__(self):
        self.width = 800
        self.height = 480
        self.vertical_mode = False
        self.screensaver = _PanelScreensaverStub()
        self._config = types.SimpleNamespace(
            get_main_config=lambda: {},
            set=lambda *args, **kwargs: None,
            save_user_config_options=lambda: None,
        )
        self.files = _PanelFilesStub("", {})
        self.printer = _PanelPrinterStub(print_state="standby", print_filename="")
        self.gtk = types.SimpleNamespace(
            font_size=24,
            img_scale=24,
            button_image_scale=1,
            bsidescale=1,
            Button=lambda *args, **kwargs: _GtkWidgetStub(),
            Image=lambda *args, **kwargs: _GtkWidgetStub(),
            ScrolledWindow=lambda *args, **kwargs: _GtkWidgetStub(),
        )


class GcodeRendererRuntimeTests(unittest.TestCase):
    def test_gcode_viewer_constructor_initializes_buttons_before_sync(self):
        module = self._parse_gcode_viewer_module()
        init_func = self._find_method(module, "__init__")

        button_assign_index = None
        sync_call_index = None
        refresh_call_index = None
        executor_submit_in_init = False

        for index, statement in enumerate(init_func.body):
            if self._assigns_attribute(statement, "buttons"):
                button_assign_index = index
            if self._calls_method(statement, "_sync_settings"):
                sync_call_index = index
            if self._calls_method(statement, "_refresh_from_printer"):
                refresh_call_index = index
            if self._calls_method(statement, "submit", owner_attr="executor"):
                executor_submit_in_init = True

        self.assertIsNotNone(button_assign_index)
        self.assertIsNotNone(sync_call_index)
        self.assertLess(button_assign_index, sync_call_index)
        self.assertIsNone(refresh_call_index)
        self.assertFalse(executor_submit_in_init)

    def test_gcode_viewer_sync_settings_is_idempotent_and_load_free(self):
        module = self._parse_gcode_viewer_module()
        sync_func = self._find_method(module, "_sync_settings")
        sync_calls = sum(
            1 for node in ast.walk(module) if self._is_method_call(node, "_sync_settings")
        )

        self.assertGreaterEqual(sync_calls, 2)
        self.assertFalse(
            any(self._is_method_call(node, "_schedule_load") for node in ast.walk(sync_func))
        )
        self.assertFalse(
            any(self._is_method_call(node, "_refresh_from_printer") for node in ast.walk(sync_func))
        )

    def test_gcode_viewer_activate_performs_first_refresh(self):
        module = self._parse_gcode_viewer_module()
        activate_func = self._find_method(module, "activate")

        self.assertTrue(
            any(
                self._is_method_call(node, "_refresh_from_printer")
                for node in ast.walk(activate_func)
            )
        )
        self.assertTrue(
            any(
                self._is_method_call(node, "activate", owner_attr="load_tracker")
                for node in ast.walk(activate_func)
            )
        )

    def test_gcode_viewer_view_callbacks_do_not_schedule_loads(self):
        module = self._parse_gcode_viewer_module()
        for method_name in ("zoom", "rotate_left", "rotate_right", "fit_view", "reset_view"):
            method = self._find_method(module, method_name)
            self.assertFalse(
                any(self._is_method_call(node, "_schedule_load") for node in ast.walk(method))
            )

    def test_gcode_viewer_display_callbacks_do_not_schedule_loads(self):
        module = self._parse_gcode_viewer_module()
        for method_name in ("set_view_mode", "set_drag_mode", "toggle_travel", "cycle_mode"):
            method = self._find_method(module, method_name)
            self.assertFalse(
                any(self._is_method_call(node, "_schedule_load") for node in ast.walk(method))
            )
            self.assertFalse(
                any(
                    self._is_method_call(node, "submit", owner_attr="executor")
                    for node in ast.walk(method)
                )
            )

    def test_gcode_viewer_blanking_inhibition_hooks_are_lifecycle_scoped(self):
        module = self._parse_gcode_viewer_module()
        activate_func = self._find_method(module, "activate")
        deactivate_func = self._find_method(module, "deactivate")
        set_view_mode_func = self._find_method(module, "set_view_mode")
        refresh_func = self._find_method(module, "_refresh_from_printer")

        self.assertTrue(
            any(
                self._is_method_call(node, "_sync_blanking_inhibition")
                for node in ast.walk(activate_func)
            )
        )
        self.assertTrue(
            any(
                self._is_method_call(node, "_release_blanking_inhibition")
                for node in ast.walk(deactivate_func)
            )
        )
        self.assertTrue(
            any(
                self._is_method_call(node, "_sync_blanking_inhibition")
                for node in ast.walk(set_view_mode_func)
            )
        )
        self.assertTrue(
            any(
                self._is_method_call(node, "_sync_blanking_inhibition")
                for node in ast.walk(refresh_func)
            )
        )

    def test_gcode_viewer_sidebar_removes_internal_back_button_and_status_section(self):
        viewer_path = os.path.join(REPO_ROOT, "panels", "gcode_viewer.py")
        with open(viewer_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertNotIn("controls_close_button", source)
        self.assertNotIn('_wrap_control_section(_("Controls")', source)
        self.assertNotIn('_wrap_control_section(_("Status")', source)

    def test_gcode_viewer_sidebar_keeps_view_and_display_sections(self):
        viewer_path = os.path.join(REPO_ROOT, "panels", "gcode_viewer.py")
        with open(viewer_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn('_wrap_control_section(_("View")', source)
        self.assertIn('_wrap_control_section(_("Display")', source)
        self.assertIn("DisplayViewMode.MODE_2D", source)
        self.assertIn("DisplayViewMode.MODE_3D", source)
        self.assertIn("self.drag_mode_box", source)

    def test_viewer_layout_helper_prefers_landscape_split_layout(self):
        spec = get_viewer_layout_spec(width=1024, height=600, vertical_mode=False)
        self.assertEqual(spec.mode, "landscape")
        self.assertFalse(spec.controls_collapsed)
        self.assertGreaterEqual(spec.controls_width, 220)
        self.assertLessEqual(spec.controls_width, 320)

    def test_viewer_layout_helper_prefers_portrait_collapsible_controls(self):
        spec = get_viewer_layout_spec(width=600, height=1024, vertical_mode=True)
        self.assertEqual(spec.mode, "portrait")
        self.assertTrue(spec.controls_collapsed)
        self.assertGreaterEqual(spec.controls_width, 220)
        self.assertLessEqual(spec.controls_width, 360)

    def test_rotation_helper_rotates_around_origin(self):
        self.assertEqual(rotate_point(10.0, 0.0, 0.0), (10.0, 0.0))
        x, y = rotate_point(10.0, 0.0, 90.0)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 10.0, places=6)

    def test_rotated_bounds_expand_at_ninety_degrees(self):
        bounds = Bounds(0.0, 0.0, 20.0, 10.0)
        rotated = rotated_bounds(bounds, 90.0)
        self.assertAlmostEqual(rotated.width, 10.0, places=6)
        self.assertAlmostEqual(rotated.height, 20.0, places=6)

    def test_viewport_reset_rotation_zoom_and_pan(self):
        viewport = ViewportState(scale=2.0, pan_x=10.0, pan_y=15.0, rotation_deg=45.0, fitted=False)
        viewport.reset(Bounds(0.0, 0.0, 20.0, 10.0), 400, 300)
        self.assertEqual(viewport.rotation_deg, 0.0)
        self.assertEqual(viewport.pan_x, 0.0)
        self.assertEqual(viewport.pan_y, 0.0)
        self.assertTrue(viewport.fitted)

    def test_viewport_rotation_normalizes_safely(self):
        viewport = ViewportState()
        viewport.rotate(195.0)
        self.assertEqual(viewport.rotation_deg, -165.0)

    def test_visible_bounds_prefer_extrusion_over_travel_outlier(self):
        model = self._build_outlier_model()
        bounds, used_extrusion = model.visible_bounds(
            RenderMode.FULL_MODEL, current_layer=0, previous_layers=0
        )
        self.assertTrue(used_extrusion)
        self.assertEqual(
            (bounds.min_x, bounds.min_y, bounds.max_x, bounds.max_y), (0.0, 0.0, 10.0, 10.0)
        )

    def test_preview_menu_helpers(self):
        self.assertTrue(preview_menu_visible(True, "folder/part.gcode"))
        self.assertFalse(preview_menu_visible(True, ""))
        self.assertFalse(preview_menu_visible(False, "folder/part.gcode"))
        self.assertEqual(preview_access_location(), "print_menu")

    def test_renderer_settings_validation_and_clamping(self):
        settings = get_renderer_settings(
            {
                "enable_gcode_renderer": "true",
                "gcode_renderer_view": "invalid-view",
                "gcode_renderer_show_travel": "1",
                "gcode_renderer_mode": "bad-mode",
                "gcode_renderer_fps": "99",
                "gcode_renderer_previous_layers": "-5",
            }
        )
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.view, DisplayViewMode.MODE_2D)
        self.assertTrue(settings.show_travel)
        self.assertEqual(settings.mode, RenderMode.CURRENT_LAYER)
        self.assertEqual(settings.fps, 10)
        self.assertEqual(settings.previous_layers, 0)

    def test_preview_context_resolution(self):
        self.assertEqual(
            resolve_preview_context(None, "folder/part.gcode", default_active_print=True),
            PreviewContext.SELECTED_FILE,
        )
        self.assertEqual(
            resolve_preview_context(None, "", default_active_print=True),
            PreviewContext.ACTIVE_PRINT,
        )
        self.assertIsNone(
            resolve_preview_context("unknown", "folder/part.gcode", default_active_print=True)
        )

    def test_preview_panel_name_resolution(self):
        self.assertEqual(preview_panel_name("selected_file"), "gcode_viewer_selected")
        self.assertEqual(preview_panel_name("active_print"), "gcode_viewer_active")
        self.assertEqual(preview_panel_name(None), "gcode_viewer")

    def test_gcode_viewer_constructor_signature_is_navigation_compatible(self):
        module = self._parse_gcode_viewer_module()
        init_func = self._find_method(module, "__init__")
        arg_names = [arg.arg for arg in init_func.args.args]

        self.assertEqual(arg_names[:5], ["self", "screen", "title", "filename", "preview_context"])
        self.assertIsNotNone(init_func.args.kwarg)
        self.assertEqual(init_func.args.kwarg.arg, "kwargs")

    def test_gcode_viewer_constructor_accepts_selected_file_preview_context(self):
        panel_class = self._load_gcode_viewer_panel_class()
        original_build_canvas_area = panel_class._build_canvas_area
        original_build_controls_panel = panel_class._build_controls_panel
        original_sync_settings = panel_class._sync_settings
        original_apply_layout = panel_class._apply_responsive_layout
        original_set_panel_state = panel_class._set_panel_state
        original_cache_class = panel_class.__init__.__globals__["GcodeRenderCache"]
        try:
            panel_class._build_canvas_area = lambda self: None
            panel_class._build_controls_panel = lambda self: None
            panel_class._sync_settings = lambda self, sync_view_mode=True: setattr(
                self, "enabled", False
            )
            panel_class._apply_responsive_layout = lambda self, *args, **kwargs: None
            panel_class._set_panel_state = lambda self, *args, **kwargs: None
            panel_class.__init__.__globals__["GcodeRenderCache"] = lambda: types.SimpleNamespace()

            panel = panel_class(
                _PanelCtorScreenStub(),
                title="Preview",
                filename="folder/test.gcode",
                preview_context="selected_file",
            )
        finally:
            panel_class._build_canvas_area = original_build_canvas_area
            panel_class._build_controls_panel = original_build_controls_panel
            panel_class._sync_settings = original_sync_settings
            panel_class._apply_responsive_layout = original_apply_layout
            panel_class._set_panel_state = original_set_panel_state
            panel_class.__init__.__globals__["GcodeRenderCache"] = original_cache_class

        self.assertEqual(panel.explicit_filename, "folder/test.gcode")
        self.assertEqual(panel._get_preview_context(), PreviewContext.SELECTED_FILE)

    def test_gcode_viewer_constructor_accepts_active_print_preview_context(self):
        panel_class = self._load_gcode_viewer_panel_class()
        original_build_canvas_area = panel_class._build_canvas_area
        original_build_controls_panel = panel_class._build_controls_panel
        original_sync_settings = panel_class._sync_settings
        original_apply_layout = panel_class._apply_responsive_layout
        original_set_panel_state = panel_class._set_panel_state
        original_cache_class = panel_class.__init__.__globals__["GcodeRenderCache"]
        try:
            panel_class._build_canvas_area = lambda self: None
            panel_class._build_controls_panel = lambda self: None
            panel_class._sync_settings = lambda self, sync_view_mode=True: setattr(
                self, "enabled", False
            )
            panel_class._apply_responsive_layout = lambda self, *args, **kwargs: None
            panel_class._set_panel_state = lambda self, *args, **kwargs: None
            panel_class.__init__.__globals__["GcodeRenderCache"] = lambda: types.SimpleNamespace()

            panel = panel_class(
                _PanelCtorScreenStub(),
                title="Preview",
                preview_context="active_print",
            )
        finally:
            panel_class._build_canvas_area = original_build_canvas_area
            panel_class._build_controls_panel = original_build_controls_panel
            panel_class._sync_settings = original_sync_settings
            panel_class._apply_responsive_layout = original_apply_layout
            panel_class._set_panel_state = original_set_panel_state
            panel_class.__init__.__globals__["GcodeRenderCache"] = original_cache_class

        self.assertEqual(panel.explicit_filename, "")
        self.assertEqual(panel._get_preview_context(), PreviewContext.ACTIVE_PRINT)

    def test_selected_file_preview_source_has_no_navigation_slider_ui(self):
        viewer_path = os.path.join(REPO_ROOT, "panels", "gcode_viewer.py")
        with open(viewer_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertNotIn("_build_selected_file_navigation", source)
        self.assertNotIn("layer_slider_section", source)
        self.assertNotIn("move_slider_section", source)
        self.assertNotIn('_("Preview Progress")', source)
        self.assertNotIn('_("Z Height")', source)
        self.assertNotIn('_("Step")', source)
        self.assertNotIn('_("Start")', source)
        self.assertNotIn('_("End")', source)

    def test_rotate_buttons_use_arrow_icons_without_text_labels(self):
        viewer_path = os.path.join(REPO_ROOT, "panels", "gcode_viewer.py")
        with open(viewer_path, "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn(
            'self.rotate_left_button = self._make_compact_button("arrow-left", None, "color1")',
            source,
        )
        self.assertIn(
            'self.rotate_right_button = self._make_compact_button("arrow-right", None, "color2")',
            source,
        )
        self.assertNotIn('self._make_compact_button(None, _("Rotate left"), "color1")', source)
        self.assertNotIn('self._make_compact_button(None, _("Rotate right"), "color2")', source)

    def test_rotate_arrow_icons_exist_in_all_themes(self):
        styles_dir = os.path.join(REPO_ROOT, "styles")
        for theme in ("colorized", "material-dark", "material-darker", "z-bolt"):
            self.assertTrue(
                os.path.exists(os.path.join(styles_dir, theme, "images", "arrow-left.svg"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(styles_dir, theme, "images", "arrow-right.svg"))
            )

    def test_selected_file_context_keeps_explicit_filename(self):
        panel_class = self._load_gcode_viewer_panel_class()
        scheduled = []
        panel = object.__new__(panel_class)
        panel.preview_context = "selected_file"
        panel.explicit_filename = "picked.gcode"
        panel.filename = "picked.gcode"
        panel._printer = _PanelPrinterStub(print_state="standby", print_filename="other.gcode")
        panel._files = _PanelFilesStub("", {})
        panel._config = types.SimpleNamespace(get_main_config=lambda: {})
        panel._sync_settings = lambda sync_view_mode=False: None
        panel._sync_blanking_inhibition = lambda: None
        panel._sync_selected_preview_controls = lambda: None
        panel._refresh_metadata = lambda: None
        panel._set_panel_state = lambda *args, **kwargs: None
        panel.queue_render = lambda: None
        panel._update_progress = lambda: False
        panel._apply_pending_load_result = lambda: False
        panel._schedule_load = lambda force_reload=False: scheduled.append(force_reload)
        panel.enabled = True
        panel.model = object()
        panel.render_message = None

        panel._refresh_from_printer()

        self.assertEqual(panel.filename, "picked.gcode")
        self.assertEqual(scheduled, [])

    def test_invalid_preview_context_falls_back_to_idle_without_loading(self):
        panel_class = self._load_gcode_viewer_panel_class()
        scheduled = []
        states = []
        panel = object.__new__(panel_class)
        panel.preview_context = "bad-context"
        panel.explicit_filename = "picked.gcode"
        panel.filename = ""
        panel._printer = _PanelPrinterStub(print_state="standby", print_filename="")
        panel._files = _PanelFilesStub("", {})
        panel._config = types.SimpleNamespace(get_main_config=lambda: {})
        panel._sync_settings = lambda sync_view_mode=False: None
        panel._sync_blanking_inhibition = lambda: None
        panel._sync_selected_preview_controls = lambda: None
        panel._refresh_metadata = lambda: None
        panel._set_panel_state = lambda *args, **kwargs: states.append(args)
        panel.queue_render = lambda: None
        panel._update_progress = lambda: False
        panel._apply_pending_load_result = lambda: False
        panel._schedule_load = lambda force_reload=False: scheduled.append(force_reload)
        panel.enabled = True
        panel.model = None
        panel.render_message = None

        panel._refresh_from_printer()

        self.assertEqual(panel.filename, "")
        self.assertEqual(scheduled, [])
        self.assertTrue(any(state[0] == "idle" for state in states))

    def test_selected_preview_state_initializes_to_last_layer(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\nG1 Z0.4\nG1 X2 Y2 E2.0\n",
            "sample.gcode",
        )
        state = initial_selected_preview_state(model)
        self.assertEqual(state.layer_index, model.total_layers - 1)
        self.assertEqual(state.move_index, 0)

    def test_selected_preview_state_clamps_layer_and_move_indexes(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\nG0 X2 Y2\nG1 X3 Y3 E2.0\n",
            "sample.gcode",
        )
        state = clamp_selected_preview_state(model, 99, 99)
        self.assertEqual(state.layer_index, model.total_layers - 1)
        self.assertEqual(state.move_index, model.layer_segment_count(state.layer_index) - 1)

    def test_layer_slider_maps_minimum_and_maximum_with_variable_z_heights(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\nG1 Z0.45\nG1 X2 Y2 E2.0\nG1 Z0.9\nG1 X3 Y3 E3.0\n",
            "sample.gcode",
        )
        self.assertEqual(model.clamp_layer_index(0), 0)
        self.assertEqual(model.clamp_layer_index(999), model.total_layers - 1)
        self.assertAlmostEqual(model.layer_z_height(0), 0.2, places=6)
        self.assertAlmostEqual(model.layer_z_height(1), 0.45, places=6)
        self.assertAlmostEqual(model.layer_z_height(2), 0.9, places=6)

    def test_movement_slider_maps_to_first_and_last_segment(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\nG0 X2 Y2\nG1 X3 Y3 E2.0\n",
            "sample.gcode",
        )
        layer_index = model.total_layers - 1
        self.assertEqual(
            model.layer_move_segment_index(layer_index, 0),
            model.layer_segment_range(layer_index)[0],
        )
        self.assertEqual(
            model.layer_move_segment_index(layer_index, 999),
            model.layer_segment_range(layer_index)[1] - 1,
        )

    def test_intermediate_move_progress_preserves_segment_order_with_hidden_travel(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\nG0 X2 Y2\nG1 X3 Y3 E2.0\n",
            "sample.gcode",
        )
        layer_index = model.total_layers - 1
        start, end = model.layer_segment_range(layer_index)
        self.assertEqual(model.layer_segment_count(layer_index), end - start)
        self.assertEqual(model.layer_move_segment_index(layer_index, 1), start + 1)
        progress = model.progress_for_layer_move(layer_index, 1)
        self.assertEqual(progress.current_segment, start + 1)
        self.assertEqual(progress.executed_segments, start + 1)

    def test_selected_file_progress_uses_static_completed_preview(self):
        panel_class = self._load_gcode_viewer_panel_class()
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\nG0 X2 Y2\nG1 X3 Y3 E2.0\n",
            "sample.gcode",
        )
        panel = object.__new__(panel_class)
        panel.preview_context = "selected_file"
        panel.model = model
        panel._printer = _PanelPrinterStub(
            print_state="printing",
            print_filename="other.gcode",
            virtual_sdcard={"file_position": 999999},
        )
        panel.print_state = "printing"
        panel.last_progress_signature = None

        changed = panel._update_progress()

        self.assertTrue(changed)
        self.assertEqual(panel.progress.current_layer, model.total_layers - 1)
        self.assertEqual(panel.progress.current_segment, model.segment_count - 1)
        self.assertEqual(panel.progress.executed_segments, model.segment_count)

    def test_active_print_progress_uses_live_file_position(self):
        panel_class = self._load_gcode_viewer_panel_class()
        payload = b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\nG1 X2 Y2 E2.0\n"
        model = parse_gcode(payload, "sample.gcode", file_size=len(payload), modified=1.0)
        panel = object.__new__(panel_class)
        panel.preview_context = "active_print"
        panel.model = model
        panel._printer = _PanelPrinterStub(
            print_state="printing",
            print_filename="sample.gcode",
            virtual_sdcard={"file_position": model.segment_end_offsets[0]},
        )
        panel.print_state = "printing"
        panel.last_progress_signature = None

        changed = panel._update_progress()

        self.assertTrue(changed)
        self.assertEqual(panel.progress.current_segment, 1)
        self.assertEqual(panel.progress.executed_segments, 1)

    def test_selected_file_display_state_hides_travel_and_mode_controls(self):
        panel_class = self._load_gcode_viewer_panel_class()
        panel = object.__new__(panel_class)
        panel.preview_context = "selected_file"
        panel.explicit_filename = "picked.gcode"
        panel._active_print_session_show_travel = None
        panel._interaction_restore_timer = None
        panel.mode_button = _ButtonStateStub()
        panel.travel_button = _ButtonStateStub()
        panel.view_buttons = {
            DisplayViewMode.MODE_2D: _ButtonStateStub(),
            DisplayViewMode.MODE_3D: _ButtonStateStub(),
        }
        panel.drag_buttons = {
            panel_class.DRAG_ROTATE: _ButtonStateStub(),
            panel_class.DRAG_PAN: _ButtonStateStub(),
        }
        panel.drag_mode_box = _VisibleStub()
        panel.drag_mode_3d = panel_class.DRAG_ROTATE
        panel.view_mode = DisplayViewMode.MODE_2D
        panel._config = _ConfigStub(
            {
                "enable_gcode_renderer": "True",
                "gcode_renderer_show_travel": "True",
                "gcode_renderer_mode": RenderMode.CURRENT_LAYER.value,
            }
        )

        panel._sync_settings()

        self.assertFalse(panel.show_travel)
        self.assertEqual(panel.render_mode, RenderMode.FULL_MODEL)
        self.assertFalse(panel.mode_button.visible)
        self.assertFalse(panel.travel_button.visible)

    def test_active_print_display_state_defaults_travel_on_and_shows_controls(self):
        panel_class = self._load_gcode_viewer_panel_class()
        panel = object.__new__(panel_class)
        panel.preview_context = "active_print"
        panel.explicit_filename = ""
        panel._active_print_session_show_travel = None
        panel._interaction_restore_timer = None
        panel.mode_button = _ButtonStateStub()
        panel.travel_button = _ButtonStateStub()
        panel.view_buttons = {
            DisplayViewMode.MODE_2D: _ButtonStateStub(),
            DisplayViewMode.MODE_3D: _ButtonStateStub(),
        }
        panel.drag_buttons = {
            panel_class.DRAG_ROTATE: _ButtonStateStub(),
            panel_class.DRAG_PAN: _ButtonStateStub(),
        }
        panel.drag_mode_box = _VisibleStub()
        panel.drag_mode_3d = panel_class.DRAG_ROTATE
        panel.view_mode = DisplayViewMode.MODE_2D
        panel._config = _ConfigStub(
            {
                "enable_gcode_renderer": "True",
                "gcode_renderer_show_travel": "False",
                "gcode_renderer_mode": RenderMode.CURRENT_AND_PREVIOUS.value,
            }
        )

        panel._sync_settings()

        self.assertTrue(panel.show_travel)
        self.assertEqual(panel.render_mode, RenderMode.CURRENT_AND_PREVIOUS)
        self.assertTrue(panel.mode_button.visible)
        self.assertTrue(panel.travel_button.visible)

    def test_context_change_refreshes_visibility_without_leaking_selected_file_state(self):
        panel_class = self._load_gcode_viewer_panel_class()
        panel = object.__new__(panel_class)
        panel.preview_context = "selected_file"
        panel.explicit_filename = "picked.gcode"
        panel._active_print_session_show_travel = None
        panel._interaction_restore_timer = None
        panel.mode_button = _ButtonStateStub()
        panel.travel_button = _ButtonStateStub()
        panel.view_buttons = {
            DisplayViewMode.MODE_2D: _ButtonStateStub(),
            DisplayViewMode.MODE_3D: _ButtonStateStub(),
        }
        panel.drag_buttons = {
            panel_class.DRAG_ROTATE: _ButtonStateStub(),
            panel_class.DRAG_PAN: _ButtonStateStub(),
        }
        panel.drag_mode_box = _VisibleStub()
        panel.drag_mode_3d = panel_class.DRAG_ROTATE
        panel.view_mode = DisplayViewMode.MODE_2D
        panel._config = _ConfigStub(
            {
                "enable_gcode_renderer": "True",
                "gcode_renderer_show_travel": "False",
                "gcode_renderer_mode": RenderMode.CURRENT_AND_PREVIOUS.value,
            }
        )

        panel._sync_settings()
        self.assertFalse(panel.show_travel)
        self.assertEqual(panel.render_mode, RenderMode.FULL_MODEL)

        panel.preview_context = "active_print"
        panel.explicit_filename = ""
        panel._sync_settings()

        self.assertTrue(panel.show_travel)
        self.assertEqual(panel.render_mode, RenderMode.CURRENT_AND_PREVIOUS)
        self.assertTrue(panel.mode_button.visible)
        self.assertTrue(panel.travel_button.visible)

    def test_renderer_geometry_cache_reuses_same_selection(self):
        from ks_includes.gcode_renderer.renderer import ToolpathRenderer

        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\nG1 X2 Y2 E2.0\n",
            "sample.gcode",
        )
        renderer = ToolpathRenderer()
        first = renderer._prepare_geometry(
            model,
            RenderMode.CURRENT_LAYER,
            model.total_layers - 1,
            previous_layers=0,
            show_travel=False,
        )
        second = renderer._prepare_geometry(
            model,
            RenderMode.CURRENT_LAYER,
            model.total_layers - 1,
            previous_layers=0,
            show_travel=False,
        )
        self.assertIs(first, second)

    def test_selected_file_interaction_timer_is_replaced_instead_of_accumulating(self):
        panel_class = self._load_gcode_viewer_panel_class()
        module = sys.modules[panel_class.__module__]
        tracker = _PanelGLibTracker()
        original_glib = module.GLib
        module.GLib = tracker
        try:
            panel = object.__new__(panel_class)
            panel.preview_context = "selected_file"
            panel.explicit_filename = "picked.gcode"
            panel.panel_active = True
            panel._interaction_restore_timer = None
            panel._interaction_active = True
            panel.queue_render = lambda: None

            panel._schedule_interaction_quality_restore()
            first_timer = panel._interaction_restore_timer
            panel._schedule_interaction_quality_restore()

            self.assertEqual(first_timer, 1)
            self.assertEqual(panel._interaction_restore_timer, 2)
            self.assertEqual(tracker.removed, [1])
            self.assertEqual(len(tracker.timeouts), 2)
        finally:
            module.GLib = original_glib

    def test_selected_file_interaction_restore_returns_to_final_quality(self):
        panel_class = self._load_gcode_viewer_panel_class()
        panel = object.__new__(panel_class)
        renders = []
        panel.preview_context = "selected_file"
        panel.explicit_filename = "picked.gcode"
        panel.panel_active = True
        panel._interaction_active = True
        panel._interaction_restore_timer = 9
        panel.queue_render = lambda: renders.append("render")

        result = panel._restore_interaction_quality()

        self.assertFalse(result)
        self.assertFalse(panel._interaction_active)
        self.assertIsNone(panel._interaction_restore_timer)
        self.assertEqual(renders, ["render"])

    def test_selected_file_3d_draw_uses_renderer_draw_path(self):
        panel_class = self._load_gcode_viewer_panel_class()
        draw_calls = []
        canvas = types.SimpleNamespace(
            get_allocated_width=lambda: 800, get_allocated_height=lambda: 480
        )
        panel = object.__new__(panel_class)
        panel.preview_context = "selected_file"
        panel.explicit_filename = "picked.gcode"
        panel.view_mode = DisplayViewMode.MODE_3D
        panel.model = object()
        panel.render_message = None
        panel.viewport = ViewportState()
        panel.camera_3d = types.SimpleNamespace()
        panel.progress = ProgressInfo()
        panel.render_mode = RenderMode.FULL_MODEL
        panel.previous_layers = 0
        panel.show_travel = False
        panel.bed_bounds = None
        panel._interaction_active = False
        panel.renderer = types.SimpleNamespace(
            draw=lambda *args, **kwargs: draw_calls.append((args, kwargs)),
        )

        panel._draw_selected_file_3d_frame(
            canvas,
            object(),
        )

        self.assertEqual(len(draw_calls), 1)
        self.assertEqual(draw_calls[0][1]["preview_context"], PreviewContext.SELECTED_FILE)
        self.assertEqual(draw_calls[0][0][3], DisplayViewMode.MODE_3D)
        self.assertFalse(draw_calls[0][1]["drag_active"])
        self.assertFalse(draw_calls[0][1]["interaction_active"])

    def test_rendering_exception_does_not_persist_2d_or_leave_3d(self):
        panel_class = self._load_gcode_viewer_panel_class()
        calls = []
        config_sets = []
        saves = []
        overlays = []
        panel = object.__new__(panel_class)
        panel.preview_context = "selected_file"
        panel.explicit_filename = "picked.gcode"
        panel.filename = "picked.gcode"
        panel.view_mode = DisplayViewMode.MODE_3D
        panel.model = types.SimpleNamespace(segment_count=1234)
        panel.viewport = ViewportState()
        panel.camera_3d = types.SimpleNamespace()
        panel.progress = ProgressInfo()
        panel.render_mode = RenderMode.FULL_MODEL
        panel.previous_layers = 0
        panel.show_travel = False
        panel.render_message = None
        panel.bed_bounds = None
        panel.drag_state = None
        panel._interaction_active = False
        panel._config = types.SimpleNamespace(
            set=lambda *args, **kwargs: config_sets.append((args, kwargs)),
            save_user_config_options=lambda: saves.append(True),
        )
        panel._draw_3d_error_overlay = lambda *args, **kwargs: overlays.append((args, kwargs))

        def _draw(*args, **kwargs):
            view_mode = args[3]
            calls.append(view_mode)
            if view_mode == DisplayViewMode.MODE_3D:
                raise RuntimeError("boom")

        panel.renderer = types.SimpleNamespace(draw=_draw)

        da = types.SimpleNamespace(
            get_allocated_width=lambda: 800, get_allocated_height=lambda: 480
        )
        panel.on_draw(da, object())

        self.assertEqual(calls, [DisplayViewMode.MODE_3D, DisplayViewMode.MODE_2D])
        self.assertEqual(panel.view_mode, DisplayViewMode.MODE_3D)
        self.assertEqual(config_sets, [])
        self.assertEqual(saves, [])
        self.assertEqual(len(overlays), 1)

    def test_manual_selecting_2d_still_persists_normally(self):
        panel_class = self._load_gcode_viewer_panel_class()
        config_sets = []
        saves = []
        panel = object.__new__(panel_class)
        panel.view_mode = DisplayViewMode.MODE_3D
        panel.model = None
        panel.camera_3d = types.SimpleNamespace(fitted=False)
        panel.viewport = types.SimpleNamespace(fitted=False)
        panel._config = types.SimpleNamespace(
            set=lambda *args, **kwargs: config_sets.append((args, kwargs)),
            save_user_config_options=lambda: saves.append(True),
        )
        panel._update_control_labels = lambda: None
        panel._sync_blanking_inhibition = lambda: None
        panel.queue_render = lambda: None

        panel.set_view_mode(None, DisplayViewMode.MODE_2D)

        self.assertEqual(panel.view_mode, DisplayViewMode.MODE_2D)
        self.assertEqual(
            config_sets[0][0], ("main", "gcode_renderer_view", DisplayViewMode.MODE_2D.value)
        )
        self.assertEqual(saves, [True])

    def test_successful_3d_draw_remains_in_3d(self):
        panel_class = self._load_gcode_viewer_panel_class()
        calls = []
        panel = object.__new__(panel_class)
        panel.preview_context = "selected_file"
        panel.explicit_filename = "picked.gcode"
        panel.view_mode = DisplayViewMode.MODE_3D
        panel.model = object()
        panel.viewport = ViewportState()
        panel.camera_3d = types.SimpleNamespace()
        panel.progress = ProgressInfo()
        panel.render_mode = RenderMode.FULL_MODEL
        panel.previous_layers = 0
        panel.show_travel = False
        panel.render_message = None
        panel.bed_bounds = None
        panel.drag_state = None
        panel._interaction_active = False
        panel._draw_3d_error_overlay = lambda *args, **kwargs: self.fail(
            "3D error overlay should not be shown"
        )
        panel.renderer = types.SimpleNamespace(draw=lambda *args, **kwargs: calls.append(args[3]))

        da = types.SimpleNamespace(
            get_allocated_width=lambda: 800, get_allocated_height=lambda: 480
        )
        panel.on_draw(da, object())

        self.assertEqual(calls, [DisplayViewMode.MODE_3D])
        self.assertEqual(panel.view_mode, DisplayViewMode.MODE_3D)

    def test_active_print_3d_draw_path_remains_renderer_based(self):
        panel_class = self._load_gcode_viewer_panel_class()
        calls = []
        panel = object.__new__(panel_class)
        panel.preview_context = "active_print"
        panel.explicit_filename = ""
        panel.view_mode = DisplayViewMode.MODE_3D
        panel.model = object()
        panel.viewport = ViewportState()
        panel.camera_3d = types.SimpleNamespace()
        panel.progress = ProgressInfo()
        panel.render_mode = RenderMode.CURRENT_AND_PREVIOUS
        panel.previous_layers = 3
        panel.show_travel = True
        panel.render_message = None
        panel.bed_bounds = None
        panel.drag_state = None
        panel._interaction_active = False
        panel._draw_3d_error_overlay = lambda *args, **kwargs: self.fail(
            "3D error overlay should not be shown"
        )
        panel.renderer = types.SimpleNamespace(draw=lambda *args, **kwargs: calls.append(args[3]))

        da = types.SimpleNamespace(
            get_allocated_width=lambda: 800, get_allocated_height=lambda: 480
        )
        panel.on_draw(da, object())

        self.assertEqual(calls, [DisplayViewMode.MODE_3D])

    def test_file_list_preview_action_passes_filename_and_context(self):
        panel_class = self._load_gcodes_panel_class()
        calls = []
        panel = object.__new__(panel_class)
        panel._screen = types.SimpleNamespace(
            show_panel=lambda *args, **kwargs: calls.append((args, kwargs))
        )

        panel.open_preview(None, "folder/part.gcode")

        self.assertEqual(
            calls,
            [
                (
                    ("gcode_viewer",),
                    {
                        "title": "Preview",
                        "filename": "folder/part.gcode",
                        "preview_context": "selected_file",
                    },
                )
            ],
        )

    def test_file_list_preview_icon_and_actions_are_present_without_replacing_edit_delete(self):
        gcodes_path = os.path.join(REPO_ROOT, "panels", "gcodes.py")
        with open(gcodes_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('PREVIEW_ICON = "bed-mesh"', source)
        self.assertIn('preview.connect("clicked", self.open_preview, path)', source)
        self.assertIn('rename.connect("clicked", self.show_rename', source)
        self.assertIn('delete.connect("clicked", self.confirm_delete_file', source)
        self.assertNotIn("preview.hide()", source)
        self.assertIn("tile.add(actions)", source)

    def test_enabled_renderer_list_file_constructs_preview_action(self):
        panel = self._make_gcodes_panel(list_mode=True, renderer_enabled=True)
        created_icons = []
        panel._build_action_button = lambda icon_name, color: (
            created_icons.append(icon_name) or _ActionButtonStub(icon_name)
        )

        child = panel.create_item({"filename": "part.gcode", "modified": 1, "size": 10})

        self.assertIsNotNone(child)
        self.assertIn(panel.PREVIEW_ICON, created_icons)
        self.assertTrue(self._find_icon_widget(child, panel.PREVIEW_ICON))

    def test_disabled_renderer_list_file_has_no_preview_action(self):
        panel = self._make_gcodes_panel(list_mode=True, renderer_enabled=False)
        created_icons = []
        panel._build_action_button = lambda icon_name, color: (
            created_icons.append(icon_name) or _ActionButtonStub(icon_name)
        )

        child = panel.create_item({"filename": "part.gcode", "modified": 1, "size": 10})

        self.assertIsNotNone(child)
        self.assertNotIn(panel.PREVIEW_ICON, created_icons)
        self.assertFalse(self._find_icon_widget(child, panel.PREVIEW_ICON))

    def test_directory_row_does_not_construct_or_attach_preview_action(self):
        panel = self._make_gcodes_panel(list_mode=True, renderer_enabled=True)
        created_icons = []
        panel._build_action_button = lambda icon_name, color: (
            created_icons.append(icon_name) or _ActionButtonStub(icon_name)
        )

        child = panel.create_item({"dirname": "folder", "modified": 1, "size": 0})

        self.assertIsNotNone(child)
        self.assertNotIn(panel.PREVIEW_ICON, created_icons)
        self.assertFalse(self._find_icon_widget(child, panel.PREVIEW_ICON))

    def test_directory_row_show_all_cannot_expose_preview(self):
        panel = self._make_gcodes_panel(list_mode=True, renderer_enabled=False)
        child = panel.create_item({"dirname": "folder", "modified": 1, "size": 0})

        child.show_all()

        self.assertFalse(self._find_icon_widget(child, panel.PREVIEW_ICON))

    def test_thumbnail_directory_does_not_construct_preview_action(self):
        panel = self._make_gcodes_panel(list_mode=False, renderer_enabled=True)
        created_icons = []
        panel._build_action_button = lambda icon_name, color: (
            created_icons.append(icon_name) or _ActionButtonStub(icon_name)
        )

        child = panel.create_item({"dirname": "folder", "modified": 1, "size": 0})

        self.assertIsNotNone(child)
        self.assertNotIn(panel.PREVIEW_ICON, created_icons)
        self.assertFalse(self._find_icon_widget(child, panel.PREVIEW_ICON))

    def test_enabled_renderer_thumbnail_file_constructs_preview_action(self):
        panel = self._make_gcodes_panel(list_mode=False, renderer_enabled=True)
        created_icons = []
        panel._build_action_button = lambda icon_name, color: (
            created_icons.append(icon_name) or _ActionButtonStub(icon_name)
        )

        child = panel.create_item({"filename": "part.gcode", "modified": 1, "size": 10})

        self.assertIsNotNone(child)
        self.assertIn(panel.PREVIEW_ICON, created_icons)
        self.assertTrue(self._find_icon_widget(child, panel.PREVIEW_ICON))

    def test_disabled_renderer_thumbnail_file_has_no_preview_action(self):
        panel = self._make_gcodes_panel(list_mode=False, renderer_enabled=False)
        created_icons = []
        panel._build_action_button = lambda icon_name, color: (
            created_icons.append(icon_name) or _ActionButtonStub(icon_name)
        )

        child = panel.create_item({"filename": "part.gcode", "modified": 1, "size": 10})

        self.assertIsNotNone(child)
        self.assertNotIn(panel.PREVIEW_ICON, created_icons)
        self.assertFalse(self._find_icon_widget(child, panel.PREVIEW_ICON))

    def test_print_menu_preview_context_is_explicit(self):
        menu_path = os.path.join(REPO_ROOT, "config", "print_menu.conf")
        with open(menu_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('params: {"preview_context": "active_print"}', source)

    def test_screen_panel_menu_item_passes_panel_params(self):
        screen_panel_class = self._load_screen_panel_class()
        calls = []
        panel = object.__new__(screen_panel_class)
        panel._screen = types.SimpleNamespace(
            show_panel=lambda *args, **kwargs: calls.append((args, kwargs))
        )

        screen_panel_class.menu_item_clicked(
            panel,
            None,
            {
                "panel": "gcode_viewer",
                "name": "Preview",
                "params": '{"preview_context": "active_print"}',
            },
        )

        self.assertEqual(
            calls,
            [(("gcode_viewer",), {"title": "Preview", "preview_context": "active_print"})],
        )

    def test_screen_show_panel_uses_context_specific_preview_panel_names(self):
        module = self._load_screen_module()
        init_calls = []

        class _PanelStub:
            def __init__(self, screen, title=None, **kwargs):
                init_calls.append((title, dict(kwargs)))
                self.menu = []

        fake_screen = types.SimpleNamespace(
            panels={},
            panels_reinit=[],
            _cur_panels=[],
            dialogs=[],
            gtk=types.SimpleNamespace(remove_dialog=lambda dialog: None),
            lock_screen=types.SimpleNamespace(lock=lambda *args, **kwargs: None),
            _load_panel=lambda panel: types.SimpleNamespace(Panel=_PanelStub),
            _remove_current_panel=lambda: None,
            _remove_all_panels=lambda: None,
            _menu_go_back=lambda home=False: None,
            attach_panel=lambda panel_name: None,
            set_titlebar_items=lambda panel: None,
            show_error_modal=lambda *args, **kwargs: self.fail("show_panel should not error"),
        )

        module.KlipperScreen.show_panel(
            fake_screen,
            "gcode_viewer",
            title="Preview",
            filename="folder/part.gcode",
            preview_context="selected_file",
        )
        module.KlipperScreen.show_panel(
            fake_screen,
            "gcode_viewer",
            title="Preview",
            preview_context="active_print",
        )

        self.assertIn("gcode_viewer_selected", fake_screen.panels)
        self.assertIn("gcode_viewer_active", fake_screen.panels)
        self.assertEqual(init_calls[0][1]["filename"], "folder/part.gcode")
        self.assertEqual(init_calls[0][1]["preview_context"], "selected_file")
        self.assertEqual(init_calls[1][1]["preview_context"], "active_print")

    def test_screen_show_panel_reinitializes_selected_preview_for_new_filename(self):
        module = self._load_screen_module()

        class _PanelStub:
            def __init__(self, screen, title=None, **kwargs):
                calls = getattr(self, "init_calls", [])
                calls.append((title, dict(kwargs)))
                self.init_calls = calls
                self.menu = []

        panel_module = types.SimpleNamespace(Panel=_PanelStub)
        fake_screen = types.SimpleNamespace(
            panels={},
            panels_reinit=[],
            _cur_panels=[],
            dialogs=[],
            gtk=types.SimpleNamespace(remove_dialog=lambda dialog: None),
            lock_screen=types.SimpleNamespace(lock=lambda *args, **kwargs: None),
            _load_panel=lambda panel: panel_module,
            _remove_current_panel=lambda: None,
            _remove_all_panels=lambda: None,
            _menu_go_back=lambda home=False: None,
            attach_panel=lambda panel_name: None,
            set_titlebar_items=lambda panel: None,
            show_error_modal=lambda *args, **kwargs: self.fail("show_panel should not error"),
        )

        module.KlipperScreen.show_panel(
            fake_screen,
            "gcode_viewer",
            title="Preview",
            filename="folder/one.gcode",
            preview_context="selected_file",
        )
        fake_screen._cur_panels = ["gcodes"]
        module.KlipperScreen.show_panel(
            fake_screen,
            "gcode_viewer",
            title="Preview",
            filename="folder/two.gcode",
            preview_context="selected_file",
        )

        panel = fake_screen.panels["gcode_viewer_selected"]
        self.assertEqual(len(panel.init_calls), 2)
        self.assertEqual(panel.init_calls[0][1]["filename"], "folder/one.gcode")
        self.assertEqual(panel.init_calls[1][1]["filename"], "folder/two.gcode")

    def test_load_tracker_single_flight_and_cancellation(self):
        tracker = LoadTracker()
        tracker.activate()
        first = tracker.begin("a.gcode")
        self.assertEqual(first, 1)
        self.assertIsNone(tracker.begin("a.gcode"))
        self.assertEqual(tracker.finish(first, "a.gcode"), "accepted")

        second = tracker.begin("b.gcode")
        tracker.deactivate()
        self.assertEqual(tracker.finish(second, "b.gcode"), "inactive")

        tracker.activate("b.gcode")
        self.assertEqual(tracker.finish(second, "b.gcode"), "accepted")

        third = tracker.begin("c.gcode")
        self.assertEqual(tracker.finish(third + 1, "c.gcode"), "stale")

    def test_filename_resolution_prefers_non_empty_sources_without_erasing_current_filename(self):
        self.assertEqual(
            resolve_active_filename(
                printer_filename="active.gcode",
                explicit_filename="menu.gcode",
                current_filename="held.gcode",
                virtual_sdcard_status={"file_path": "sd.gcode"},
            ),
            "active.gcode",
        )
        self.assertEqual(
            resolve_active_filename(
                printer_filename="",
                explicit_filename="menu.gcode",
                current_filename="held.gcode",
                virtual_sdcard_status={"file_path": "sd.gcode"},
            ),
            "menu.gcode",
        )
        self.assertEqual(
            resolve_active_filename(
                printer_filename="",
                explicit_filename="",
                current_filename="held.gcode",
                virtual_sdcard_status={"file_path": "sd.gcode"},
            ),
            "held.gcode",
        )
        self.assertEqual(
            resolve_active_filename(
                printer_filename="",
                explicit_filename="",
                current_filename="",
                virtual_sdcard_status={"file_path": "sd.gcode"},
            ),
            "sd.gcode",
        )
        self.assertFalse(should_clear_active_filename("held.gcode", "held.gcode", "printing"))
        self.assertTrue(should_clear_active_filename("held.gcode", "", "standby"))

    def test_cache_rejects_old_version_and_malformed_model(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\n", "cache.gcode", file_size=24, modified=1.0
        )
        self.assertEqual(validate_toolpath_model(model), (True, "valid"))

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = GcodeRenderCache(tmpdir)
            entry = cache.make_entry("cache.gcode", 24, 1.0)
            path = cache._cache_path(entry.fingerprint)

            with open(path, "wb") as handle:
                pickle.dump(
                    {
                        "version": GcodeRenderCache.CACHE_VERSION - 1,
                        "fingerprint": entry.fingerprint,
                        "model": model,
                    },
                    handle,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            self.assertIsNone(cache.load(entry))

            malformed = parse_gcode(
                b"G90\nM82\nG1 Z0.2\nG1 X1 Y1 E1.0\n",
                "cache.gcode",
                file_size=24,
                modified=1.0,
            )
            malformed.segments = [(0.0, 0.0, 1.0, 1.0, 0.2, 0, 1, 10)]
            with open(path, "wb") as handle:
                pickle.dump(
                    {
                        "version": GcodeRenderCache.CACHE_VERSION,
                        "fingerprint": entry.fingerprint,
                        "model": malformed,
                    },
                    handle,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            self.assertIsNone(cache.load(entry))
            self.assertFalse(os.path.exists(path))

    def test_gcode_viewer_transient_empty_printer_filename_does_not_erase_loaded_filename(self):
        panel_class = self._load_gcode_viewer_panel_class()
        panel = object.__new__(panel_class)
        scheduled = []
        panel._printer = _PanelPrinterStub(print_state="printing", print_filename="")
        panel.explicit_filename = ""
        panel.filename = "held.gcode"
        panel.file_metadata = {}
        panel.metadata_requested_for = ""
        panel.model = object()
        panel.progress = ProgressInfo()
        panel.viewport = types.SimpleNamespace(fitted=True)
        panel.camera_3d = types.SimpleNamespace(fitted=True)
        panel.load_tracker = LoadTracker(panel_active=True)
        panel.pending_load_result = None
        panel.last_progress_signature = None
        panel.enabled = True
        panel.render_message = None
        panel.view_mode = DisplayViewMode.MODE_2D
        panel.refresh_interval = 5
        panel.show_travel = False
        panel.previous_layers = 3
        panel.render_mode = RenderMode.CURRENT_LAYER
        panel._files = _PanelFilesStub("", {})
        panel._config = types.SimpleNamespace(get_main_config=lambda: {})
        panel._sync_settings = lambda sync_view_mode=False: None
        panel._refresh_metadata = lambda: None
        panel._set_panel_state = lambda *args, **kwargs: None
        panel.queue_render = lambda: None
        panel._update_progress = lambda: False
        panel._apply_pending_load_result = lambda: False
        panel._schedule_load = lambda force_reload=False: scheduled.append(force_reload)

        panel._refresh_from_printer()

        self.assertEqual(panel.filename, "held.gcode")
        self.assertEqual(scheduled, [])

    def test_gcode_viewer_loading_lifecycle_loads_once_and_reuses_model_across_view_modes(self):
        panel_class = self._load_gcode_viewer_panel_class()
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = "sample.gcode"
            full_path = os.path.join(tmpdir, filename)
            payload = b"G90\nM82\nG1 Z0.2\nG1 X10 Y0 E1.0\nG1 X10 Y10 E2.0\n"
            with open(full_path, "wb") as handle:
                handle.write(payload)

            metadata = {filename: {"size": len(payload), "modified": 123.0, "path": filename}}
            panel = object.__new__(panel_class)
            panel._printer = _PanelPrinterStub(print_state="printing", print_filename=filename)
            panel._files = _PanelFilesStub(tmpdir, metadata)
            panel._screen = types.SimpleNamespace(restApi=_PanelRestStub())
            panel._config = types.SimpleNamespace(
                get_main_config=lambda: {},
                set=lambda *args, **kwargs: None,
                save_user_config_options=lambda: None,
            )
            panel.explicit_filename = ""
            panel.filename = ""
            panel.file_metadata = {}
            panel.metadata_requested_for = ""
            panel.model = None
            panel.progress = ProgressInfo()
            panel.viewport = types.SimpleNamespace(fitted=False, user_modified=False)
            panel.camera_3d = types.SimpleNamespace(fitted=False, user_modified=False)
            panel.cache = GcodeRenderCache(os.path.join(tmpdir, "cache"))
            panel.load_tracker = LoadTracker(panel_active=True)
            panel.executor = _ImmediateExecutor()
            panel.pending_load_result = None
            panel.last_progress_signature = None
            panel.print_state = "printing"
            panel.panel_state = "idle"
            panel.render_message = None
            panel.enabled = True
            panel.refresh_interval = 5
            panel.show_travel = False
            panel.previous_layers = 3
            panel.render_mode = RenderMode.CURRENT_LAYER
            panel.view_mode = DisplayViewMode.MODE_2D
            panel._sync_settings = lambda sync_view_mode=False: None
            panel._refresh_metadata = lambda: setattr(
                panel, "file_metadata", dict(metadata[filename])
            )
            panel._update_progress = lambda: False
            panel.queue_render = lambda: None
            panel._fit_view_to_model = lambda force=False: None
            panel._update_control_labels = lambda: None
            panel._set_panel_state = lambda state, detail=None: setattr(panel, "panel_state", state)

            panel._refresh_from_printer()

            self.assertEqual(panel.filename, filename)
            self.assertIsNotNone(panel.model)
            self.assertEqual(panel.panel_state, "ready")
            self.assertEqual(panel.executor.submit_count, 1)

            model_before_switch = panel.model
            panel.set_view_mode(None, DisplayViewMode.MODE_3D)
            self.assertEqual(panel.view_mode, DisplayViewMode.MODE_3D)
            self.assertIs(panel.model, model_before_switch)

            panel._refresh_from_printer()
            self.assertEqual(panel.executor.submit_count, 1)

    def test_local_file_loading_stays_inside_gcodes_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = os.path.join(tmpdir, "subdir")
            os.makedirs(target_dir)
            target = os.path.join(target_dir, "part.gcode")
            with open(target, "wb") as handle:
                handle.write(b"G1 X1 Y1 E1.0\n")

            resolved = resolve_local_gcode_path(tmpdir, "subdir/part.gcode")
            self.assertEqual(os.path.realpath(resolved), os.path.realpath(target))
            self.assertIsNone(resolve_local_gcode_path(tmpdir, "../escape.gcode"))
            self.assertEqual(load_local_gcode(tmpdir, "subdir/part.gcode")[1], b"G1 X1 Y1 E1.0\n")

    def test_gcode_stream_uses_extended_timeout_without_changing_default_get_timeout(self):
        rest = _CaptureRest()
        self.assertEqual(rest.send_request("printer/info"), {})
        self.assertEqual(rest.calls[-1]["timeout"], 4)

        payload = rest.get_gcode_stream("folder name/part.gcode")
        self.assertEqual(payload, b"ok")
        self.assertEqual(rest.calls[-1]["timeout"], 60)
        self.assertEqual(rest.calls[-1]["method"], "server/files/gcodes/folder%20name/part.gcode")

    def test_renderer_options_are_saved_in_main_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "KlipperScreen.conf")
            with open(config_path, "w", encoding="utf-8") as handle:
                handle.write("[main]\n")

            config = KlipperScreenConfig(config_path, screen=_ScreenStub())
            config.set("main", "enable_gcode_renderer", "True")
            config.set("main", "gcode_renderer_view", DisplayViewMode.MODE_3D.value)
            config.set("main", "gcode_renderer_mode", RenderMode.FULL_MODEL.value)
            config.set("main", "gcode_renderer_previous_layers", "4")
            config.save_user_config_options()

            with open(config_path, "r", encoding="utf-8") as handle:
                saved = handle.read()

            self.assertIn("enable_gcode_renderer = True", saved)
            self.assertIn("gcode_renderer_view = 3d", saved)
            self.assertIn("gcode_renderer_mode = full_model", saved)
            self.assertIn("gcode_renderer_previous_layers = 4", saved)

    def test_settings_panel_source_contains_renderer_submenu(self):
        settings_path = os.path.join(REPO_ROOT, "panels", "settings.py")
        with open(settings_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("RENDERER_OPTION_KEYS", source)
        self.assertIn('"gcode_renderer_menu"', source)
        self.assertIn("G-code Renderer", source)

    def test_renderer_settings_submenu_places_enable_first(self):
        panel_class = self._load_settings_panel_class()
        options = [
            {"gcode_renderer_view": {"name": "View"}},
            {"gcode_renderer_mode": {"name": "Mode"}},
            {"enable_gcode_renderer": {"name": "Enable"}},
            {"gcode_renderer_fps": {"name": "FPS"}},
        ]
        screen = types.SimpleNamespace(
            _config=types.SimpleNamespace(
                get_configurable_options=lambda: list(options),
                get_printers=lambda: [],
                lang_list=[],
            ),
            change_language=lambda *args, **kwargs: None,
            gtk=types.SimpleNamespace(ScrolledWindow=lambda: _GtkWidgetStub()),
        )
        added = []
        screen_panel_class = panel_class.__mro__[1]
        original_add_option = screen_panel_class.add_option
        screen_panel_class.add_option = lambda self, section, store, name, option: added.append(
            (section, name)
        )
        try:
            panel_class(screen, title="Settings")
        finally:
            screen_panel_class.add_option = original_add_option

        renderer_names = [name for section, name in added if section == "gcode_renderer"]
        self.assertEqual(
            renderer_names,
            [
                "enable_gcode_renderer",
                "gcode_renderer_view",
                "gcode_renderer_mode",
                "gcode_renderer_fps",
            ],
        )

    def test_job_status_source_keeps_original_thumbnail_layout(self):
        job_status_path = os.path.join(REPO_ROOT, "panels", "job_status.py")
        with open(job_status_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn(
            'self.labels["info_grid"].attach(self.labels["thumbnail"], 0, 0, 1, 1)', source
        )
        self.assertNotIn("preview_button", source)
        self.assertNotIn("thumb_box", source)
        self.assertNotIn("show_toolpath_preview", source)

    def test_print_menu_source_contains_preview_entry(self):
        menu_path = os.path.join(REPO_ROOT, "config", "print_menu.conf")
        with open(menu_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("[menu __print preview]", source)
        self.assertIn("panel: gcode_viewer", source)
        self.assertIn("klipperscreen.gcode_renderer.preview_available", source)

    def test_print_menu_preview_icon_uses_existing_bed_mesh_asset(self):
        menu_path = os.path.join(REPO_ROOT, "config", "print_menu.conf")
        with open(menu_path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("icon: bed-mesh", source)
        self.assertNotIn("icon: file", source)

        styles_dir = os.path.join(REPO_ROOT, "styles")
        themed_dirs = [
            entry
            for entry in os.listdir(styles_dir)
            if os.path.isdir(os.path.join(styles_dir, entry, "images"))
        ]
        self.assertGreater(len(themed_dirs), 0)
        for theme in themed_dirs:
            icon_path = os.path.join(styles_dir, theme, "images", "bed-mesh.svg")
            self.assertTrue(
                os.path.exists(icon_path), msg=f"Missing bed-mesh icon for theme {theme}"
            )

    def test_active_3d_preview_acquires_screen_blanking_inhibition(self):
        panel_class = self._load_gcode_viewer_panel_class()
        screensaver = _PanelScreensaverStub()
        panel = object.__new__(panel_class)
        panel._screen = types.SimpleNamespace(screensaver=screensaver)
        panel.preview_context = "active_print"
        panel.panel_active = True
        panel.enabled = True
        panel.view_mode = DisplayViewMode.MODE_3D

        panel._sync_blanking_inhibition()

        self.assertEqual(
            screensaver.calls,
            [("inhibit", panel_class.BLANKING_INHIBIT_OWNER)],
        )

    def test_2d_preview_does_not_acquire_screen_blanking_inhibition(self):
        panel_class = self._load_gcode_viewer_panel_class()
        screensaver = _PanelScreensaverStub()
        panel = object.__new__(panel_class)
        panel._screen = types.SimpleNamespace(screensaver=screensaver)
        panel.preview_context = "active_print"
        panel.panel_active = True
        panel.enabled = True
        panel.view_mode = DisplayViewMode.MODE_2D

        panel._sync_blanking_inhibition()

        self.assertFalse(any(call[0] == "inhibit" for call in screensaver.calls))

    def test_switching_from_3d_to_2d_releases_screen_blanking_inhibition(self):
        panel_class = self._load_gcode_viewer_panel_class()
        screensaver = _PanelScreensaverStub()
        panel = object.__new__(panel_class)
        panel._screen = types.SimpleNamespace(screensaver=screensaver)
        panel.preview_context = "active_print"
        panel.panel_active = True
        panel.enabled = True
        panel.view_mode = DisplayViewMode.MODE_3D

        panel._sync_blanking_inhibition()
        panel.view_mode = DisplayViewMode.MODE_2D
        panel._sync_blanking_inhibition()

        self.assertEqual(
            screensaver.calls,
            [
                ("inhibit", panel_class.BLANKING_INHIBIT_OWNER),
                ("release", panel_class.BLANKING_INHIBIT_OWNER),
            ],
        )

    def test_gcode_viewer_deactivate_releases_screen_blanking_inhibition(self):
        panel_class = self._load_gcode_viewer_panel_class()
        screensaver = _PanelScreensaverStub()
        panel = object.__new__(panel_class)
        panel._screen = types.SimpleNamespace(screensaver=screensaver)
        panel.preview_context = "active_print"
        panel.load_tracker = types.SimpleNamespace(deactivate=lambda: None)
        panel.refresh_timer = None
        panel.controls_revealer = None
        panel.drag_state = (1, 1)
        panel.panel_active = True
        panel.enabled = True
        panel.view_mode = DisplayViewMode.MODE_3D

        panel._sync_blanking_inhibition()
        panel.deactivate()

        self.assertFalse(panel.panel_active)
        self.assertEqual(
            screensaver.calls,
            [
                ("inhibit", panel_class.BLANKING_INHIBIT_OWNER),
                ("release", panel_class.BLANKING_INHIBIT_OWNER),
            ],
        )

    def test_selected_file_preview_does_not_inhibit_screen_blanking(self):
        panel_class = self._load_gcode_viewer_panel_class()
        screensaver = _PanelScreensaverStub()
        panel = object.__new__(panel_class)
        panel._screen = types.SimpleNamespace(screensaver=screensaver)
        panel.preview_context = "selected_file"
        panel.panel_active = True
        panel.enabled = True
        panel.view_mode = DisplayViewMode.MODE_3D

        panel._sync_blanking_inhibition()

        self.assertEqual(
            screensaver.calls,
            [("release", panel_class.BLANKING_INHIBIT_OWNER)],
        )

    def test_screensaver_inhibition_is_idempotent_and_restores_timeout_after_final_release(self):
        module = self._load_screensaver_module()
        tracker = _GLibTracker()
        module.GLib = tracker
        screen = _ScreenSaverScreenStub()
        saver = module.ScreenSaver(screen)
        saver.screensaver_timeout = 41

        self.assertTrue(saver.inhibit("preview-3d"))
        self.assertFalse(saver.inhibit("preview-3d"))
        self.assertEqual(tracker.removed, [41])
        self.assertEqual(screen.runtime_calls, [True])
        self.assertFalse(saver.release("missing-owner"))
        self.assertTrue(saver.release("preview-3d"))
        self.assertFalse(saver.release("preview-3d"))
        self.assertEqual(screen.runtime_calls, [True, False])
        self.assertEqual(screen.reset_calls, 1)

    def test_screensaver_inhibition_does_not_modify_configured_blanking_values(self):
        module = self._load_screensaver_module()
        tracker = _GLibTracker()
        module.GLib = tracker
        screen = _ScreenSaverScreenStub(
            values={
                "screen_blanking": "120",
                "screen_blanking_printing": "3600",
                "screensaver_wake_delay": "2",
            }
        )
        original = dict(screen._config.values)
        saver = module.ScreenSaver(screen)

        saver.inhibit("preview-3d")
        saver.reset_timeout()
        saver.show()
        saver.release("preview-3d")

        self.assertEqual(screen._config.values, original)
        self.assertEqual(tracker.timeouts, [])

    def _parse_gcode_viewer_module(self):
        viewer_path = os.path.join(REPO_ROOT, "panels", "gcode_viewer.py")
        with open(viewer_path, "r", encoding="utf-8") as handle:
            return ast.parse(handle.read(), filename=viewer_path)

    def _load_gcode_viewer_panel_class(self):
        gi_module = sys.modules.get("gi")
        if gi_module is None:
            gi_module = types.ModuleType("gi")
            sys.modules["gi"] = gi_module
        gi_module.require_version = lambda *args, **kwargs: None

        repository_module = types.ModuleType("gi.repository")
        gtk_stub = types.SimpleNamespace(
            ScrolledWindow=_GtkWidgetStub,
            DrawingArea=_GtkWidgetStub,
            StyleContext=type("StyleContext", (object,), {}),
            Container=type("Container", (object,), {}),
            Bin=type("Bin", (object,), {}),
            Button=_GtkWidgetStub,
            Alignment=_GtkWidgetStub,
            Box=_GtkWidgetStub,
            Label=_GtkWidgetStub,
            Spinner=_GtkWidgetStub,
            Grid=_GtkWidgetStub,
            Overlay=_GtkWidgetStub,
            PolicyType=types.SimpleNamespace(NEVER=0, AUTOMATIC=1),
            Orientation=types.SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
            Align=types.SimpleNamespace(CENTER=0, END=1, FILL=2),
            Justification=types.SimpleNamespace(CENTER=0),
            RevealerTransitionType=types.SimpleNamespace(SLIDE_LEFT=0),
        )
        repository_module.Gtk = gtk_stub
        repository_module.Gdk = types.SimpleNamespace(
            EventMask=types.SimpleNamespace(
                BUTTON_PRESS_MASK=1,
                BUTTON_RELEASE_MASK=2,
                BUTTON1_MOTION_MASK=4,
                TOUCH_MASK=8,
            )
        )
        repository_module.GLib = types.SimpleNamespace(
            idle_add=lambda func, *args: func(*args),
            timeout_add=lambda *args, **kwargs: 1,
            source_remove=lambda *args, **kwargs: None,
        )
        repository_module.Pango = types.SimpleNamespace(
            WrapMode=types.SimpleNamespace(WORD_CHAR=0),
            EllipsizeMode=types.SimpleNamespace(END=0),
        )
        repository_module.GdkPixbuf = types.SimpleNamespace(
            Pixbuf=type(
                "Pixbuf",
                (),
                {
                    "new_from_file_at_size": staticmethod(lambda *args, **kwargs: None),
                    "new_from_stream_at_scale": staticmethod(lambda *args, **kwargs: None),
                },
            )
        )
        repository_module.Gio = types.SimpleNamespace(
            MemoryInputStream=types.SimpleNamespace(
                new_from_data=lambda *args, **kwargs: types.SimpleNamespace(
                    close_async=lambda *close_args, **close_kwargs: None
                )
            )
        )
        sys.modules["gi.repository"] = repository_module
        sys.modules["cairo"] = types.SimpleNamespace(Context=object)
        screen_panel_module = types.ModuleType("ks_includes.screen_panel")

        class _ScreenPanelStub:
            def __init__(self, screen, title, **kwargs):
                self._screen = screen
                self._config = screen._config
                self._printer = screen.printer
                self._files = screen.files
                self._gtk = screen.gtk
                self.labels = {}
                self.control = {}
                self.title = title
                self.bts = getattr(self._gtk, "bsidescale", 1)
                self.content = _GtkWidgetStub()

        screen_panel_module.ScreenPanel = _ScreenPanelStub
        sys.modules["ks_includes.screen_panel"] = screen_panel_module
        klippygtk_module = types.ModuleType("ks_includes.KlippyGtk")
        klippygtk_module.find_widget = lambda *args, **kwargs: None
        sys.modules["ks_includes.KlippyGtk"] = klippygtk_module

        for module_name in (
            "panels.gcode_viewer",
            "ks_includes.widgets.scroll",
        ):
            sys.modules.pop(module_name, None)
        module = importlib.import_module("panels.gcode_viewer")
        module._ = lambda text: text
        return module.Panel

    def _load_gcodes_panel_class(self):
        gi_module = sys.modules.get("gi")
        if gi_module is None:
            gi_module = types.ModuleType("gi")
            sys.modules["gi"] = gi_module
        gi_module.require_version = lambda *args, **kwargs: None

        repository_module = types.ModuleType("gi.repository")
        repository_module.Gtk = types.SimpleNamespace(
            Label=_GtkWidgetStub,
            Button=_GtkWidgetStub,
            Box=_GtkWidgetStub,
            Grid=_GtkWidgetStub,
            FlowBox=_GtkWidgetStub,
            Image=_GtkWidgetStub,
            PolicyType=types.SimpleNamespace(NEVER=0, AUTOMATIC=1),
            SelectionMode=types.SimpleNamespace(NONE=0),
            Align=types.SimpleNamespace(START=0, END=1, CENTER=2),
            Orientation=types.SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
            PositionType=types.SimpleNamespace(RIGHT=0),
            ResponseType=types.SimpleNamespace(REJECT=0, OK=1, CANCEL=2),
        )
        repository_module.Pango = types.SimpleNamespace(
            WrapMode=types.SimpleNamespace(CHAR=0, WORD_CHAR=1),
            EllipsizeMode=types.SimpleNamespace(END=0),
        )
        sys.modules["gi.repository"] = repository_module

        klippygtk_module = types.ModuleType("ks_includes.KlippyGtk")
        klippygtk_module.find_widget = lambda *args, **kwargs: None
        sys.modules["ks_includes.KlippyGtk"] = klippygtk_module
        flowbox_module = types.ModuleType("ks_includes.widgets.flowboxchild_extended")
        flowbox_module.PrintListItem = _PrintListItemStub
        sys.modules["ks_includes.widgets.flowboxchild_extended"] = flowbox_module
        screen_panel_module = types.ModuleType("ks_includes.screen_panel")
        screen_panel_module.ScreenPanel = type("ScreenPanel", (object,), {})
        sys.modules["ks_includes.screen_panel"] = screen_panel_module

        sys.modules.pop("panels.gcodes", None)
        module = importlib.import_module("panels.gcodes")
        module._ = lambda text: text
        return module.Panel

    def _load_settings_panel_class(self):
        gi_module = sys.modules.get("gi")
        if gi_module is None:
            gi_module = types.ModuleType("gi")
            sys.modules["gi"] = gi_module
        gi_module.require_version = lambda *args, **kwargs: None

        repository_module = types.ModuleType("gi.repository")
        repository_module.Gtk = types.SimpleNamespace(
            Grid=_GtkWidgetStub,
        )
        sys.modules["gi.repository"] = repository_module

        screen_panel_module = types.ModuleType("ks_includes.screen_panel")

        class _ScreenPanelStub:
            def __init__(self, screen, title, **kwargs):
                self._screen = screen
                self._config = screen._config
                self._gtk = screen.gtk
                self.labels = {}
                self.content = _GtkWidgetStub()
                self.menu = []

            def add_option(self, *args, **kwargs):
                return None

        screen_panel_module.ScreenPanel = _ScreenPanelStub
        sys.modules["ks_includes.screen_panel"] = screen_panel_module

        sys.modules.pop("panels.settings", None)
        module = importlib.import_module("panels.settings")
        module._ = lambda text: text
        return module.Panel

    def _load_screensaver_module(self):
        gi_module = sys.modules.get("gi")
        if gi_module is None:
            gi_module = types.ModuleType("gi")
            sys.modules["gi"] = gi_module
        gi_module.require_version = lambda *args, **kwargs: None

        repository_module = types.ModuleType("gi.repository")
        repository_module.GLib = types.SimpleNamespace(
            timeout_add_seconds=lambda *args, **kwargs: 1,
            source_remove=lambda *args, **kwargs: None,
        )
        repository_module.Gtk = types.SimpleNamespace(
            Button=type("Button", (object,), {}),
            Box=type("Box", (object,), {}),
            Align=types.SimpleNamespace(CENTER=0),
        )
        sys.modules["gi.repository"] = repository_module

        sys.modules.pop("ks_includes.widgets.screensaver", None)
        return importlib.import_module("ks_includes.widgets.screensaver")

    def _load_screen_panel_class(self):
        gi_module = sys.modules.get("gi")
        if gi_module is None:
            gi_module = types.ModuleType("gi")
            sys.modules["gi"] = gi_module
        gi_module.require_version = lambda *args, **kwargs: None

        repository_module = types.ModuleType("gi.repository")
        repository_module.GLib = types.SimpleNamespace()
        repository_module.Gtk = types.SimpleNamespace(
            Align=types.SimpleNamespace(START=0, CENTER=1),
            Orientation=types.SimpleNamespace(VERTICAL=0),
            Label=type("Label", (object,), {}),
            Box=type("Box", (object,), {}),
        )
        repository_module.Pango = types.SimpleNamespace(
            WrapMode=types.SimpleNamespace(WORD_CHAR=0),
        )
        sys.modules["gi.repository"] = repository_module

        klippygtk_module = types.ModuleType("ks_includes.KlippyGtk")
        klippygtk_module.find_widget = lambda *args, **kwargs: None
        sys.modules["ks_includes.KlippyGtk"] = klippygtk_module
        sys.modules.pop("ks_includes.screen_panel", None)
        return importlib.import_module("ks_includes.screen_panel").ScreenPanel

    def _load_screen_module(self):
        gi_module = sys.modules.get("gi")
        if gi_module is None:
            gi_module = types.ModuleType("gi")
            sys.modules["gi"] = gi_module
        gi_module.require_version = lambda *args, **kwargs: None

        repository_module = types.ModuleType("gi.repository")
        repository_module.Gdk = types.SimpleNamespace()
        repository_module.GLib = types.SimpleNamespace()
        repository_module.Gtk = types.SimpleNamespace(
            ApplicationWindow=type("ApplicationWindow", (object,), {}),
            Application=type("Application", (object,), {}),
            Overlay=_GtkWidgetStub,
        )
        repository_module.Pango = types.SimpleNamespace()
        sys.modules["gi.repository"] = repository_module

        stubs = {
            "ks_includes.functions": {"dpms_loaded": False},
            "ks_includes.config": {
                "KlipperScreenConfig": type("KlipperScreenConfig", (object,), {})
            },
            "ks_includes.files": {"KlippyFiles": type("KlippyFiles", (object,), {})},
            "ks_includes.KlippyGtk": {"KlippyGtk": type("KlippyGtk", (object,), {})},
            "ks_includes.KlippyRest": {"KlippyRest": type("KlippyRest", (object,), {})},
            "ks_includes.KlippyUDS": {"KlippyUDS": type("KlippyUDS", (object,), {})},
            "ks_includes.KlippyWebsocket": {
                "KlippyWebsocket": type("KlippyWebsocket", (object,), {})
            },
            "ks_includes.notification_handler": {
                "NotificationHandler": type("NotificationHandler", (object,), {})
            },
            "ks_includes.printer": {"Printer": type("Printer", (object,), {})},
            "ks_includes.spoolman_api": {"SpoolmanAPI": type("SpoolmanAPI", (object,), {})},
            "ks_includes.widgets.keyboard": {"Keyboard": type("Keyboard", (object,), {})},
            "ks_includes.widgets.lockscreen": {"LockScreen": type("LockScreen", (object,), {})},
            "ks_includes.widgets.prompts": {"Prompt": type("Prompt", (object,), {})},
            "ks_includes.widgets.screensaver": {"ScreenSaver": type("ScreenSaver", (object,), {})},
            "panels.base_panel": {"BasePanel": type("BasePanel", (object,), {})},
        }
        for module_name, attrs in stubs.items():
            module = types.ModuleType(module_name)
            for attr_name, value in attrs.items():
                setattr(module, attr_name, value)
            sys.modules[module_name] = module
        jinja2_module = types.ModuleType("jinja2")
        jinja2_module.Environment = type("Environment", (object,), {})
        sys.modules["jinja2"] = jinja2_module

        sys.modules.pop("screen", None)
        return importlib.import_module("screen")

    def _build_outlier_model(self):
        from ks_includes.gcode_renderer.parser import parse_gcode

        return parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X10 Y0 E1.0\nG1 X10 Y10 E2.0\nG0 X1000 Y1000\n",
            "outlier.gcode",
        )

    def _make_gcodes_panel(self, *, list_mode, renderer_enabled):
        panel_class = self._load_gcodes_panel_class()
        panel = object.__new__(panel_class)
        panel.PREVIEW_ICON = panel_class.PREVIEW_ICON
        panel.cur_directory = "gcodes"
        panel.list_mode = list_mode
        panel.thumbsize = 48
        panel.list_button_size = 24
        panel._printer = types.SimpleNamespace(extrudercount=1)
        panel._screen = types.SimpleNamespace(
            width=800,
            vertical_mode=False,
            files=types.SimpleNamespace(get_file_info=lambda path: {}),
        )
        panel._gtk = types.SimpleNamespace(
            Button=lambda *args, **kwargs: _GtkWidgetStub(),
            Image=lambda icon_name=None, *args, **kwargs: _ImageStub(icon_name),
        )
        panel._config = types.SimpleNamespace(
            get_main_config=lambda: {
                "enable_gcode_renderer": "True" if renderer_enabled else "False"
            }
        )
        panel.image_load = lambda *args, **kwargs: None
        panel.get_info_str = lambda *args, **kwargs: ""
        panel.confirm_print = lambda *args, **kwargs: None
        panel.confirm_delete_file = lambda *args, **kwargs: None
        panel.confirm_delete_directory = lambda *args, **kwargs: None
        panel.show_rename = lambda *args, **kwargs: None
        panel.change_dir = lambda *args, **kwargs: None
        panel.open_preview = lambda *args, **kwargs: None
        panel._build_action_button = lambda icon_name, color: _ActionButtonStub(icon_name)
        return panel

    def _find_icon_widget(self, widget, icon_name):
        if getattr(widget, "icon_name", None) == icon_name:
            return True
        image = getattr(widget, "image", None)
        if getattr(image, "icon_name", None) == icon_name:
            return True
        for child in getattr(widget, "children", ()):
            if self._find_icon_widget(child, icon_name):
                return True
        return False

    def _find_method(self, module, name):
        for node in module.body:
            if isinstance(node, ast.ClassDef) and node.name == "Panel":
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == name:
                        return child
        self.fail(f"Panel.{name} not found")

    def _assigns_attribute(self, statement, attribute_name):
        if not isinstance(statement, ast.Assign):
            return False
        for target in statement.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                if target.value.id == "self" and target.attr == attribute_name:
                    return True
        return False

    def _calls_method(self, statement, method_name, owner_attr=None):
        for node in ast.walk(statement):
            if self._is_method_call(node, method_name, owner_attr=owner_attr):
                return True
        return False

    @staticmethod
    def _is_method_call(node, method_name, owner_attr=None):
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != method_name:
            return False
        if owner_attr is None:
            return isinstance(func.value, ast.Name) and func.value.id == "self"
        return (
            isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
            and func.value.attr == owner_attr
        )


class _GLibTracker:
    def __init__(self):
        self.removed = []
        self.timeouts = []

    def timeout_add_seconds(self, delay, callback, *args):
        self.timeouts.append((delay, callback, args))
        return len(self.timeouts)

    def source_remove(self, source_id):
        self.removed.append(source_id)


class _VisibleStub:
    def __init__(self):
        self.visible = None

    def set_visible(self, visible):
        self.visible = visible


class _ButtonStateStub(_VisibleStub):
    def __init__(self):
        super().__init__()
        self.label = None
        self.sensitive = True

    def set_label(self, value):
        self.label = value

    def get_style_context(self):
        return _StyleContextStub()

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive


class _ActionButtonStub(_GtkWidgetStub):
    def __init__(self, icon_name=None, label=None):
        super().__init__(label=label)
        self.icon_name = icon_name


class _ImageStub:
    def __init__(self, icon_name=None, *args, **kwargs):
        self.icon_name = icon_name


class _PanelGLibTracker:
    def __init__(self):
        self.timeouts = []
        self.removed = []

    def timeout_add(self, delay, callback, *args):
        self.timeouts.append((delay, callback, args))
        return len(self.timeouts)

    def source_remove(self, source_id):
        self.removed.append(source_id)


class _ScaleStub:
    def __init__(self):
        self.range = None
        self.increments = None
        self.value = None
        self.sensitive = True

    def set_visible(self, visible):
        return None

    def set_range(self, minimum, maximum):
        self.range = (minimum, maximum)

    def set_increments(self, step, page):
        self.increments = (step, page)

    def set_value(self, value):
        self.value = value

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive


class _LabelStub:
    def __init__(self):
        self.value = None

    def set_label(self, value):
        self.value = value


class _ConfigStub:
    def __init__(self, values):
        self.values = dict(values)

    def get_main_config(self):
        return self

    def get(self, key, fallback=None):
        return self.values.get(key, fallback)

    def getint(self, key, fallback=None):
        value = self.values.get(key, fallback)
        return int(value) if value is not None else fallback


class _ScreenSaverScreenStub:
    def __init__(self, values=None):
        self.printer = types.SimpleNamespace(state="ready")
        self._config = _ConfigStub(
            values
            or {
                "screen_blanking": "120",
                "screen_blanking_printing": "3600",
                "screensaver_wake_delay": "1",
            }
        )
        self.blanking_time = 120
        self.use_dpms = False
        self.runtime_calls = []
        self.reset_calls = 0
        self.idle_calls = []
        self.dialogs = []
        self.overlay = types.SimpleNamespace(
            get_children=lambda: [],
            add=lambda *args, **kwargs: None,
            remove=lambda *args, **kwargs: None,
        )
        self.lock_screen = types.SimpleNamespace(relock=lambda: None)
        self.gtk = types.SimpleNamespace(set_cursor=lambda *args, **kwargs: None)

    def set_runtime_blanking_inhibited(self, inhibited):
        self.runtime_calls.append(inhibited)

    def reset_screenblanking_timeout(self):
        self.reset_calls += 1

    def inhibit_idle(self, owner="screen_blanking"):
        self.idle_calls.append(("inhibit", owner))

    def uninhibit_idle(self, owner="screen_blanking"):
        self.idle_calls.append(("release", owner))

    def remove_keyboard(self):
        return None

    def close_popup_message(self):
        return None

    def power_devices(self, *args, **kwargs):
        return None

    def wake_screen(self):
        return None

    def get_window(self):
        return None


if __name__ == "__main__":
    unittest.main()
