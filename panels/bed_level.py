import gi
import logging
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

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

        supported = [4, 6, 8]
        nscrews = len(screws)
        if nscrews not in supported:
            logging.debug("%d bed_screws not supported: calculating 4 locations", nscrews)
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
        else:
            self.screws = screws

        if (("bltouch" in self._screen.printer.get_config_section_list() or
            "probe" in self._screen.printer.get_config_section_list()) and
                config_section_name == "screws_tilt_adjust"):
            if "bltouch" in self._screen.printer.get_config_section_list():
                bltouch = self._screen.printer.get_config_section("bltouch")
                if "x_offset" in bltouch:
                    self.x_offset = float(bltouch['x_offset'])
                if "y_offset" in bltouch:
                    self.y_offset = float(bltouch['y_offset'])
                logging.debug("Bltouch found substracted offset X: %.0f Y: %.0f", self.x_offset, self.y_offset)
                self._screen.show_popup_message(_("Bltouch found applied offset"), level=1)
            elif "probe" in self._screen.printer.get_config_section_list():
                probe = self._screen.printer.get_config_section("probe")
                if "x_offset" in probe:
                    self.x_offset = float(probe['x_offset'])
                if "y_offset" in probe:
                    self.y_offset = float(probe['y_offset'])
                logging.debug("Probe found substracting offset X: %.0f Y: %.0f", self.x_offset, self.y_offset)
                self._screen.show_popup_message(_("Probe found applied offset"), level=1)
            new_screws = []
            for screw in self.screws:
                new_screws.append([
                    self.apply_offset(screw[0], self.x_offset),
                    self.apply_offset(screw[1], self.y_offset)
                ])
            self.screws = new_screws

        # get dimensions
        self.x_cnt = len(list(dict.fromkeys([int(x[0]) for x in self.screws])))
        self.y_cnt = len(list(dict.fromkeys([int(x[1]) for x in self.screws])))

        min_x = min(dict(self.screws).keys())
        max_x = max(dict(self.screws).keys())
        min_y = min(dict(self.screws[::-1]).values())
        max_y = max(dict(self.screws).values())

        fl = [min_x, min_y]
        bl = [min_x, max_y]
        br = [max_x, max_y]
        fr = [max_x, min_y]

        if self.x_cnt == 3:
            mid_x = [x for x in list(zip(*self.screws))[0] if x not in (min_x, max_x)][0]
            fm = [mid_x, min_y]
            bm = [mid_x, max_y]
        else:
            fm = bm = None
        if self.y_cnt == 3:
            mid_y = [y for y in list(zip(*self.screws))[1] if y not in (min_y, max_y)][0]
            lm = [min_x, mid_y]
            rm = [max_x, mid_y]
        else:
            lm = rm = None

        logging.debug("Using %d-screw locations [x,y] [%dx%d]", len(self.screws), self.x_cnt, self.y_cnt)

        self.labels['bl'] = self._gtk.ButtonImage("bed-level-t-l", None, None, 2.5)
        self.labels['br'] = self._gtk.ButtonImage("bed-level-t-r", None, None, 2.5)
        self.labels['fl'] = self._gtk.ButtonImage("bed-level-b-l", None, None, 2.5)
        self.labels['fr'] = self._gtk.ButtonImage("bed-level-b-r", None, None, 2.5)
        self.labels['lm'] = self._gtk.ButtonImage("bed-level-l-m", None, None, 2.5)
        self.labels['rm'] = self._gtk.ButtonImage("bed-level-r-m", None, None, 2.5)
        self.labels['fm'] = self._gtk.ButtonImage("bed-level-b-m", None, None, 2.5)
        self.labels['bm'] = self._gtk.ButtonImage("bed-level-t-m", None, None, 2.5)

        bedgrid = Gtk.Grid()
        bedgrid.attach(self.labels['bl'], 1, 0, 1, 1)
        bedgrid.attach(self.labels['fl'], 1, 2, 1, 1)
        bedgrid.attach(self.labels['fr'], 3, 2, 1, 1)
        bedgrid.attach(self.labels['br'], 3, 0, 1, 1)

        rotation = 0
        if 'bed_screws' in self._config.get_config():
            rotation = self._config.get_config()['bed_screws'].getint("rotation", 0)
            logging.debug("Rotation: %d", rotation)
        if rotation == 90:
            # fl lm bl
            # fm    bm
            # fr rm br
            if self.y_cnt == 3:
                bedgrid.attach(self.labels['bm'], 2, 0, 1, 1)
                bedgrid.attach(self.labels['fm'], 2, 2, 1, 1)
            if self.x_cnt == 3:
                bedgrid.attach(self.labels['lm'], 1, 1, 1, 1)
                bedgrid.attach(self.labels['rm'], 3, 1, 1, 1)
            self.labels['bl'].connect("clicked", self.go_to_position, fl)
            self.labels['bm'].connect("clicked", self.go_to_position, lm)
            self.labels['br'].connect("clicked", self.go_to_position, bl)
            self.labels['rm'].connect("clicked", self.go_to_position, bm)
            self.labels['fr'].connect("clicked", self.go_to_position, br)
            self.labels['fm'].connect("clicked", self.go_to_position, rm)
            self.labels['fl'].connect("clicked", self.go_to_position, fr)
            self.labels['lm'].connect("clicked", self.go_to_position, fm)
            self.screw_dict = {
                'bl': fl,
                'bm': lm,
                'br': bl,
                'rm': bm,
                'fr': br,
                'fm': rm,
                'fl': fr,
                'lm': fm
            }
        elif rotation == 180:
            # fr fm fl
            # rm    lm
            # br bm bl
            if self.x_cnt == 3:
                bedgrid.attach(self.labels['bm'], 2, 0, 1, 1)
                bedgrid.attach(self.labels['fm'], 2, 2, 1, 1)
            if self.y_cnt == 3:
                bedgrid.attach(self.labels['lm'], 1, 1, 1, 1)
                bedgrid.attach(self.labels['rm'], 3, 1, 1, 1)
            self.labels['bl'].connect("clicked", self.go_to_position, fr)
            self.labels['bm'].connect("clicked", self.go_to_position, fm)
            self.labels['br'].connect("clicked", self.go_to_position, fl)
            self.labels['rm'].connect("clicked", self.go_to_position, lm)
            self.labels['fr'].connect("clicked", self.go_to_position, bl)
            self.labels['fm'].connect("clicked", self.go_to_position, bm)
            self.labels['fl'].connect("clicked", self.go_to_position, br)
            self.labels['lm'].connect("clicked", self.go_to_position, rm)
            self.screw_dict = {
                'bl': fr,
                'bm': fm,
                'br': fl,
                'rm': lm,
                'fr': bl,
                'fm': bm,
                'fl': br,
                'lm': rm
            }
        elif rotation == 270:
            # br rm fr
            # bm    fm
            # bl lm fl
            if self.y_cnt == 3:
                bedgrid.attach(self.labels['bm'], 2, 0, 1, 1)
                bedgrid.attach(self.labels['fm'], 2, 2, 1, 1)
            if self.x_cnt == 3:
                bedgrid.attach(self.labels['lm'], 1, 1, 1, 1)
                bedgrid.attach(self.labels['rm'], 3, 1, 1, 1)
            self.labels['bl'].connect("clicked", self.go_to_position, br)
            self.labels['bm'].connect("clicked", self.go_to_position, rm)
            self.labels['br'].connect("clicked", self.go_to_position, fr)
            self.labels['rm'].connect("clicked", self.go_to_position, fm)
            self.labels['fr'].connect("clicked", self.go_to_position, fl)
            self.labels['fm'].connect("clicked", self.go_to_position, lm)
            self.labels['fl'].connect("clicked", self.go_to_position, bl)
            self.labels['lm'].connect("clicked", self.go_to_position, bm)
            self.screw_dict = {
                'bl': br,
                'bm': rm,
                'br': fr,
                'rm': fm,
                'fr': fl,
                'fm': lm,
                'fl': bl,
                'lm': bm
            }
        else:
            # bl bm br
            # lm    rm
            # fl fm fr
            self.labels['bl'].connect("clicked", self.go_to_position, bl)
            self.labels['bm'].connect("clicked", self.go_to_position, bm)
            self.labels['br'].connect("clicked", self.go_to_position, br)
            self.labels['rm'].connect("clicked", self.go_to_position, rm)
            self.labels['fr'].connect("clicked", self.go_to_position, fr)
            self.labels['fm'].connect("clicked", self.go_to_position, fm)
            self.labels['fl'].connect("clicked", self.go_to_position, fl)
            self.labels['lm'].connect("clicked", self.go_to_position, lm)
            self.screw_dict = {
                'bl': bl,
                'bm': bm,
                'br': br,
                'rm': rm,
                'fr': fr,
                'fm': fm,
                'fl': fl,
                'lm': lm
            }
            if self.x_cnt == 3:
                bedgrid.attach(self.labels['bm'], 2, 0, 1, 1)
                bedgrid.attach(self.labels['fm'], 2, 2, 1, 1)
            if self.y_cnt == 3:
                bedgrid.attach(self.labels['lm'], 1, 1, 1, 1)
                bedgrid.attach(self.labels['rm'], 3, 1, 1, 1)

        grid.attach(bedgrid, 1, 0, 3, 2)

        self.labels['dm'] = self._gtk.ButtonImage("motor-off", _("Disable XY"), "color3")
        self.labels['dm'].connect("clicked", self.disable_motors)

        grid.attach(self.labels['dm'], 0, 0, 1, 1)

        if self._printer.config_section_exists("screws_tilt_adjust"):
            self.labels['screws'] = self._gtk.ButtonImage("refresh", _("Screws Adjust"), "color4")
            self.labels['screws'].connect("clicked", self.screws_tilt_calculate)
            grid.attach(self.labels['screws'], 0, 1, 1, 1)

        self.content.add(grid)

    def activate(self):
        for key, value in self.screw_dict.items():
            self.labels[key].set_label(str(value))
        if self._printer.config_section_exists("screws_tilt_adjust"):
            self.labels['screws'].set_sensitive(True)

    def go_to_position(self, widget, position):
        if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
        logging.debug("Going to position: %s", position)
        script = [
            "%s" % KlippyGcodes.MOVE_ABSOLUTE,
            "G1 Z7 F800\n",
            "G1 X%s Y%s F3600\n" % (position[0], position[1]),
            "G1 Z.1 F300\n"
        ]

        self._screen._ws.klippy.gcode_script(
            "\n".join(script)
        )

    def disable_motors(self, widget):
        self._screen._ws.klippy.gcode_script(
            "M18"  # Disable motors
        )

    def process_update(self, action, data):
        _ = self.lang.gettext
        if action == "notify_gcode_response":
            if data.startswith('!!'):
                self.response_count = 0
                self.labels['screws'].set_sensitive(True)
                return
            result = re.match(
                "^// (.*) : [xX= ]+([\\-0-9\\.]+), [yY= ]+([\\-0-9\\.]+), [zZ= ]+[\\-0-9\\.]+ :" +
                " (Adjust ->|adjust) ([CW]+ [0-9:]+)",
                data
            )
            if result:
                x = self.apply_offset(result.group(2), self.x_offset)
                y = self.apply_offset(result.group(3), self.y_offset)
                for key, value in self.screw_dict.items():
                    if value and x == value[0] and y == value[1]:
                        logging.debug("X: %s Y: %s Adjust: %s Pos: %s" % (x, y, result.group(5), key))
                        self.labels[key].set_label(result.group(5))
                        break
                self.response_count += 1
                if self.response_count >= len(self.screws)-1:
                    self.labels['screws'].set_sensitive(True)
            else:
                result = re.match(
                    "^// (.*) : [xX= ]+([\\-0-9\\.]+), [yY= ]+([\\-0-9\\.]+), [zZ= ]+[\\-0-9\\.]",
                    data
                )
                if result and re.search('base', result.group(1)):
                    x = self.apply_offset(result.group(2), self.x_offset)
                    y = self.apply_offset(result.group(3), self.y_offset)
                    logging.debug("X: %s Y: %s is the reference" % (x, y))
                    for key, value in self.screw_dict.items():
                        if value and x == value[0] and y == value[1]:
                            logging.debug("X: %s Y: %s Pos: %s" % (x, y, key))
                            self.labels[key].set_label(_("Reference"))

    def apply_offset(self, pos, offset):
        return max(0, int(float(pos) - offset))

    def screws_tilt_calculate(self, widget):
        if self._screen.printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
        self.response_count = 0
        self.labels['screws'].set_sensitive(False)
        self._screen._ws.klippy.gcode_script("SCREWS_TILT_CALCULATE")
