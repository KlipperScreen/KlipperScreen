import logging
import math
import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


# Find the screw closest to the point,
# but return None if the distance is above max_distance.
# If remove is set to true, the screw is also removed
# from the list of passed in screws.
def find_closest(screws, point, max_distance):
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
    screws.remove(closest)
    return closest


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Bed Level")
        super().__init__(screen, title)
        self.screw_positions = {}
        self.screws = []
        self.x_offset = 0
        self.y_offset = 0
        self.buttons = {'dm': self._gtk.Button("motor-off", _("Disable Motors"), "color3")}
        self.buttons['dm'].connect("clicked", self.disable_motors)
        rotation = 0
        self.probe_z_height = 0
        self.lift_speed = 5
        self.horizontal_move_z = 5
        self.horizontal_speed = 50
        invert_x = invert_y = False

        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
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
                    self.x_offset = float(probe['x_offset'])
                if "y_offset" in probe:
                    self.y_offset = float(probe['y_offset'])
                logging.debug(f"offset X: {self.x_offset} Y: {self.y_offset}")
            # bed_screws uses NOZZLE positions
            # screws_tilt_adjust uses PROBE positions and
            # to be offseted for the buttons to work equal to bed_screws
            new_screws = [
                [screw[0] + self.x_offset, screw[1] + self.y_offset]
                for screw in self.screws
            ]

            self.screws = new_screws
            logging.info(f"screws with offset: {self.screws}")
        elif "bed_screws" in self._printer.get_config_section_list():
            self.screws = self._get_screws("bed_screws")
            logging.info(f"bed_screws: {self.screws}")

        # KS config
        if self.ks_printer_cfg is not None:
            rotation = self.ks_printer_cfg.getint("screw_rotation", 0)
            if rotation not in (0, 90, 180, 270):
                self._screen.show_popup_message(_("Rotation invalid") + f" {rotation} \n")
                logging.info(f"Rotation invalid: {rotation}")
                rotation = 0
            logging.info(f"Rotation: {rotation}")
            invert_x = self._config.get_config()['main'].getboolean("invert_x", False)
            invert_y = self._config.get_config()['main'].getboolean("invert_y", False)
            logging.info(f"Inversion X: {invert_x} Y: {invert_y}")

        # get dimensions
        x_positions = {x[0] for x in self.screws}
        y_positions = {y[1] for y in self.screws}
        logging.info(f"X: {x_positions}\nY: {y_positions}")

        min_x = min(x_positions)
        max_x = max(x_positions)
        mid_x = round((min_x + max_x) / 2)

        min_y = min(y_positions)
        max_y = max(y_positions)
        mid_y = round((min_y + max_y) / 2)

        max_distance = math.floor(min(max_x - min_x, max_y - min_y) / 3)

        logging.debug(f"Using max_distance: {max_distance} to fit: {len(self.screws)} screws.")

        remaining_screws = self.screws[:]

        # The order here it's important because the rotation function will
        # shift the values according to the angle of rotation
        self.screw_positions = {
            'bl': find_closest(remaining_screws, (min_x, max_y), max_distance),
            'fm': find_closest(remaining_screws, (mid_x, min_y), max_distance),
            'br': find_closest(remaining_screws, (max_x, max_y), max_distance),
            'lm': find_closest(remaining_screws, (min_x, mid_y), max_distance),
            'fr': find_closest(remaining_screws, (max_x, min_y), max_distance),
            'bm': find_closest(remaining_screws, (mid_x, max_y), max_distance),
            'fl': find_closest(remaining_screws, (min_x, min_y), max_distance),
            'rm': find_closest(remaining_screws, (max_x, mid_y), max_distance),
        }

        if invert_x and invert_y:
            rotation = (rotation + 180) % 360
            invert_x = invert_y = False
        if rotation != 0:
            self.screw_positions = self.map_rotation(self.screw_positions, rotation)
            logging.info(f"Rotated: {rotation}")
        if invert_x or invert_y:
            self.screw_positions = self.map_invert(self.screw_positions, invert_x, invert_y)

        self.screw_positions['center'] = find_closest(remaining_screws, (mid_x, mid_y), max_distance)

        if len(remaining_screws) != 0:
            found = []
            for pos in self.screw_positions:
                if self.screw_positions[pos]:
                    found.append(pos)
            logging.debug(f"Found: {found}")
            logging.debug(f"Screws not used: {remaining_screws}")
            if len(self.screws) > 9:
                error_msg = _("This panel supports up-to 9 screws in a 3x3 Grid")
            else:
                error_msg = _("It's possible that the configuration is not correct")
            self._screen.show_popup_message(_("Screws not used:") + f" {remaining_screws} \n" +
                                            error_msg, 2)

        logging.debug(f"Using {len(self.screws) - len(remaining_screws)}/{len(self.screws)}-screw locations")

        button_scale = 2

        self.buttons['bl'] = self._gtk.Button("bed-level-t-l", scale=button_scale)
        self.buttons['br'] = self._gtk.Button("bed-level-t-r", scale=button_scale)
        self.buttons['fl'] = self._gtk.Button("bed-level-b-l", scale=button_scale)
        self.buttons['fr'] = self._gtk.Button("bed-level-b-r", scale=button_scale)
        self.buttons['lm'] = self._gtk.Button("bed-level-l-m", scale=button_scale)
        self.buttons['rm'] = self._gtk.Button("bed-level-r-m", scale=button_scale)
        self.buttons['fm'] = self._gtk.Button("bed-level-b-m", scale=button_scale)
        self.buttons['bm'] = self._gtk.Button("bed-level-t-m", scale=button_scale)
        self.buttons['center'] = self._gtk.Button("bed-level-center", scale=button_scale)

        screw_layout_map = {
            'fr': [3, 2, 1, 1],
            'fm': [2, 2, 1, 1],
            'fl': [1, 2, 1, 1],
            'rm': [3, 1, 1, 1],
            'br': [3, 0, 1, 1],
            'bm': [2, 0, 1, 1],
            'bl': [1, 0, 1, 1],
            'lm': [1, 1, 1, 1],
            'center': [2, 1, 1, 1],
        }

        bedgrid = Gtk.Grid()
        for pos in screw_layout_map:
            bedgrid.attach(self.buttons[pos], *screw_layout_map[pos])
            self.buttons[pos].set_no_show_all(True)
            if pos in self.screw_positions and self.screw_positions[pos]:
                self.buttons[pos].show()

        for layout_pos in self.screw_positions:
            self.buttons[layout_pos].connect("clicked", self.go_to_position, self.screw_positions[layout_pos])

        remove_list = []
        for screw in self.screw_positions:
            if self.screw_positions[screw] is None:
                remove_list.append(screw)
        for screw in remove_list:
            self.screw_positions.pop(screw)

        logging.info(f"screw_positions: {self.screw_positions}")

        grid.attach(bedgrid, 1, 0, 3, 2)
        self.content.add(grid)

    @staticmethod
    def map_invert(positions, invert_x, invert_y):
        if invert_x:
            return {
                'fr': positions['fl'],
                'fm': positions['fm'],
                'fl': positions['fr'],
                'rm': positions['lm'],
                'bl': positions['br'],
                'bm': positions['bm'],
                'br': positions['bl'],
                'lm': positions['rm']
            }
        if invert_y:
            return {
                'fr': positions['br'],
                'fm': positions['bm'],
                'fl': positions['bl'],
                'rm': positions['rm'],
                'bl': positions['fl'],
                'bm': positions['fm'],
                'br': positions['fr'],
                'lm': positions['lm']
            }
        return positions

    @staticmethod
    def map_rotation(positions, angle):
        angle %= 360
        shift = (angle // 90) * 2
        rotated_positions = {}
        keys = list(positions.keys())
        for i, key in enumerate(keys):
            new_key = keys[(i + shift) % len(keys)]
            rotated_positions[new_key] = positions[key]
        return rotated_positions

    def home(self):
        # Test if all axes have been homed. Home if necessary.
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script("G28")
            # do Z_TILT_CALIBRATE if applicable.
            if self._printer.config_section_exists("z_tilt"):
                self._screen._ws.klippy.gcode_script("Z_TILT_ADJUST")

    def go_to_position(self, widget, position):
        self.home()
        logging.debug(f"Going to position: {position}")
        script = [
            f"{KlippyGcodes.MOVE_ABSOLUTE}",
            f"G1 Z{self.horizontal_move_z} F{self.lift_speed * 60}\n",
            f"G1 X{position[0]} Y{position[1]} F{self.horizontal_speed * 60}\n",
            f"G1 Z{self.probe_z_height} F{self.lift_speed * 60}\n"
        ]
        self._screen._send_action(widget, "printer.gcode.script", {"script": "\n".join(script)})

    def disable_motors(self, widget):
        self._screen._send_action(widget, "printer.gcode.script", {"script": "M18"})

    def process_busy(self, busy):
        for button in self.buttons:
            if button == "screws":
                continue
            self.buttons[button].set_sensitive((not busy))

    def process_update(self, action, data):
        if 'idle_timeout' in data:
            self.process_busy(data['idle_timeout']['state'].lower() == "printing")
        if action != "notify_status_update":
            return
        if "screws_tilt_adjust" in data:
            if "error" in data["screws_tilt_adjust"]:
                self.buttons['screws'].set_sensitive(True)
                logging.info("Error reported by screws_tilt_adjust")
            if "results" in data["screws_tilt_adjust"]:
                section = self._printer.get_config_section('screws_tilt_adjust')
                for screw, result in data["screws_tilt_adjust"]["results"].items():
                    logging.info(f"{screw} {result['sign']} {result['adjust']}")
                    if screw not in section:
                        logging.error(f"{screw} not found in {section}")
                        continue
                    x, y = section[screw].split(',')
                    x = float(x) + self.x_offset
                    y = float(y) + self.y_offset
                    for key, value in self.screw_positions.items():
                        if value and x == value[0] and y == value[1]:
                            logging.debug(f"X: {x} Y: {y} Adjust: {result['adjust']} Pos: {key}")
                            if result['is_base']:
                                logging.info(f"{screw} is the Reference")
                                self.buttons[key].set_label(_("Reference"))
                            else:
                                self.buttons[key].set_label(f"{result['sign']} {result['adjust']}")
                            if int(result['adjust'].split(':')[0]) == 0 and int(result['adjust'].split(':')[1]) < 6:
                                self.buttons[key].set_image(self._gtk.Image('complete'))
                            else:
                                self.buttons[key].set_image(self._gtk.Image(result['sign'].lower()))

    def _get_screws(self, config_section_name):
        screws = []
        config_section = self._printer.get_config_section(config_section_name)
        logging.debug(config_section_name)
        for item in config_section:
            logging.debug(f"{item}: {config_section[item]}")
            if item == 'probe_speed':
                self.lift_speed = float(config_section[item])
            elif item == 'speed':
                self.horizontal_speed = float(config_section[item])
            elif item == 'horizontal_move_z':
                self.horizontal_move_z = float(config_section[item])
            elif item == 'probe_height':
                self.probe_z_height = float(config_section[item])
            else:
                result = re.match(r"([\-0-9\.]+)\s*,\s*([\-0-9\.]+)", config_section[item])
                if result:
                    screws.append([
                        float(result[1]),
                        float(result[2])
                    ])
        return sorted(screws, key=lambda s: (float(s[1]), float(s[0])))

    def screws_tilt_calculate(self, widget):
        self.home()
        self._screen._send_action(widget, "printer.gcode.script", {"script": "SCREWS_TILT_CALCULATE"})
