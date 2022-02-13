import gi
import logging
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return BedLevelPanel(*args)

class BedLevelPanel(ScreenPanel):
    x_offset = 0
    y_offset = 0

    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.panel_name = panel_name
        self.screws = None
        grid = self._gtk.HomogeneousGrid()
        self.disabled_motors = False

        screws = []
        config_section_name = None
        if "screws_tilt_adjust" in self._screen.printer.get_config_section_list():
            config_section_name = "screws_tilt_adjust"
        elif "bed_screws" in self._screen.printer.get_config_section_list():
            config_section_name = "bed_screws"

        if config_section_name is not None:
            config_section = self._screen.printer.get_config_section(config_section_name)
            for item in config_section:
                logging.debug("Screws section: %s" % config_section[item])
                result = re.match(r"([\-0-9\.]+)\s*,\s*([\-0-9\.]+)", config_section[item])
                if result:
                    screws.append([
                        round(float(result.group(1)), 2),
                        round(float(result.group(2)), 2)
                    ])

            screws = sorted(screws, key=lambda x: (float(x[1]), float(x[0])))
            logging.debug("Bed screw locations [x,y]: %s", screws)
            if ("bltouch" in self._screen.printer.get_config_section_list() and
                    config_section_name == "screws_tilt_adjust"):
                x_offset = 0
                y_offset = 0
                bltouch = self._screen.printer.get_config_section("bltouch")
                if "x_offset" in bltouch:
                    self.x_offset = float(bltouch['x_offset'])
                if "y_offset" in bltouch:
                    self.y_offset = float(bltouch['y_offset'])
                new_screws = []
                for screw in screws:
                    new_screws.append([
                        round(float(screw[0]) + self.x_offset, 2),
                        round(float(screw[1]) + self.y_offset, 2)
                    ])
                screws = new_screws

            self.screws = screws
            logging.debug("Screws: %s" % screws)

        if len(screws) < 4:
            logging.debug("bed_screws not configured, calculating locations")
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
            logging.debug("Calculated screw locations [x,y]: %s", self.screws)
        else:
            logging.debug("Configured %d-screw locations [x,y]: %s", len(self.screws), self.screws)

        # min_x, min_y
        fl = sorted(self.screws)[0]
        # max_x, max_y
        br = sorted(self.screws)[-1]
        # min_x, max_y
        bl = [min(dict(self.screws).keys()), max(dict(self.screws).values())]
        # max_x, min_y
        fr = [max(dict(self.screws).keys()), min(dict(self.screws[::-1]).values())]

        self.labels['bl'] = self._gtk.ButtonImage("bed-level-t-l", None, None, 3, 3)
        self.labels['bl'].connect("clicked", self.go_to_position, bl)
        self.labels['br'] = self._gtk.ButtonImage("bed-level-t-r", None, None, 3, 3)
        self.labels['br'].connect("clicked", self.go_to_position, br)
        self.labels['fl'] = self._gtk.ButtonImage("bed-level-b-l", None, None, 3, 3)
        self.labels['fl'].connect("clicked", self.go_to_position, fl)
        self.labels['fr'] = self._gtk.ButtonImage("bed-level-b-r", None, None, 3, 3)
        self.labels['fr'].connect("clicked", self.go_to_position, fr)

        if self._screen.lang_ltr:
            grid.attach(self.labels['bl'], 1, 0, 1, 1)
            grid.attach(self.labels['br'], 2, 0, 1, 1)
            grid.attach(self.labels['fl'], 1, 1, 1, 1)
            grid.attach(self.labels['fr'], 2, 1, 1, 1)
        else:
            grid.attach(self.labels['bl'], 2, 0, 1, 1)
            grid.attach(self.labels['br'], 1, 0, 1, 1)
            grid.attach(self.labels['fl'], 2, 1, 1, 1)
            grid.attach(self.labels['fr'], 1, 1, 1, 1)

        self.labels['home'] = self._gtk.ButtonImage("home", _("Home All"), "color2")
        self.labels['home'].connect("clicked", self.home)

        self.labels['dm'] = self._gtk.ButtonImage("motor-off", _("Disable XY"), "color3")
        self.labels['dm'].connect("clicked", self.disable_motors)

        grid.attach(self.labels['home'], 0, 0, 1, 1)
        grid.attach(self.labels['dm'], 0, 1, 1, 1)

        if self._printer.config_section_exists("screws_tilt_adjust"):
            self.labels['screws'] = self._gtk.ButtonImage("refresh", _("Screws Adjust"), "color4")
            self.labels['screws'].connect("clicked", self.screws_tilt_calculate)
            grid.attach(self.labels['screws'], 3, 0, 1, 1)

        self.content.add(grid)

    def activate(self):
        self.labels['bl'].set_label("")
        self.labels['br'].set_label("")
        self.labels['fl'].set_label("")
        self.labels['fr'].set_label("")
        if self._printer.config_section_exists("screws_tilt_adjust"):
            self.labels['screws'].set_sensitive(True)

    def go_to_position(self, widget, position):
        logging.debug("Going to position: %s", position)
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
            "M18"  # Disable motors
        )

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            result = re.match(
                "^// (.*) : [xX= ]+([\\-0-9\\.]+), [yY= ]+([\\-0-9\\.]+), [zZ= ]+[\\-0-9\\.]+ :" +
                " (Adjust ->|adjust) ([CW]+ [0-9:]+)",
                data
            )
            if result:
                screw_labels = ['fl', 'fr', 'bl', 'br']
                x = int(float(result.group(2)) + self.x_offset)
                y = int(float(result.group(3)) + self.y_offset)
                logging.debug(data)
                logging.debug("X: %s Y: %s" % (x, y))
                for i in range(len(self.screws)):
                    logging.debug(self.screws[i])
                    if x == int(float(self.screws[i][0])) and y == int(float(self.screws[i][1])):
                        break
                self.labels[screw_labels[i]].set_label(result.group(5))
                self.response_count += 1
                if self.response_count >= len(self.screws)-1:
                    self.labels['screws'].set_sensitive(True)


    def screws_tilt_calculate(self, widget):
        self.response_count = 0
        self.labels['screws'].set_sensitive(False)
        self._screen._ws.klippy.gcode_script("SCREWS_TILT_CALCULATE")
