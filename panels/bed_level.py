import gi
import logging
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.BedLevelPanel")

def create_panel(*args):
    return BedLevelPanel(*args)

class BedLevelPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.panel_name = panel_name
        self.screws = None
        grid = KlippyGtk.HomogeneousGrid()
        self.disabled_motors = False

        screws = []
        if "bed_screws" in self._screen.printer.get_config_section_list():
            bed_screws = self._screen.printer.get_config_section("bed_screws")
            for item in bed_screws:
                if re.match(r"^[0-9\.]+,[0-9\.]+$", bed_screws[item]):
                    screws.append(bed_screws[item].split(","))

            screws = sorted(screws, key=lambda x: (float(x[1]), float(x[0])))
            logger.debug("Bed screw locations [x,y]: %s", screws)
            if "bltouch" in self._screen.printer.get_config_section_list():
                x_offset = 0
                y_offset = 0
                bltouch = self._screen.printer.get_config_section("bltouch")
                if "x_offset" in bltouch:
                    x_offset = float(bltouch['x_offset'])
                if "y_offset" in bltouch:
                    y_offset = float(bltouch['y_offset'])
                new_screws = []
                for screw in screws:
                    new_screws.append([float(screw[0]) + x_offset, float(screw[1]) + y_offset])
                screws = new_screws

            self.screws = screws

        if len(screws) < 4:
            logger.debug("bed_screws not configured, calculating locations")
            xconf = self._screen.printer.get_config_section("stepper_x")
            yconf = self._screen.printer.get_config_section("stepper_y")
            x = int(int(xconf['position_max'])/4)
            y = int(int(yconf['position_max'])/4)
            self.screws = [
                [x, y],
                [x*3, y],
                [x, y*3],
                [x*3, y*3],
            ]
            logger.debug("Calculated screw locations [x,y]: %s", screws)
        else:
            logger.debug("Configured screw locations [x,y]: %s", screws)


        self.labels['bl'] = KlippyGtk.ButtonImage("bed-level-t-l", None, None, )
        self.labels['bl'].connect("clicked", self.go_to_position, self.screws[2])
        self.labels['br'] = KlippyGtk.ButtonImage("bed-level-t-r")
        self.labels['br'].connect("clicked", self.go_to_position, self.screws[3])
        self.labels['fl'] = KlippyGtk.ButtonImage("bed-level-b-l")
        self.labels['fl'].connect("clicked", self.go_to_position, self.screws[0])
        self.labels['fr'] = KlippyGtk.ButtonImage("bed-level-b-r")
        self.labels['fr'].connect("clicked", self.go_to_position, self.screws[1])

        grid.attach(self.labels['bl'], 1, 0, 1, 1)
        grid.attach(self.labels['br'], 2, 0, 1, 1)
        grid.attach(self.labels['fl'], 1, 1, 1, 1)
        grid.attach(self.labels['fr'], 2, 1, 1, 1)

        self.labels['home'] = KlippyGtk.ButtonImage("home",_("Home All"),"color2")
        self.labels['home'].connect("clicked", self.home)

        self.labels['dm'] = KlippyGtk.ButtonImage("motor-off", _("Disable XY"), "color3")
        self.labels['dm'].connect("clicked", self.disable_motors)

        grid.attach(self.labels['home'], 0, 0, 1, 1)
        grid.attach(self.labels['dm'], 0, 1, 1, 1)

        if self._printer.config_section_exists("screws_tilt_adjust"):
            self.labels['screws'] = KlippyGtk.ButtonImage("refresh",_("Screws Adjust"),"color4")
            self.labels['screws'].connect("clicked", self.screws_tilt_calculate)
            grid.attach(self.labels['screws'], 3, 0, 1, 1)

        self.content.add(grid)

    def go_to_position(self, widget, position):
        logger.debug("Going to position: %s", position)
        script = [
            "%s" % KlippyGcodes.MOVE_ABSOLUTE,
            "G1 Z7 F800\n",
            "G1 X%s Y%s F3600\n" % (position[0], position[1]),
            "G1 Z.1 F300\n"
        ]

        if self.disabled_motors:
            self.disabled_motors = False
            script.insert(0, "G28")

        self._screen._ws.klippy.gcode_script(
            "\n".join(script)
        )

    def disable_motors(self, widget):
        self._screen._ws.klippy.gcode_script(
            "M18" # Disable motors
        )

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            result = re.match(
                "^// (back|front) (left|right) screw : X [0-9\.]+, Y [0-9\.]+, Z [0-9\.]+ : Adjust -> ([CW]+ [0-9:]+)",
                data
            )
            if result:
                self.labels["%s%s" % (result.group(1)[0:1], result.group(2)[0:1])].set_label(result.group(3))
                self.response_count += 1
                if self.response_count > 3:
                    self._screen.remove_subscription(self.panel_name)


    def screws_tilt_calculate(self, widget):
        self.response_count = 0
        self._screen.add_subscription(self.panel_name)
        self._screen._ws.klippy.gcode_script("SCREWS_TILT_CALCULATE")
