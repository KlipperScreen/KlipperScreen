import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return FanPanel(*args)


CHANGEABLE_FANS = ["fan", "fan_generic"]


class FanPanel(ScreenPanel):
    fan_speed = {}
    user_selecting = False

    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.devices = {}

        scroll = self._gtk.ScrolledWindow()

        # Create a grid for all devices
        self.labels['devices'] = Gtk.Grid()
        scroll.add(self.labels['devices'])

        # Create a box to contain all of the above
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.pack_start(scroll, True, True, 0)

        self.load_fans()

        self.content.add(box)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for fan in self.devices:
            if fan in data and "speed" in data[fan]:
                self.update_fan_speed(fan, self._printer.get_fan_speed(fan, data[fan]["speed"]))

    def update_fan_speed(self, fan, speed):
        if fan not in self.devices:
            return
        if self.devices[fan]['changeable'] is True:
            if self.devices[fan]['scale'].has_grab():
                return
            self.fan_speed[fan] = round(float(speed) * 100)
            self.devices[fan]['scale'].disconnect_by_func(self.set_fan_speed)
            self.devices[fan]['scale'].set_value(self.fan_speed[fan])
            self.devices[fan]['scale'].connect("button-release-event", self.set_fan_speed, fan)
        else:
            self.fan_speed[fan] = float(speed)
            self.devices[fan]['scale'].set_fraction(self.fan_speed[fan])

    def add_fan(self, fan):
        logging.info("Adding fan: %s" % fan)
        changeable = False
        for x in CHANGEABLE_FANS:
            if fan.startswith(x) or fan == x:
                changeable = True
                break

        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")

        self.fan_speed[fan] = float(self._printer.get_fan_speed(fan))

        name = Gtk.Label()
        if fan == "fan":
            fan_name = "Part Fan"
        else:
            fan_name = " ".join(fan.split(" ")[1:])
        name.set_markup("<big><b>%s</b></big>" % fan_name)
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        adj = Gtk.Adjustment(0, 0, 100, 1, 5, 0)
        if changeable is True:
            self.fan_speed[fan] = round(self.fan_speed[fan] * 100)
            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
            scale.set_value(self.fan_speed[fan])
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("fan_slider")
            scale.connect("button-release-event", self.set_fan_speed, fan)
        else:
            scale = Gtk.ProgressBar()
            scale.set_fraction(self.fan_speed[fan])
            scale.set_show_text(True)
            scale.set_hexpand(True)
            # scale.get_style_context().add_class("fan_slider")

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)
        labels.add(scale)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.add(labels)
        frame.add(dev)

        self.devices[fan] = {
            "changeable": changeable,
            "row": frame,
            "scale": scale,
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
        self.labels['devices'].attach(self.devices[fan]['row'], 0, pos, 1, 1)
        self.labels['devices'].show_all()

    def load_fans(self):
        fans = self._printer.get_fans()
        for fan in fans:
            # Support for hiding devices by name
            name = " ".join(fan.split(" ")[1:]) if not (fan == "fan") else fan
            if name.startswith("_"):
                continue
            self.add_fan(fan)

    def set_fan_speed(self, widget, event, fan):
        value = self.devices[fan]['scale'].get_value()

        if fan == "fan":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.set_fan_speed(value))
        else:
            f = " ".join(fan.split(" ")[1:])
            self._screen._ws.klippy.gcode_script("SET_FAN_SPEED FAN=%s SPEED=%s" % (f, float(value) / 100))
        # Check the speed in case it wasn't applied
        GLib.timeout_add_seconds(1, self.check_fan_speed, fan)

    def check_fan_speed(self, fan):
        self.update_fan_speed(fan, self._printer.get_fan_speed(fan))
        return False
