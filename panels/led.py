import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

RGB = ["r", "g", "b"]
RGBW = ["r", "g", "b", "w"]
RGB_PRESETS = {"r": [1.0, 0.0, 0.0],
               "g": [0.0, 1.0, 0.0],
               "b": [0.0, 0.0, 1.0],
               "rgb": [1.0, 1.0, 1.0],
               "off": [0.0, 0.0, 0.0]}
RGBW_PRESETS = {"r": [1.0, 0.0, 0.0, 0.0],
                "g": [0.0, 1.0, 0.0, 0.0],
                "b": [0.0, 0.0, 1.0, 0.0],
                "w": [0.0, 0.0, 0.0, 1.0],
                "rgb": [1.0, 1.0, 1.0, 0.0],
                "rgbw": [1.0, 1.0, 1.0, 1.0],
                "off": [0.0, 0.0, 0.0, 0.0]}


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.led = ''
        self.col_mix = []
        self.presets = {}
        self.scales = {}
        self.buttons = []
        self.leds = self._printer.get_leds()
        # is it ness to rise an err len == 0 ? rise a distinguishable error for user and ret to
        if len(self.leds) == 1:
            self.content.add(self.color_selector((self.leds[:1])))
        elif len(self.leds) in {2, 3, 4}:
            self.content.add(self.load_leds())
        else:
            self._screen.show_error_modal("Unsupported", f"Current configuration not supported,\n {self.leds}")

    def back(self):
        if self.led != '':
            self.close_color_selector()
            return True
        return False

    def load_leds(self):
        grid = self._gtk.HomogeneousGrid()
        column = row = idx = 0
        for led in self.leds:
            name = led.split()[1] if len(led.split()) > 1 else led
            button = self._gtk.Button(None, name.upper(), "color1")
            button.connect("clicked", self.choose_color, led)
            if idx % 4 == 0:
                column += 1
                row = 0
            grid.attach(button, column, row, 1, 1)
            row += 1
            idx += 1
        return grid

    def choose_color(self, _btn, led):
        children = self.content.get_children()
        self.content.remove(children[0])
        self.content.add(self.color_selector(led))
        self.content.show_all()

    def close_color_selector(self):
        child = self.content.get_children()
        self.content.remove(child[0])
        self.led = ''
        self.content.add(self.load_leds())
        self.content.show_all()

    def process_update(self, action, data):
        if action != 'notify_status_update':
            return
        for led in self.leds:
            if led in data and "color_data" in data[led]:
                self.update_scales(None, self._printer.get_led_color(led))

    def color_selector(self, led):
        grid = self._gtk.HomogeneousGrid()
        logging.info(f"Adding led: {led}")
        self.led = led
        color_data = self._printer.get_led_color(led)
        presets_data = self._printer.get_led_presets(led)
        self.col_mix = RGB if self._printer.get_led_color_mix(
            led) == 3 else RGBW # choose other way to unify for other types of leds
        if len(presets_data) < 1:
            self.presets = RGB_PRESETS if self.col_mix == RGB else RGBW_PRESETS
        else:
            self.presets = self.parse_presets(presets_data)
        for idx, col_value in enumerate(color_data):
            name = Gtk.Label()
            name.set_markup(
                f"\n<big><b>{(self.col_mix[idx]).upper()}</b></big>\n")
            scale = Gtk.Scale.new_with_range(
                orientation=Gtk.Orientation.VERTICAL, min=0, max=255, step=1)
            scale.set_inverted(True)
            scale.set_value(round(col_value * 255))
            scale.set_digits(0)
            scale.set_vexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            scale.connect("button-release-event", self.apply_scales)
            self.scales[self.col_mix[idx]] = scale
            scale_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=1)
            scale_box.add(scale)
            scale_box.add(name)
            grid.attach(scale_box, idx, 0, 1, 1)

        button_grid = self._gtk.HomogeneousGrid()
        column = row = 0
        for idx, key in enumerate(self.presets):
            button = self._gtk.Button(None, key.upper(), "color1")
            button.connect("clicked", self.apply_preset, self.presets[key])
            if idx % 4 == 0:
                column += 1
                row = 0
            button_grid.attach(button, column, row, 1, 1)
            row += 1
        grid.attach(button_grid, len(self.scales), 0, 2, 1)
        return grid

    def update_scales(self, event, color_data):
        for idx, col_name in enumerate(self.col_mix):
            scale = self.scales[col_name]
            scale.disconnect_by_func(self.apply_scales)
            scale.set_value(round(color_data[idx] * 255))
            scale.connect("button-release-event", self.apply_scales)

    def set_led_color(self, color_data):
        name = self.led.split()[1] if len(self.led.split()) > 1 else self.led
        self._screen._send_action(None, "printer.gcode.script",
                                  {"script": KlippyGcodes.set_led_color(name, color_data)})

    def apply_scales(self, widget, event):
        self.set_led_color(self.get_color_data())

    def apply_preset(self, widget, color_data):
        self.set_led_color(color_data)
        GLib.timeout_add_seconds(1, self.check_led_color)

    def get_color_data(self):
        color_data = []
        for col_name in self.col_mix:
            color_data.append(
                round(self.scales[col_name].get_value() / 255, 4))
        return color_data

    def check_led_color(self):
        self.update_scales(None, self._printer.get_led_color(self.led))
        return False

    @staticmethod
    def parse_presets(presets_data) -> {}:
        parsed = {}
        for preset in presets_data.values():
            name = preset["name"].lower()
            parsed[name] = []
            for color in ["red", "green", "blue", "white"]:
                if color in preset:
                    parsed[name].append(round(preset[color] / 255, 4))
        return parsed
