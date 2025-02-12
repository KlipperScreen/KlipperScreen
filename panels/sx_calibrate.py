import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Calibrate")
        super().__init__(screen, title)

        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)

        calibration_buttons = {
            "BED_CALIBRATION": self._gtk.Button("bed-level", _("Bed Calibration"), "color2", 1, Gtk.PositionType.LEFT, 1),
            "PROBE_CALIBRATION": self._gtk.Button("extruder", _("Probe Calibration"), "color2", 1, Gtk.PositionType.LEFT, 1),
        }

        calibration_buttons["BED_CALIBRATION"].connect("clicked", self.menu_item_clicked, {
            "name": _("Bed Calibration"),
            "panel": "sx_calibrate_bed"
        })

        calibration_buttons["PROBE_CALIBRATION"].connect("clicked", self.menu_item_clicked, {
            "name": _("Probe Calibration"),
            "panel": "sx_calibrate_probe"
        })

        if "EXTRUDER_SCREW_PLACEMENT" in self._printer.available_commands:
            button = self._gtk.Button("z-farther", _("IDEX Calibration for Z Axis"), "color3", 1, Gtk.PositionType.LEFT, 1)
            calibration_buttons["MECHANICAL_CALIBRATION"] = button
            calibration_buttons["MECHANICAL_CALIBRATION"].connect("clicked", self.menu_item_clicked, {
                "name": _("Mechanical Calibration"),
                "panel": "sx_calibrate_mechanical"
            })

        if "PRINT_CALIBRATION" in self._printer.available_commands:
            button = self._gtk.Button("resume", _("Print IDEX Calibration File for XY Axes"), "color4", 1, Gtk.PositionType.LEFT, 1)
            calibration_buttons["PRINT_CALIBRATION"] = button
            calibration_buttons["PRINT_CALIBRATION"].connect("clicked", self.print_calibration)

        for current_row, button in enumerate(calibration_buttons):
            if button == "MECHANICAL_CALIBRATION":
                grid.attach(calibration_buttons[button], 0, current_row, 5, 1)
                height_check_button = self._gtk.Button("extruder", _("Check"), "color2")
                height_check_button.connect("clicked", self.check_height)
                grid.attach(height_check_button, 5, current_row, 1, 1)
                continue

            if button == "PRINT_CALIBRATION":
                grid.attach(calibration_buttons[button], 0, current_row, 5, 1)
                idex_calibration_button = self._gtk.Button("extruder", _("Adjust"), "color2")
                idex_calibration_button.connect("clicked", self.menu_item_clicked, {
                    "name": _("IDEX Calibration"),
                    "panel": "sx_calibrate_idex"
                })
                grid.attach(idex_calibration_button, 5, current_row, 1, 1)
                continue
            
            grid.attach(calibration_buttons[button], 0, current_row, 6, 1)

        self.content.add(grid)


    def print_calibration(self, button):
        self._screen._ws.klippy.gcode_script("print_calibration")


    def check_height(self, button):
        self._screen._ws.klippy.gcode_script("IDEX_NOZZLE_CHECK")
        message: str = _("Nozzle height will be checked.") + "\n\n" \
        + _("If not properly leveled, perform a mechanical calibration.")
        self._screen.show_popup_message(message, level=4)