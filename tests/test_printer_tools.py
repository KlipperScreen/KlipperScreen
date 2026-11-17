import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with patch.dict(sys.modules, {"gi": MagicMock(), "gi.repository": MagicMock()}):
    from ks_includes.printer import Printer


def make_printer(sections):
    printer = Printer(state_cb=None, state_callbacks={})
    config = {section: {} for section in sections}
    printer.reinit({"software_version": "test"}, {"configfile": {"config": config}})
    return printer


class ToolOrderTest(unittest.TestCase):
    def test_extruders_are_ordered_by_number(self):
        extruders = ["extruder"] + [f"extruder{i}" for i in range(1, 12)]
        printer = make_printer(reversed(extruders))
        self.assertEqual(printer.get_tools(), extruders)
        self.assertEqual(printer.get_tool_number("extruder2"), 2)
        self.assertEqual(printer.get_tool_number("extruder10"), 10)

    def test_extruder_steppers_follow_extruders(self):
        printer = make_printer(
            ["extruder_stepper belt", "extruder10", "extruder", "extruder_stepper aux"]
            + [f"extruder{i}" for i in range(1, 10)]
        )
        tools = printer.get_tools()
        self.assertEqual(tools[:11], ["extruder"] + [f"extruder{i}" for i in range(1, 11)])
        self.assertEqual(tools[11:], ["extruder_stepper aux", "extruder_stepper belt"])


if __name__ == "__main__":
    unittest.main()
