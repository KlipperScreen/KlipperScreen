import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return FanPanel(*args)


CHANGEABLE_FANS = ["fan", "fan_generic"]


class FanPanel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.fan_speed = {}
        self.devices = {}
        # Create a grid for all devices
        self.labels['devices'] = Gtk.Grid()
        self.labels['devices'].set_valign(Gtk.Align.CENTER)

        self.load_fans()

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels['devices'])

        self.content.add(scroll)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for fan in self.devices:
            if fan in data and "speed" in data[fan]:
                self.update_fan_speed(None, fan, self._printer.get_fan_speed(fan))

    def update_fan_speed(self, widget, fan, speed):
        if fan not in self.devices:
            return

        if self.devices[fan]['changeable'] is True:
            if self.devices[fan]['scale'].has_grab():
                return
            self.devices[fan]["speed"] = round(float(speed) * 100)
            self.devices[fan]['scale'].disconnect_by_func(self.set_fan_speed)
            self.devices[fan]['scale'].set_value(self.devices[fan]["speed"])
            self.devices[fan]['scale'].connect("button-release-event", self.set_fan_speed, fan)
        else:
            self.devices[fan]["speed"] = float(speed)
            self.devices[fan]['scale'].set_fraction(self.devices[fan]["speed"])
        if widget is not None:
            self.set_fan_speed(None, None, fan)

    def add_fan(self, fan):

        logging.info(f"Adding fan: {fan}")
        changeable = any(fan.startswith(x) or fan == x for x in CHANGEABLE_FANS)
        name = Gtk.Label()
        fan_name = _("Part Fan") if fan == "fan" else fan.split()[1]
        name.set_markup(f"\n<big><b>{fan_name}</b></big>\n")
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        fan_col = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        stop_btn = self._gtk.Button("cancel", None, "color1")
        stop_btn.set_hexpand(False)
        stop_btn.connect("clicked", self.update_fan_speed, fan, 0)
        max_btn = self._gtk.Button("fan-on", _("Max"), "color2")
        max_btn.set_hexpand(False)
        max_btn.connect("clicked", self.update_fan_speed, fan, 100)

        speed = float(self._printer.get_fan_speed(fan))
        if changeable:
            speed = round(speed * 100)
            scale = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.HORIZONTAL, min=0, max=100, step=1)
            scale.set_value(speed)
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            scale.connect("button-release-event", self.set_fan_speed, fan)
            fan_col.add(stop_btn)
            fan_col.add(scale)
            fan_col.add(max_btn)
        else:
            scale = Gtk.ProgressBar()
            scale.set_fraction(speed)
            scale.set_show_text(True)
            scale.set_hexpand(True)
            fan_col.pack_start(scale, True, True, 10)

        fan_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        fan_row.add(name)
        fan_row.add(fan_col)

        self.devices[fan] = {
            "changeable": changeable,
            "scale": scale,
            "speed": speed,
        }

        devices = sorted(self.devices)
        if fan == "fan":
            pos = 0
        elif "fan" in devices:
            devices.pop(devices.index("fan"))
            pos = devices.index(fan) + 1
        else:
            pos = devices.index(fan)

        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(fan_row, 0, pos, 1, 1)
        self.labels['devices'].show_all()

    def load_fans(self):
        fans = self._printer.get_fans()
        for fan in fans:
            # Support for hiding devices by name
            name = fan.split()[1] if len(fan.split()) > 1 else fan
            if name.startswith("_"):
                continue
            self.add_fan(fan)

    def set_fan_speed(self, widget, event, fan):
        value = self.devices[fan]['scale'].get_value()

        if fan == "fan":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.set_fan_speed(value))
        else:
            self._screen._ws.klippy.gcode_script(f"SET_FAN_SPEED FAN={fan.split()[1]} SPEED={float(value) / 100}")
        # Check the speed in case it wasn't applied
        GLib.timeout_add_seconds(1, self.check_fan_speed, fan)

    def check_fan_speed(self, fan):
        self.update_fan_speed(None, fan, self._printer.get_fan_speed(fan))
        return False
