import math
import sys
import types
import unittest

if "gi" not in sys.modules:
    gi_module = types.ModuleType("gi")
    gi_module.require_version = lambda *args, **kwargs: None
    repository_module = types.ModuleType("gi.repository")
    repository_module.Gtk = types.SimpleNamespace(DrawingArea=object, StyleContext=object)
    sys.modules["gi"] = gi_module
    sys.modules["gi.repository"] = repository_module

if "cairo" not in sys.modules:
    cairo_module = types.ModuleType("cairo")
    cairo_module.Context = object
    sys.modules["cairo"] = cairo_module

from ks_includes.gcode_renderer.model import RenderMode, SpatialBounds
from ks_includes.gcode_renderer.parser import parse_gcode
from ks_includes.gcode_renderer.preview import PreviewContext
from ks_includes.gcode_renderer.projection import (
    DEFAULT_PITCH,
    DEFAULT_YAW,
    MAX_PITCH,
    MIN_PITCH,
    CameraState3D,
    clamp_pitch,
    project_bounds,
    project_to_screen,
    rotate_yaw_pitch,
)
from ks_includes.gcode_renderer.renderer import ToolpathRenderer, build_interaction_segment_subset


class GcodeProjectionTests(unittest.TestCase):
    def test_default_orthographic_projection_centers_model(self):
        camera = CameraState3D(center_x=10.0, center_y=20.0, center_z=1.0, zoom=5.0)
        point = project_to_screen(10.0, 20.0, 1.0, camera, 400, 300)
        self.assertEqual((point.x, point.y), (200.0, 150.0))

    def test_yaw_rotation_changes_projected_x(self):
        camera = CameraState3D(
            center_x=0.0, center_y=0.0, center_z=0.0, zoom=10.0, yaw=0.0, pitch=MIN_PITCH
        )
        point_zero = project_to_screen(10.0, 0.0, 0.0, camera, 400, 300)
        camera.rotate_yaw(90.0)
        point_ninety = project_to_screen(10.0, 0.0, 0.0, camera, 400, 300)
        self.assertGreater(point_zero.x, 200.0)
        self.assertAlmostEqual(point_ninety.x, 200.0, places=4)

    def test_pitch_rotation_uses_real_z_height(self):
        camera = CameraState3D(
            center_x=0.0, center_y=0.0, center_z=0.0, zoom=10.0, yaw=0.0, pitch=35.0
        )
        flat = project_to_screen(0.0, 0.0, 0.0, camera, 400, 300)
        raised = project_to_screen(0.0, 0.0, 10.0, camera, 400, 300)
        self.assertLess(raised.y, flat.y)

    def test_combined_yaw_and_pitch_projection_is_finite(self):
        camera = CameraState3D(
            center_x=5.0, center_y=5.0, center_z=1.0, zoom=8.0, yaw=33.0, pitch=47.0
        )
        projected = project_to_screen(11.0, 17.0, 3.5, camera, 320, 240)
        self.assertTrue(math.isfinite(projected.x))
        self.assertTrue(math.isfinite(projected.y))
        self.assertTrue(math.isfinite(projected.depth))

    def test_model_center_remains_stable_under_rotation(self):
        camera = CameraState3D(center_x=12.0, center_y=12.0, center_z=2.0, zoom=6.0)
        first = project_to_screen(12.0, 12.0, 2.0, camera, 320, 240)
        camera.rotate_yaw(123.0)
        camera.rotate_pitch(17.0)
        second = project_to_screen(12.0, 12.0, 2.0, camera, 320, 240)
        self.assertEqual((first.x, first.y), (second.x, second.y))

    def test_screen_y_mapping_is_inverted(self):
        camera = CameraState3D(
            center_x=0.0, center_y=0.0, center_z=0.0, zoom=10.0, yaw=0.0, pitch=MIN_PITCH
        )
        projected = project_to_screen(0.0, 10.0, 0.0, camera, 400, 300)
        self.assertLess(projected.y, 150.0)

    def test_rotate_yaw_pitch_does_not_modify_source_coordinates(self):
        point = [4.0, 5.0, 6.0]
        rotate_yaw_pitch(point[0], point[1], point[2], 45.0, 30.0)
        self.assertEqual(point, [4.0, 5.0, 6.0])

    def test_invalid_coordinate_rejection(self):
        camera = CameraState3D()
        self.assertIsNone(project_to_screen(float("nan"), 0.0, 0.0, camera, 400, 300))
        self.assertIsNone(project_to_screen(0.0, float("inf"), 0.0, camera, 400, 300))

    def test_projected_bounding_box_fits_canvas_with_margin(self):
        bounds = self._make_bounds((0.0, 0.0, 0.0), (60.0, 40.0, 20.0))
        camera = CameraState3D()
        camera.fit_bounds(bounds, 400, 300)
        projected = project_bounds(bounds, camera)
        self.assertLessEqual(projected.width * camera.zoom, 400.0 * 0.84 + 1.0)
        self.assertLessEqual(projected.height * camera.zoom, 300.0 * 0.84 + 1.0)

    def test_fit_respects_yaw_and_pitch(self):
        bounds = self._make_bounds((0.0, 0.0, 0.0), (50.0, 50.0, 50.0))
        camera = CameraState3D(yaw=60.0, pitch=50.0)
        camera.fit_bounds(bounds, 500, 400)
        projected = project_bounds(bounds, camera)
        center_x = (
            250.0 + camera.pan_x + (((projected.min_x + projected.max_x) / 2.0) * camera.zoom)
        )
        center_y = (
            200.0 + camera.pan_y - (((projected.min_y + projected.max_y) / 2.0) * camera.zoom)
        )
        self.assertAlmostEqual(center_x, 250.0, places=3)
        self.assertAlmostEqual(center_y, 200.0, places=3)

    def test_tall_model_fits_correctly(self):
        bounds = self._make_bounds((0.0, 0.0, 0.0), (10.0, 10.0, 200.0))
        camera = CameraState3D()
        camera.fit_bounds(bounds, 300, 500)
        self.assertGreater(camera.zoom, 0.0)

    def test_flat_single_layer_model_fits_correctly(self):
        bounds = self._make_bounds((0.0, 0.0, 0.2), (100.0, 100.0, 0.2))
        camera = CameraState3D()
        camera.fit_bounds(bounds, 500, 500)
        self.assertGreater(camera.zoom, 0.0)

    def test_zero_width_bounds_do_not_crash(self):
        bounds = self._make_bounds((5.0, 5.0, 5.0), (5.0, 5.0, 5.0))
        camera = CameraState3D()
        camera.fit_bounds(bounds, 400, 300)
        projected = project_to_screen(5.0, 5.0, 5.0, camera, 400, 300)
        self.assertIsNotNone(projected)

    def test_travel_outliers_do_not_dominate_extrusion_fit(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X10 Y0 E1.0\nG1 X10 Y10 E2.0\nG0 Z10.0\nG0 X1000 Y1000\n",
            "outlier.gcode",
        )
        bounds, used_extrusion = model.visible_spatial_bounds(
            RenderMode.FULL_MODEL, 0, 0, show_travel=True
        )
        self.assertTrue(used_extrusion)
        self.assertEqual((bounds.max_x, bounds.max_y, bounds.max_z), (10.0, 10.0, 0.2))

    def test_pitch_clamps_correctly(self):
        self.assertEqual(clamp_pitch(-10.0), MIN_PITCH)
        self.assertEqual(clamp_pitch(95.0), MAX_PITCH)

    def test_yaw_normalizes_correctly(self):
        camera = CameraState3D(yaw=0.0)
        camera.rotate_yaw(405.0)
        self.assertEqual(camera.yaw, 45.0)

    def test_reset_restores_default_camera(self):
        bounds = self._make_bounds((0.0, 0.0, 0.0), (20.0, 20.0, 5.0))
        camera = CameraState3D(yaw=90.0, pitch=10.0, zoom=7.0, pan_x=12.0, pan_y=15.0)
        camera.reset(bounds, 400, 300)
        self.assertEqual(camera.yaw, DEFAULT_YAW)
        self.assertEqual(camera.pitch, DEFAULT_PITCH)
        self.assertTrue(camera.fitted)

    def test_zoom_clamps(self):
        camera = CameraState3D(zoom=1.0)
        camera.zoom_by(100000.0)
        self.assertLessEqual(camera.zoom, 1000.0)
        camera.zoom_by(0.0000001)
        self.assertGreaterEqual(camera.zoom, 0.05)

    def test_pan_remains_independent(self):
        camera = CameraState3D(pan_x=0.0, pan_y=0.0)
        camera.pan_by(12.0, -8.0)
        self.assertEqual((camera.pan_x, camera.pan_y), (12.0, -8.0))

    def test_projection_cache_reuses_scene_for_unchanged_camera_and_geometry(self):
        model = self._build_sample_model()
        renderer = ToolpathRenderer()
        prepared = renderer._prepare_geometry(model, RenderMode.FULL_MODEL, 0, 0, True)
        camera = CameraState3D()
        camera.fit_bounds(prepared.spatial_bounds, 400, 300)
        scene_a, _ = renderer._prepare_projected_scene(
            model, prepared, camera, 400, 300, True, None, False
        )
        scene_b, _ = renderer._prepare_projected_scene(
            model, prepared, camera, 400, 300, True, None, False
        )
        self.assertIs(scene_a, scene_b)

    def test_live_progress_does_not_invalidate_static_projection_cache(self):
        model = self._build_sample_model()
        renderer = ToolpathRenderer()
        prepared = renderer._prepare_geometry(model, RenderMode.FULL_MODEL, 0, 0, True)
        camera = CameraState3D()
        camera.fit_bounds(prepared.spatial_bounds, 400, 300)
        progress = model.progress_for_offset(0)
        scene_a, _ = renderer._prepare_projected_scene(
            model, prepared, camera, 400, 300, True, None, False
        )
        progress = model.progress_for_offset(model.segment_end_offsets[-1])
        scene_b, _ = renderer._prepare_projected_scene(
            model, prepared, camera, 400, 300, True, None, False
        )
        self.assertEqual(progress.executed_segments, model.segment_count)
        self.assertIs(scene_a, scene_b)

    def test_camera_change_invalidates_projection_cache(self):
        model = self._build_sample_model()
        renderer = ToolpathRenderer()
        prepared = renderer._prepare_geometry(model, RenderMode.FULL_MODEL, 0, 0, True)
        camera = CameraState3D()
        camera.fit_bounds(prepared.spatial_bounds, 400, 300)
        scene_a, _ = renderer._prepare_projected_scene(
            model, prepared, camera, 400, 300, True, None, False
        )
        camera.rotate_yaw(10.0)
        scene_b, _ = renderer._prepare_projected_scene(
            model, prepared, camera, 400, 300, True, None, False
        )
        self.assertIsNot(scene_a, scene_b)

    def test_pan_and_zoom_do_not_invalidate_projection_scene_cache(self):
        model = self._build_sample_model()
        renderer = ToolpathRenderer()
        prepared = renderer._prepare_geometry(model, RenderMode.FULL_MODEL, 0, 0, True)
        camera = CameraState3D()
        camera.fit_bounds(prepared.spatial_bounds, 400, 300)
        scene_a, _ = renderer._prepare_projected_scene(
            model, prepared, camera, 400, 300, True, None, False
        )
        camera.pan_by(15.0, -10.0)
        camera.zoom_by(1.2)
        scene_b, _ = renderer._prepare_projected_scene(
            model, prepared, camera, 400, 300, True, None, False
        )
        self.assertIs(scene_a, scene_b)

    def test_interaction_subset_is_deterministic_and_preserves_layer_boundaries(self):
        model = parse_gcode(
            (
                b"G90\nM82\n"
                b"G1 Z0.2\n"
                + b"".join(f"G1 X{i} Y0 E{i + 1}.0\n".encode("ascii") for i in range(60))
                + b"G1 Z0.4\n"
                + b"".join(f"G1 X{i} Y10 E{i + 61}.0\n".encode("ascii") for i in range(60))
            ),
            "subset.gcode",
        )
        indices = tuple(range(model.segment_count))
        first = build_interaction_segment_subset(model, indices, target_count=16)
        second = build_interaction_segment_subset(model, indices, target_count=16)
        self.assertEqual(first, second)
        self.assertEqual(first[0], indices[0])
        self.assertEqual(first[-1], indices[-1])
        self.assertIn(model.layer_ranges[0][0], first)
        self.assertIn(model.layer_ranges[0][1] - 1, first)
        self.assertIn(model.layer_ranges[1][0], first)
        self.assertIn(model.layer_ranges[1][1] - 1, first)

    def test_interaction_subset_preserves_sharp_turns_and_significant_z_changes(self):
        model = parse_gcode(
            (
                b"G90\nM82\nG1 Z0.2\n"
                + b"".join(f"G1 X{i} Y0 E{i + 1}.0\n".encode("ascii") for i in range(20))
                + b"G1 X20 Y10 E21.0\n"
                + b"G1 X20 Y20 Z0.8 E22.0\n"
                + b"".join(f"G1 X20 Y{21 + i} E{23 + i}.0\n".encode("ascii") for i in range(20))
            ),
            "turns.gcode",
        )
        indices = tuple(range(model.segment_count))
        subset = build_interaction_segment_subset(model, indices, target_count=10)
        turn_index = next(
            index
            for index, segment in enumerate(model.segments)
            if segment[2] == 20.0 and segment[3] == 10.0
        )
        z_change_index = next(
            index
            for index, segment in enumerate(model.segments)
            if abs(segment[4] - segment[8]) >= 0.5
        )
        self.assertIn(turn_index, subset)
        self.assertIn(z_change_index, subset)

    def test_interaction_subset_does_not_modify_original_model(self):
        model = self._build_sample_model()
        original_segments = list(model.segments)
        original_layers = list(model.layer_ranges)
        subset = build_interaction_segment_subset(
            model, tuple(range(model.segment_count)), target_count=1
        )
        self.assertGreaterEqual(len(subset), 1)
        self.assertEqual(model.segments, original_segments)
        self.assertEqual(model.layer_ranges, original_layers)

    def test_selected_file_projection_cache_is_replaced_when_model_changes(self):
        renderer = ToolpathRenderer()
        first_model = self._build_sample_model()
        second_model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X5 Y0 E1.0\nG1 X5 Y5 E2.0\n",
            "second.gcode",
        )
        camera = CameraState3D()

        first_prepared = renderer._prepare_geometry(first_model, RenderMode.FULL_MODEL, 0, 0, False)
        camera.fit_bounds(first_prepared.spatial_bounds, 400, 300)
        renderer._prepare_projected_scene(
            first_model,
            first_prepared,
            camera,
            400,
            300,
            False,
            None,
            False,
            preview_context=PreviewContext.SELECTED_FILE,
            projection_indices=first_prepared.extrusion_indices,
        )
        self.assertEqual(len(renderer._selected_projection_cache), 1)

        second_prepared = renderer._prepare_geometry(
            second_model, RenderMode.FULL_MODEL, 0, 0, False
        )
        camera.fit_bounds(second_prepared.spatial_bounds, 400, 300)
        renderer._prepare_projected_scene(
            second_model,
            second_prepared,
            camera,
            400,
            300,
            False,
            None,
            False,
            preview_context=PreviewContext.SELECTED_FILE,
            projection_indices=second_prepared.extrusion_indices,
        )
        self.assertEqual(len(renderer._selected_projection_cache), 1)

    def test_mode_change_invalidates_renderer_geometry_cache(self):
        model = self._build_sample_model()
        renderer = ToolpathRenderer()
        full_geometry = renderer._prepare_geometry(model, RenderMode.FULL_MODEL, 1, 1, True)
        layer_geometry = renderer._prepare_geometry(model, RenderMode.CURRENT_LAYER, 1, 1, True)
        self.assertNotEqual(full_geometry.visible_indices, layer_geometry.visible_indices)

    @staticmethod
    def _make_bounds(minimum, maximum):
        bounds = SpatialBounds()
        bounds.include(*minimum)
        bounds.include(*maximum)
        return bounds

    @staticmethod
    def _build_sample_model():
        return parse_gcode(
            (
                b"G90\nM82\n"
                b"G1 Z0.2\nG1 X10 Y0 E1.0\nG1 X10 Y10 E2.0\n"
                b"G0 Z0.4\nG1 X20 Y10 E3.0\nG1 X20 Y20 Z0.6 E4.0\n"
            ),
            "sample.gcode",
        )


if __name__ == "__main__":
    unittest.main()
