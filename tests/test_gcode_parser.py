import os
import tempfile
import unittest

from ks_includes.gcode_renderer.cache import GcodeRenderCache
from ks_includes.gcode_renderer.model import (
    FLAG_EXTRUSION,
    FLAG_RETRACTION,
    FLAG_TRAVEL,
    RenderMode,
)
from ks_includes.gcode_renderer.parser import parse_gcode

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "layered_sample.gcode")


class GcodeParserTests(unittest.TestCase):
    def test_absolute_positioning_and_extrusion(self):
        model = parse_gcode(
            b"G90\nM82\nG1 X0 Y0 Z0.2 F1200\nG1 X10 Y0 E1.0\nG1 X10 Y10 E2.0\n",
            "absolute.gcode",
        )
        self.assertEqual(model.segment_count, 2)
        self.assertEqual(model.total_layers, 1)
        self.assertEqual(model.segments[0][0:4], (0.0, 0.0, 10.0, 0.0))
        self.assertEqual((model.segments[0][8], model.segments[0][4]), (0.2, 0.2))
        self.assertTrue(model.segments[0][6] & FLAG_EXTRUSION)

    def test_relative_positioning_and_relative_extrusion(self):
        model = parse_gcode(
            b"G91\nM83\nG1 Z0.2\nG1 X5 Y0 E0.5\nG1 X0 Y5 E0.25\n",
            "relative.gcode",
        )
        self.assertEqual(model.segment_count, 2)
        self.assertEqual(model.segments[1][0:4], (5.0, 0.0, 5.0, 5.0))

    def test_g92_does_not_create_false_motion(self):
        model = parse_gcode(
            b"G90\nM82\nG1 X10 Y0 E1.0\nG92 E0\nG1 X20 Y0 E1.0\n",
            "g92.gcode",
        )
        self.assertEqual(model.segment_count, 2)
        self.assertEqual(model.total_layers, 1)

    def test_travel_and_retraction_detection(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X10 Y0 E1.0\nG1 E0.5\nG0 X20 Y0\n",
            "travel.gcode",
        )
        self.assertEqual(model.segment_count, 2)
        self.assertTrue(model.segments[0][6] & FLAG_RETRACTION)
        self.assertTrue(model.segments[1][6] & FLAG_TRAVEL)

    def test_layer_detection_uses_comments_and_z_lift(self):
        with open(FIXTURE_PATH, "rb") as handle:
            fixture = handle.read()
        model = parse_gcode(fixture, "fixture.gcode")
        self.assertEqual(model.total_layers, 2)
        self.assertEqual(model.layer_ranges[0], (0, 2))
        self.assertEqual(model.layer_ranges[1], (2, 4))

    def test_malformed_and_unsupported_lines_are_safe(self):
        model = parse_gcode(
            b"G90\nTHIS IS BAD\nG2 X1 Y1 I0 J1\nG1 X5 Y5 E1.0\n",
            "bad.gcode",
        )
        self.assertEqual(model.segment_count, 1)
        self.assertGreaterEqual(len(model.parser_warnings), 1)

    def test_byte_offset_tracking_and_progress_mapping(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X10 Y0 E1.0\nG1 X20 Y0 E2.0\n",
            "offsets.gcode",
        )
        first_offset = model.segments[0][7]
        second_offset = model.segments[1][7]
        self.assertLess(first_offset, second_offset)

        progress = model.progress_for_offset(first_offset - 1)
        self.assertEqual(progress.executed_segments, 0)
        self.assertEqual(progress.current_segment, 0)

        progress = model.progress_for_offset(first_offset)
        self.assertEqual(progress.executed_segments, 1)
        self.assertEqual(progress.current_segment, 1)

    def test_empty_gcode_file(self):
        model = parse_gcode(b"", "empty.gcode")
        self.assertEqual(model.segment_count, 0)
        self.assertEqual(model.total_layers, 0)

    def test_file_without_layer_comments(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X10 Y0 E1.0\nG0 Z0.4\nG1 X20 Y0 E2.0\n",
            "no-comments.gcode",
        )
        self.assertEqual(model.total_layers, 2)

    def test_cache_invalidation_uses_file_fingerprint(self):
        model = parse_gcode(b"G1 X1 Y1 E1.0\n", "cache.gcode", file_size=16, modified=10.0)
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = GcodeRenderCache(tmpdir)
            entry = cache.make_entry("cache.gcode", 16, 10.0)
            cache.save(entry, model)
            self.assertIsNotNone(cache.load(entry))
            stale = cache.make_entry("cache.gcode", 17, 10.0)
            self.assertIsNone(cache.load(stale))

    def test_visible_segment_ranges_follow_render_mode(self):
        with open(FIXTURE_PATH, "rb") as handle:
            model = parse_gcode(handle.read(), "fixture.gcode")
        self.assertEqual(model.visible_segment_range(RenderMode.CURRENT_LAYER, 1, 3), (2, 4))
        self.assertEqual(model.visible_segment_range(RenderMode.CURRENT_AND_PREVIOUS, 1, 1), (0, 4))
        self.assertEqual(model.visible_segment_range(RenderMode.FULL_MODEL, 1, 0), (0, 4))

    def test_visible_spatial_bounds_preserve_real_z_endpoints(self):
        model = parse_gcode(
            b"G90\nM82\nG1 Z0.2\nG1 X10 Y0 E1.0\nG0 Z0.6\nG0 X15 Y0\nG1 X15 Y10 Z0.8 E2.0\n",
            "spatial.gcode",
        )
        bounds, used_extrusion = model.visible_spatial_bounds(
            RenderMode.FULL_MODEL, 0, 0, show_travel=True
        )
        self.assertTrue(used_extrusion)
        self.assertEqual((bounds.min_x, bounds.min_y, bounds.min_z), (0.0, 0.0, 0.2))
        self.assertEqual((bounds.max_x, bounds.max_y, bounds.max_z), (15.0, 10.0, 0.8))


if __name__ == "__main__":
    unittest.main()
