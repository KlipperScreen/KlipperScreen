import logging
import re
import math

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return BedLevelPanel(*args)


# Find the screw closest to the point,
# but return None if the distance is above max_distance.
# If remove is set to true, the screw is also removed
# from the list of passed in screws.
def find_closest(screws, point, max_distance, remove=False):
    if len(screws) == 0:
        return None
    closest = screws[0]
    min_distance = math.hypot(closest[0] - point[0], closest[1] - point[1])
    for screw in screws[1:]:
        distance = math.hypot(screw[0] - point[0], screw[1] - point[1])
        if distance < min_distance:
            closest = screw
            min_distance = distance

    if min_distance > max_distance:
        return None

    if remove:
        screws.remove(closest)
    return closest


class BedLevelPanel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.response_count = 0
        self.screw_dict = {}
        self.screws = []
        self.y_cnt = 0
        self.x_cnt = 0
        self.x_offset = 0
        self.y_offset = 0
        self.buttons = {'dm': self._gtk.Button("motor-off", _("Disable XY"), "color3")}
        self.buttons['dm'].connect("clicked", self.disable_motors)
        screw_positions = []
        rotation = None

        grid = self._gtk.HomogeneousGrid()
        grid.attach(self.buttons['dm'], 0, 0, 1, 1)

        if "screws_tilt_adjust" in self._printer.get_config_section_list():
            self.buttons['screws'] = self._gtk.Button("refresh", _("Screws Adjust"), "color4")
            self.buttons['screws'].connect("clicked", self.screws_tilt_calculate)
            grid.attach(self.buttons['screws'], 0, 1, 1, 1)

            self.screws = self._get_screws("screws_tilt_adjust")
            logging.info(f"screws_tilt_adjust: {self.screws}")

            probe = self._printer.get_probe()
            if probe:
                if "x_offset" in probe:
                    self.x_offset = round(float(probe['x_offset']), 1)
                if "y_offset" in probe:
                    self.y_offset = round(float(probe['y_offset']), 1)
                logging.debug(f"offset X: {self.x_offset} Y: {self.y_offset}")
            # bed_screws uses NOZZLE positions
            # screws_tilt_adjust uses PROBE positions and
            # to be offseted for the buttons to work equal to bed_screws
            new_screws = [
                [round(screw[0] + self.x_offset, 1), round(screw[1] + self.y_offset, 1)]
                for screw in self.screws
            ]

            self.screws = new_screws
            logging.info(f"screws with offset: {self.screws}")
        elif "bed_screws" in self._printer.get_config_section_list():
            self.screws = self._get_screws("bed_screws")
            logging.info(f"bed_screws: {self.screws}")

        # get dimensions
        x_positions = {x[0] for x in self.screws}
        y_positions = {y[1] for y in self.screws}
        logging.info(f"X: {x_positions}\nY: {y_positions}")
        self.x_cnt = len(x_positions)
        self.y_cnt = len(y_positions)

        min_x = min(x_positions)
        max_x = max(x_positions)
        min_y = min(y_positions)
        max_y = max(y_positions)
        max_distance = math.ceil(
            math.hypot(max_x - min_x, max_y - min_y)
            / min(self.x_cnt, self.y_cnt, 3)
        )

        logging.debug(f"Using max_distance: {max_distance} to fit: {len(self.screws)} screws.")

        remaining_screws = self.screws[:]
        remaining_positions = []

        fl = find_closest(remaining_screws, (min_x, min_y), max_distance, remove=True)
        bl = find_closest(remaining_screws, (min_x, max_y), max_distance, remove=True)
        br = find_closest(remaining_screws, (max_x, max_y), max_distance, remove=True)
        fr = find_closest(remaining_screws, (max_x, min_y), max_distance, remove=True)

        if self.x_cnt == 3:
            mid_x = [x for x in list(zip(*self.screws))[0] if x not in (min_x, max_x)][0]
            fm = find_closest(remaining_screws, (mid_x, min_y), max_distance, remove=True)
            bm = find_closest(remaining_screws, (mid_x, max_y), max_distance, remove=True)
            fmp = bmp = None
        else:
            mid_x = round((min_x + max_x) / 2)
            fmp = (mid_x, min_y)
            bmp = (mid_x, max_y)
            remaining_positions.extend([fmp, bmp])
            fm = bm = None

        if self.y_cnt == 3:
            mid_y = [y for y in list(zip(*self.screws))[1] if y not in (min_y, max_y)][0]
            lm = find_closest(remaining_screws, (min_x, mid_y), max_distance, remove=True)
            rm = find_closest(remaining_screws, (max_x, mid_y), max_distance, remove=True)
            lmp = rmp = None
        else:
            mid_y = round((min_y + max_y) / 2)
            lmp = (min_x, mid_y)
            rmp = (max_x, mid_y)
            remaining_positions.extend([lmp, rmp])
            lm = rm = None

        remaining_count = len(remaining_screws)
        while remaining_count > 0:
            logging.debug(f"Screws remaining: {remaining_screws}")
            logging.debug(f"Positions remaining: {remaining_positions}")
            for screw in remaining_screws:
                pos = find_closest(remaining_positions, screw, max_distance)
                closest = find_closest(remaining_screws, pos, max_distance)
                if closest != screw:
                    continue
                elif pos == fmp:
                    fm = screw
                elif pos == bmp:
                    bm = screw
                elif pos == lmp:
                    lm = screw
                elif pos == rmp:
                    rm = screw

                logging.debug(f"Fitted screw {screw} close to {pos}")
                remaining_positions.remove(pos)
                remaining_screws.remove(screw)

            if remaining_count == len(remaining_screws):
                logging.warning(
                    f"Remaining screws: {remaining_screws}" +
                    f" don't fit to positions: {remaining_positions}")
                break
            remaining_count = len(remaining_screws)

        if remaining_count == 0:
            # All screws fitted.
            if self.x_cnt > 3:
                self.x_cnt = 3
            if self.y_cnt > 3:
                self.y_cnt = 3
        else:
            logging.debug(f"Screws not used: {remaining_screws}")

        used_screw_cnt = len(self.screws) - len(remaining_screws)
        logging.debug(f"Using {used_screw_cnt}-screw locations [x,y] [{self.x_cnt}x{self.y_cnt}]")

        button_scale = 2

        self.buttons['bl'] = self._gtk.Button("bed-level-t-l", scale=button_scale)
        self.buttons['br'] = self._gtk.Button("bed-level-t-r", scale=button_scale)
        self.buttons['fl'] = self._gtk.Button("bed-level-b-l", scale=button_scale)
        self.buttons['fr'] = self._gtk.Button("bed-level-b-r", scale=button_scale)
        self.buttons['lm'] = self._gtk.Button("bed-level-l-m", scale=button_scale)
        self.buttons['rm'] = self._gtk.Button("bed-level-r-m", scale=button_scale)
        self.buttons['fm'] = self._gtk.Button("bed-level-b-m", scale=button_scale)
        self.buttons['bm'] = self._gtk.Button("bed-level-t-m", scale=button_scale)

        valid_positions = True
        if self.ks_printer_cfg is not None:
            screw_positions = self.ks_printer_cfg.get("screw_positions", "")
            screw_positions = [str(i.strip()) for i in screw_positions.split(',')]
            logging.info(f"Positions: {screw_positions}")
            for screw in screw_positions:
                if screw not in ("bl", "fl", "fr", "br", "bm", "fm", "lm", "rm", ""):
                    logging.error(f"Unknown screw: {screw}")
                    self._screen.show_popup_message(_("Unknown screw position") + f": {screw}")
                    valid_positions = False
            if not (3 <= len(screw_positions) <= 8):
                valid_positions = False
            rotation = self.ks_printer_cfg.getint("screw_rotation", 0)
            logging.info(f"Rotation: {rotation}")
        else:
            valid_positions = False
        if 'bed_screws' in self._config.get_config():
            rotation = self._config.get_config()['bed_screws'].getint("rotation", 0)
            logging.debug(f"Rotation: {rotation}")

        bedgrid = Gtk.Grid()
        nscrews = len(self.screws)

        if valid_positions:
            if "bl" in screw_positions:
                bedgrid.attach(self.buttons['bl'], 1, 0, 1, 1)
            if "fl" in screw_positions:
                bedgrid.attach(self.buttons['fl'], 1, 2, 1, 1)
            if "fr" in screw_positions:
                bedgrid.attach(self.buttons['fr'], 3, 2, 1, 1)
            if "br" in screw_positions:
                bedgrid.attach(self.buttons['br'], 3, 0, 1, 1)
            if "bm" in screw_positions:
                bedgrid.attach(self.buttons['bm'], 2, 0, 1, 1)
            if "fm" in screw_positions:
                bedgrid.attach(self.buttons['fm'], 2, 2, 1, 1)
            if "lm" in screw_positions:
                bedgrid.attach(self.buttons['lm'], 1, 1, 1, 1)
            if "rm" in screw_positions:
                bedgrid.attach(self.buttons['rm'], 3, 1, 1, 1)
        elif nscrews in {4, 6, 8}:
            bedgrid.attach(self.buttons['bl'], 1, 0, 1, 1)
            bedgrid.attach(self.buttons['fl'], 1, 2, 1, 1)
            bedgrid.attach(self.buttons['fr'], 3, 2, 1, 1)
            bedgrid.attach(self.buttons['br'], 3, 0, 1, 1)
            if self.x_cnt == 3:
                bedgrid.attach(self.buttons['bm'], 2, 0, 1, 1)
                bedgrid.attach(self.buttons['fm'], 2, 2, 1, 1)
            if self.y_cnt == 3:
                bedgrid.attach(self.buttons['lm'], 1, 1, 1, 1)
                bedgrid.attach(self.buttons['rm'], 3, 1, 1, 1)
        else:
            label = Gtk.Label(
                _("Bed screw configuration:") + f" {nscrews}\n\n"
                + _("Not supported for auto-detection, it needs to be configured in klipperscreen.conf")
            )
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            label.set_line_wrap(True)
            grid.attach(label, 1, 0, 3, 2)
            self.content.add(grid)
            return

        if rotation == 90:
            # fl lm bl
            # fm    bm
            # fr rm br

            self.buttons['bl'].connect("clicked", self.go_to_position, fl)
            self.buttons['bm'].connect("clicked", self.go_to_position, lm)
            self.buttons['br'].connect("clicked", self.go_to_position, bl)
            self.buttons['rm'].connect("clicked", self.go_to_position, bm)
            self.buttons['fr'].connect("clicked", self.go_to_position, br)
            self.buttons['fm'].connect("clicked", self.go_to_position, rm)
            self.buttons['fl'].connect("clicked", self.go_to_position, fr)
            self.buttons['lm'].connect("clicked", self.go_to_position, fm)
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
            self.buttons['bl'].connect("clicked", self.go_to_position, fr)
            self.buttons['bm'].connect("clicked", self.go_to_position, fm)
            self.buttons['br'].connect("clicked", self.go_to_position, fl)
            self.buttons['rm'].connect("clicked", self.go_to_position, lm)
            self.buttons['fr'].connect("clicked", self.go_to_position, bl)
            self.buttons['fm'].connect("clicked", self.go_to_position, bm)
            self.buttons['fl'].connect("clicked", self.go_to_position, br)
            self.buttons['lm'].connect("clicked", self.go_to_position, rm)
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
            self.buttons['bl'].connect("clicked", self.go_to_position, br)
            self.buttons['bm'].connect("clicked", self.go_to_position, rm)
            self.buttons['br'].connect("clicked", self.go_to_position, fr)
            self.buttons['rm'].connect("clicked", self.go_to_position, fm)
            self.buttons['fr'].connect("clicked", self.go_to_position, fl)
            self.buttons['fm'].connect("clicked", self.go_to_position, lm)
            self.buttons['fl'].connect("clicked", self.go_to_position, bl)
            self.buttons['lm'].connect("clicked", self.go_to_position, bm)
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
            self.buttons['bl'].connect("clicked", self.go_to_position, bl)
            self.buttons['bm'].connect("clicked", self.go_to_position, bm)
            self.buttons['br'].connect("clicked", self.go_to_position, br)
            self.buttons['rm'].connect("clicked", self.go_to_position, rm)
            self.buttons['fr'].connect("clicked", self.go_to_position, fr)
            self.buttons['fm'].connect("clicked", self.go_to_position, fm)
            self.buttons['fl'].connect("clicked", self.go_to_position, fl)
            self.buttons['lm'].connect("clicked", self.go_to_position, lm)
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

        grid.attach(bedgrid, 1, 0, 3, 2)
        self.content.add(grid)

    def activate(self):
        for key, value in self.screw_dict.items():
            self.buttons[key].set_label(f"{value}")

    def home(self):
        # Test if all axes have been homed. Home if necessary.
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)
            # do Z_TILT_CALIBRATE if applicable.
            if self._printer.config_section_exists("z_tilt"):
                self._screen._ws.klippy.gcode_script(KlippyGcodes.Z_TILT)

    def go_to_position(self, widget, position):
        self.home()
        logging.debug(f"Going to position: {position}")
        script = [
            f"{KlippyGcodes.MOVE_ABSOLUTE}",
            "G1 Z7 F800\n",
            f"G1 X{position[0]} Y{position[1]} F3600\n",
            "G1 Z.1 F300\n"
        ]

        self._screen._ws.klippy.gcode_script(
            "\n".join(script)
        )

    def disable_motors(self, widget):
        self._screen._ws.klippy.gcode_script(
            "M18"  # Disable motors
        )

    def process_busy(self, busy):
        for button in self.buttons:
            if button == "screws":
                self.buttons[button].set_sensitive(
                    self._printer.config_section_exists("screws_tilt_adjust")
                    and (not busy))
                continue
            self.buttons[button].set_sensitive((not busy))

    def process_update(self, action, data):
        if action == "notify_busy":
            self.process_busy(data)
            return
        if action != "notify_gcode_response":
            return
        if data.startswith('!!'):
            self.response_count = 0
            self.buttons['screws'].set_sensitive(True)
            return
        result = re.match(
            "^// (.*) : [xX= ]+([\\-0-9\\.]+), [yY= ]+([\\-0-9\\.]+), [zZ= ]+[\\-0-9\\.]+ :" +
            " (Adjust ->|adjust) ([CW]+ [0-9:]+)",
            data
        )
        # screws_tilt_adjust uses PROBE positions and was offseted for the buttons to work equal to bed_screws
        # for the result we need to undo the offset
        if result:
            x = round(float(result[2]) + self.x_offset, 1)
            y = round(float(result[3]) + self.y_offset, 1)
            for key, value in self.screw_dict.items():
                if value and x == value[0] and y == value[1]:
                    logging.debug(f"X: {x} Y: {y} Adjust: {result[5]} Pos: {key}")
                    self.buttons[key].set_label(result[5])
                    break
            self.response_count += 1
            if self.response_count >= len(self.screws) - 1:
                self.buttons['screws'].set_sensitive(True)
        else:
            result = re.match(
                "^// (.*) : [xX= ]+([\\-0-9\\.]+), [yY= ]+([\\-0-9\\.]+), [zZ= ]+[\\-0-9\\.]",
                data
            )
            # screws_tilt_adjust uses PROBE positions and was offseted for the buttons to work equal to bed_screws
            # for the result we need to undo the offset
            if result and re.search('base', result[1]):
                x = round(float(result[2]) + self.x_offset, 1)
                y = round(float(result[3]) + self.y_offset, 1)
                logging.debug(f"X: {x} Y: {y} is the reference")
                for key, value in self.screw_dict.items():
                    if value and x == value[0] and y == value[1]:
                        logging.debug(f"X: {x} Y: {y} Pos: {key}")
                        self.buttons[key].set_label(_("Reference"))

    def _get_screws(self, config_section_name):
        screws = []
        config_section = self._printer.get_config_section(config_section_name)
        for item in config_section:
            logging.debug(f"{config_section_name}: {config_section[item]}")
            result = re.match(r"([\-0-9\.]+)\s*,\s*([\-0-9\.]+)", config_section[item])
            if result:
                screws.append([
                    round(float(result[1]), 1),
                    round(float(result[2]), 1)
                ])
        return sorted(screws, key=lambda s: (float(s[1]), float(s[0])))

    def screws_tilt_calculate(self, widget):
        self.home()
        self.response_count = 0
        self.buttons['screws'].set_sensitive(False)
        self._screen._ws.klippy.gcode_script("SCREWS_TILT_CALCULATE")
