import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from math import pi
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Leds")
        super().__init__(screen, title)
        self.da_size = self._gtk.img_scale * 2
        self.preview = Gtk.DrawingArea(width_request=self.da_size, height_request=self.da_size)
        self.preview.set_size_request(-1, self.da_size * 2)
        self.preview.connect("draw", self.on_draw)
        self.preview_label = Gtk.Label()
        self.preset_list = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        self.color_data = [0, 0, 0, 0]
        self.color_order = 'RGBW'
        self.presets = {"off": [0.0, 0.0, 0.0, 0.0]}
        self.scales = {}
        self.buttons = []
        self.leds = self._printer.get_leds()
        self.current_led = self.leds[0] if len(self.leds) == 1 else None
        self.open_selector(None, self.current_led)

    def color_available(self, idx):
        return (
            (idx == 0 and 'R' in self.color_order)
            or (idx == 1 and 'G' in self.color_order)
            or (idx == 2 and 'B' in self.color_order)
            or (idx == 3 and 'W' in self.color_order)
        )

    def activate(self):
        if self.current_led is not None:
            self.set_title(f"{self.current_led}")

    def set_title(self, title):
        self._screen.base_panel.set_title(self.prettify(title))

    def back(self):
        if len(self.leds) > 1 and self.current_led:
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
        self.current_led = None
        columns = 3 if self._screen.vertical_mode else 4
        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
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
        self.current_led = led
        self.set_title(f"{self.current_led}")
        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        self.color_order = self._printer.get_led_color_order(led)
        if self.color_order is None:
            logging.error("Error: Color order is None")
            self.back()
            return
        on = [1 if self.color_available(i) else 0 for i in range(4)]
        self.presets["on"] = on
        scale_grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        for idx, col_value in enumerate(self.color_data):
            if not self.color_available(idx):
                continue
            color = [0, 0, 0, 0]
            color[idx] = 1
            button = self._gtk.Button()
            preview = Gtk.DrawingArea(width_request=self.da_size, height_request=self.da_size)
            preview.connect("draw", self.on_draw, color)
            button.set_image(preview)
            button.connect("clicked", self.apply_preset, color)
            button.set_hexpand(False)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min=0, max=255, step=1)
            scale.set_value(round(col_value * 255))
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            scale.connect("button-release-event", self.apply_scales)
            scale.connect("value_changed", self.update_preview)
            self.scales[idx] = scale
            scale_grid.attach(button, 0, idx, 1, 1)
            scale_grid.attach(scale, 1, idx, 3, 1)
        grid.attach(scale_grid, 0, 0, 3, 1)

        columns = 3 if self._screen.vertical_mode else 2
        data_misc = self._screen.apiclient.send_request(
            "server/database/item?namespace=mainsail&key=miscellaneous.entries")
        if data_misc:
            presets_data = data_misc['value'][next(iter(data_misc["value"]))]['presets']
            if presets_data:
                self.presets.update(self.parse_presets(presets_data))
        for i, key in enumerate(self.presets):
            logging.info(f'Adding preset: {key}')
            preview = Gtk.DrawingArea(width_request=self.da_size, height_request=self.da_size)
            preview.connect("draw", self.on_draw, self.presets[key])
            button = self._gtk.Button()
            button.set_image(preview)
            button.connect("clicked", self.apply_preset, self.presets[key])
            self.preset_list.attach(button, i % columns, int(i / columns) + 1, 1, 1)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.preset_list)
        preview_box = Gtk.Box(homogeneous=True)
        preview_box.add(self.preview_label)
        preview_box.add(self.preview)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(preview_box)
        box.add(scroll)
        if self._screen.vertical_mode:
            grid.attach(box, 0, 1, 3, 1)
        else:
            grid.attach(box, 3, 0, 2, 1)
        return grid

    def on_draw(self, da, ctx, color=None):
        if color is None:
            color = self.color_data
        ctx.set_source_rgb(*self.rgbw_to_rgb(color))
        # Set the size of the rectangle
        width = height = da.get_allocated_width() * .9
        x = da.get_allocated_width() * .05
        # Set the radius of the corners
        radius = width / 2 * 0.2
        ctx.arc(x + radius, radius, radius, pi, 3 * pi / 2)
        ctx.arc(x + width - radius, radius, radius, 3 * pi / 2, 0)
        ctx.arc(x + width - radius, height - radius, radius, 0, pi / 2)
        ctx.arc(x + radius, height - radius, radius, pi / 2, pi)
        ctx.close_path()
        ctx.fill()

    def update_preview(self, args):
        self.update_color_data()
        self.preview.queue_draw()
        self.preview_label.set_label(self.rgb_to_hex(self.rgbw_to_rgb(self.color_data)))

    def process_update(self, action, data):
        if action != 'notify_status_update':
            return
        if self.current_led in data and "color_data" in data[self.current_led]:
            self.update_scales(data[self.current_led]["color_data"][0])
            self.preview.queue_draw()

    def update_scales(self, color_data):
        for idx in self.scales:
            self.scales[idx].set_value(int(color_data[idx] * 255))
        self.color_data = color_data

    def update_color_data(self):
        for idx in self.scales:
            self.color_data[idx] = self.scales[idx].get_value() / 255

    def apply_preset(self, widget, color_data):
        self.update_scales(color_data)
        self.apply_scales()

    def apply_scales(self, *args):
        self.update_color_data()
        self.set_led_color(self.color_data)

    def set_led_color(self, color_data):
        name = self.current_led.split()[1] if len(self.current_led.split()) > 1 else self.current_led
        self._screen._send_action(None, "printer.gcode.script",
                                  {"script": KlippyGcodes.set_led_color(name, color_data)})

    @staticmethod
    def parse_presets(presets_data) -> {}:
        parsed = {}
        for i, preset in enumerate(presets_data.values()):
            name = i if preset["name"] == '' else preset["name"].lower()
            parsed[name] = []
            for color in ["red", "green", "blue", "white"]:
                if color not in preset or preset[color] is None:
                    parsed[name].append(0)
                    continue
                parsed[name].append(preset[color] / 255)
        return parsed

    @staticmethod
    def rgb_to_hex(color):
        hex_color = '#'
        for value in color:
            int_value = round(value * 255)
            hex_color += hex(int_value)[2:].zfill(2)
        return hex_color.upper()

    @staticmethod
    def rgbw_to_rgb(color):
        # The idea here is to use the white channel as a saturation control
        # The white channel 'washes' the color
        return (
            [color[3] for i in range(3)]  # Special case of only white channel
            if color[0] == 0 and color[1] == 0 and color[2] == 0
            else [color[i] + (1 - color[i]) * color[3] / 3 for i in range(3)]
        )
