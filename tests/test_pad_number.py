import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ks_includes.functions import pad_number

FIGURE_SPACE = " "


class PadNumberTest(unittest.TestCase):
    def test_length_is_constant_across_digit_counts(self):
        for value in (0, 5, 42, 100, 255):
            self.assertEqual(len(pad_number(value, 3)), 3)
        for value in (0.0, 9.8, 25.3, 210.4):
            self.assertEqual(len(pad_number(value, 5, 1)), 5)

    def test_pads_with_figure_space(self):
        self.assertEqual(pad_number(5, 3), f"{FIGURE_SPACE * 2}5")
        self.assertEqual(pad_number(9.84, 5, 1), f"{FIGURE_SPACE * 2}9.8")
        self.assertNotIn(" ", pad_number(7, 4))

    def test_wider_values_are_not_truncated(self):
        self.assertEqual(pad_number(1000, 3), "1000")
        self.assertEqual(pad_number(-5, 3), f"{FIGURE_SPACE}-5")


if __name__ == "__main__":
    unittest.main()
