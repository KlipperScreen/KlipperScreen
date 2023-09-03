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
        self.col_mix = RGBW
        self.presets = {}
        self.scales = {}
        self.buttons = []
        self.leds = self._printer.get_leds()
        self.led = self.leds[0] if len(self.leds) == 1 else None
        self.open_selector(None, self.led)

    def back(self):
        if len(self.leds) > 1:
            self.open_selector(led=None)
            return True
        return False

    def open_selector(self, widget=None, led=None):
        for child in self.content.get_children():
            self.content.remove(child)
        if led is None:
            self.content.add(self.led_selector())
        else:
            self.content.add(self.color_selector(led))
        self.content.show_all()

    def led_selector(self):
        columns = 3 if self._screen.vertical_mode else 4
        grid = self._gtk.HomogeneousGrid()
        for i, led in enumerate(self.leds):
            name = led.split()[1] if len(led.split()) > 1 else led
            button = self._gtk.Button(None, name.upper(), style=f"color{(i % 4) + 1}")
            button.connect("clicked", self.open_selector, led)
            grid.attach(button, (i % columns), int(i / columns), 1, 1)
        scroll = self._gtk.ScrolledWindow()
        scroll.add(grid)
        return scroll

    def color_selector(self, led):
        logging.info(led)
        self.led = led
        grid = self._gtk.HomogeneousGrid()
        color_data = self._printer.get_led_color(led)
        color_mix = self._printer.get_led_color_mix(led)
        if color_data is None or color_mix is None:
            self.back()
            return
        if len(color_mix) == 3:
            self.col_mix = RGB
            if len(color_data) > 3:
                # is it always rgbw?
                color_data.pop(-1)

        presets_data = self._printer.get_led_presets(led)
        if len(presets_data) < 1:
            self.presets = RGB_PRESETS if self.col_mix == RGB else RGBW_PRESETS
        else:
            self.presets = self.parse_presets(presets_data)

        for idx, col_value in enumerate(color_data):
            name = Gtk.Label()
            name.set_markup(
                f"\n<big><b>{(self.col_mix[idx]).upper()}</b></big>\n")
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.VERTICAL, min=0, max=255, step=1)
            scale.set_inverted(True)
            scale.set_value(round(col_value * 255))
            scale.set_digits(0)
            scale.set_vexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            scale.connect("button-release-event", self.apply_scales)
            self.scales[self.col_mix[idx]] = scale
            scale_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            scale_box.add(scale)
            scale_box.add(name)
            grid.attach(scale_box, idx, 0, 1, 1)

        button_grid = self._gtk.HomogeneousGrid()
        for i, key in enumerate(self.presets):
            button = self._gtk.Button(None, key.upper(), style=f"color{(i % 4) + 1}")
            button.connect("clicked", self.apply_preset, self.presets[key])
            button_grid.attach(button, (i % 2), int(i / 2), 1, 1)
        grid.attach(button_grid, len(self.scales), 0, 2, 1)
        scroll = self._gtk.ScrolledWindow()
        scroll.add(grid)
        return scroll

    def process_update(self, action, data):
        if action != 'notify_status_update':
            return
        for led in self.leds:
            if led in data and "color_data" in data[led]:
                self.update_scales(None, self._printer.get_led_color(led))

    def update_scales(self, event, color_data):
        for idx, col_name in enumerate(self.scales):
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
        return [
            round(self.scales[col_name].get_value() / 255, 4)
            for col_name in self.col_mix
        ]

    def check_led_color(self):
        self.update_scales(None, self._printer.get_led_color(self.led))
        return False

    @staticmethod
    def parse_presets(presets_data) -> {}:
        parsed = {}
        for preset in presets_data.values():
            name = preset["name"].lower()
            parsed[name] = [
                round(preset[color] / 255, 4)
                for color in ["red", "green", "blue", "white"]
                if color in preset
            ]
        return parsed
