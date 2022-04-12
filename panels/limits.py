import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, Pango

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return LimitsPanel(*args)


class LimitsPanel(ScreenPanel):
    values = {}

    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.devices = {}

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        # Create a grid for all devices
        self.labels['devices'] = Gtk.Grid()
        scroll.add(self.labels['devices'])

        # Create a box to contain all of the above
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.pack_start(scroll, True, True, 0)

        conf = self._printer.get_config_section("printer")
        self.options = [
            {"name": _("Max Accelation"), "units": _("mm/s^2"), "option": "max_accel",
                "value": self.stn(conf['max_accel'])},
            {"name": _("Max Acceleration to Deceleration"), "units": _("mm/s^2"), "option": "max_accel_to_decel",
                "value": self.stn(conf['max_accel_to_decel']) if "max_accel_to_decel" in conf else
                round(self.stn(conf['max_accel'])/2)},
            {"name": _("Max Velocity"), "units": _("mm/s"), "option": "max_velocity",
                "value": self.stn(conf["max_velocity"])},
            {"name": _("Square Corner Velocity"), "units": _("mm/s"), "option": "square_corner_velocity",
                "value": self.stn(conf['square_corner_velocity']) if "square_corner_velocity" in conf else 5}
        ]

        for opt in self.options:
            self.add_option(opt['option'], opt['name'], opt['units'], opt['value'])

        self.content.add(box)
        self.content.show_all()

    def stn(self, str):
        return int(float(str))

    def process_update(self, action, data):
        if (action != "notify_status_update"):
            return

        for opt in self.devices:
            if "toolhead" in data and opt in data["toolhead"]:
                self.update_option(opt, data["toolhead"][opt])

    def update_option(self, option, value):
        if option not in self.devices:
            return

        if self.devices[option]['scale'].has_grab():
            return

        self.values[option] = int(value)
        self.devices[option]['scale'].disconnect_by_func(self.set_opt_value)
        self.devices[option]['scale'].set_value(self.values[option])
        self.devices[option]['scale'].connect("button-release-event", self.set_opt_value, option)

    def add_option(self, option, optname, units, value):
        logging.info("Adding option: %s" % option)

        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big> (%s)" % (optname, units))
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        adj = Gtk.Adjustment(0, 0, value, 1, 5, 0)
        self.values[option] = value
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_value(self.values[option])
        scale.set_digits(0)
        scale.set_hexpand(True)
        scale.set_has_origin(True)
        scale.get_style_context().add_class("option_slider")
        scale.connect("button-release-event", self.set_opt_value, option)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)
        labels.add(scale)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.add(labels)
        frame.add(dev)

        self.devices[option] = {
            "row": frame,
            "scale": scale,
        }

        devices = sorted(self.devices)
        pos = devices.index(option)

        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(self.devices[option]['row'], 0, pos, 1, 1)
        self.labels['devices'].show_all()

    def set_opt_value(self, widget, event, opt):
        value = self.devices[opt]['scale'].get_value()

        if opt == "max_accel":
            self._screen._ws.klippy.gcode_script("SET_VELOCITY_LIMIT ACCEL=%s" % (value))
        elif opt == "max_accel_to_decel":
            self._screen._ws.klippy.gcode_script("SET_VELOCITY_LIMIT ACCEL_TO_DECEL=%s" % (value))
        elif opt == "max_velocity":
            self._screen._ws.klippy.gcode_script("SET_VELOCITY_LIMIT VELOCITY=%s" % (value))
        elif opt == "square_corner_velocity":
            self._screen._ws.klippy.gcode_script("SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=%s" % (value))
