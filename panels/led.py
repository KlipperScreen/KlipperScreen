import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

colors = "RGBW"
DEFAULT_PRESETS = {
    "on": [1.0, 1.0, 1.0, 1.0],
    "off": [0.0, 0.0, 0.0, 0.0]
}


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        data_misc = screen.apiclient.send_request("server/database/item?namespace=mainsail&key=miscellaneous.entries")
        if data_misc:
            self._printer.add_led_presets(data_misc['result']['value'][next(iter(data_misc["result"]["value"]))])
        self.color_data = [0, 0, 0, 0]
        self.color_order = 'RGBW'
        self.presets = {}
        self.scales = {}
        self.buttons = []
        self.leds = self._printer.get_leds()
        self.led = self.leds[0] if len(self.leds) == 1 else None
        self.open_selector(None, self.led)

    def color_available(self, idx):
        return (
            (idx == 0 and 'R' in self.color_order)
            or (idx == 1 and 'G' in self.color_order)
            or (idx == 2 and 'B' in self.color_order)
            or (idx == 3 and 'W' in self.color_order)
        )

    def activate(self):
        if self.led is not None:
            self.set_title(f"{self.led}")

    def set_title(self, title):
        self._screen.base_panel.set_title(self.prettify(title))

    def back(self):
        if len(self.leds) > 1:
            self.set_title(self._screen.panels[self._screen._cur_panels[-1]].title)
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
        self.led = None
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
        self.set_title(f"{self.led}")
        grid = self._gtk.HomogeneousGrid()
        self.color_data = self._printer.get_led_color(led)
        self.color_order = self._printer.get_led_color_order(led)
        if self.color_data is None or self.color_order is None:
            self.back()
            return
        presets_data = self._printer.get_led_presets(led)
        self.presets = DEFAULT_PRESETS if len(presets_data) < 1 else self.parse_presets(presets_data)
        scale_grid = self._gtk.HomogeneousGrid()
        for idx, col_value in enumerate(self.color_data):
            if not self.color_available(idx):
                continue
            button = self._gtk.Button("light", label=f'{colors[idx].upper()}', style=f"color{idx + 1}")
            color = [0, 0, 0, 0]
            color[idx] = 1
            button.connect("clicked", self.apply_preset, color)
            button.set_hexpand(False)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=255, step=1)
            scale.set_value(round(col_value * 255))
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            scale.connect("button-release-event", self.apply_scales)
            self.scales[idx] = scale
            scale_grid.attach(button, 0, idx, 1, 1)
            scale_grid.attach(scale, 1, idx, 3, 1)
        grid.attach(scale_grid, 0, 0, 2, 1)

        preset_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        for i, key in enumerate(self.presets):
            button = self._gtk.Button(None, key.upper(), style=f"color{(i % 4) + 1}")
            button.connect("clicked", self.apply_preset, self.presets[key])
            preset_list.add(button)
        scroll = self._gtk.ScrolledWindow()
        scroll.add(preset_list)
        grid.attach(scroll, 2, 0, 1, 1)
        return grid

    def process_update(self, action, data):
        if action != 'notify_status_update':
            return
        for led in self.leds:
            if led in data and "color_data" in data[led]:
                self.color_data = data[led]["color_data"][0]
                self.update_scales(data[led]["color_data"][0])

    def update_scales(self, color_data):
        for idx, col_value in enumerate(self.color_data):
            if not self.color_available(idx):
                continue
            self.scales[idx].set_value(round(color_data[idx] * 255))

    def set_led_color(self, color_data):
        name = self.led.split()[1] if len(self.led.split()) > 1 else self.led
        self._screen._send_action(None, "printer.gcode.script",
                                  {"script": KlippyGcodes.set_led_color(name, color_data)})

    def apply_scales(self, widget, event):
        for idx, col_value in enumerate(self.color_data):
            if not self.color_available(idx):
                continue
            self.color_data[idx] = round(self.scales[idx].get_value() / 255, 4)
        self.set_led_color(self.color_data)

    def apply_preset(self, widget, color_data):
        self.set_led_color(color_data)

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
