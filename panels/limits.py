import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return LimitsPanel(*args)


class LimitsPanel(ScreenPanel):
    values = {}

    def initialize(self, panel_name):

        self.limits = {}

        scroll = self._gtk.ScrolledWindow()

        # Create a grid for all limits
        self.grid = Gtk.Grid()
        scroll.add(self.grid)

        conf = self._printer.get_config_section("printer")
        self.options = [
            {"name": _("Max Acceleration"), "units": _("mm/s²"), "option": "max_accel",
             "max": self.stn(conf['max_accel'])},
            {"name": _("Max Acceleration to Deceleration"), "units": _("mm/s²"), "option": "max_accel_to_decel",
             "max": self.stn(conf['max_accel_to_decel']) if "max_accel_to_decel" in conf else
             round(self.stn(conf['max_accel']) / 2)},
            {"name": _("Max Velocity"), "units": _("mm/s"), "option": "max_velocity",
             "max": self.stn(conf["max_velocity"])},
            {"name": _("Square Corner Velocity"), "units": _("mm/s"), "option": "square_corner_velocity",
             "max": self.stn(conf['square_corner_velocity']) if "square_corner_velocity" in conf else 5}
        ]

        for opt in self.options:
            self.add_option(opt['option'], opt['name'], opt['units'], opt['max'])

        self.content.add(scroll)
        self.content.show_all()

    def stn(self, str):
        return int(float(str))

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for opt in self.limits:
            if "toolhead" in data and opt in data["toolhead"]:
                self.update_option(opt, data["toolhead"][opt])

    def update_option(self, option, value):
        if option not in self.limits:
            return

        if self.limits[option]['scale'].has_grab():
            return

        self.values[option] = int(value)
        self.limits[option]['scale'].disconnect_by_func(self.set_opt_value)
        self.limits[option]['scale'].set_value(self.values[option])
        for opt in self.options:
            if opt["option"] == option:
                if self.values[option] > opt["max"]:
                    self.limits[option]['scale'].get_style_context().add_class("option_slider_max")
                else:
                    self.limits[option]['scale'].get_style_context().remove_class("option_slider_max")
        self.limits[option]['scale'].connect("button-release-event", self.set_opt_value, option)

    def add_option(self, option, optname, units, value):
        logging.info("Adding option: %s" % option)

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big> (%s)" % (optname, units))
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        adj = Gtk.Adjustment(0, 1, (value * 1.5), 1, 5, 0)
        self.values[option] = value
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_value(self.values[option])
        scale.set_digits(0)
        scale.set_hexpand(True)
        scale.set_has_origin(True)
        scale.get_style_context().add_class("option_slider")
        scale.connect("button-release-event", self.set_opt_value, option)

        reset = self._gtk.ButtonImage("refresh", None, "color1")
        reset.connect("clicked", self.reset_value, option)
        reset.set_hexpand(False)

        item = Gtk.Grid()
        item.attach(name, 0, 0, 2, 1)
        item.attach(scale, 0, 1, 1, 1)
        item.attach(reset, 1, 1, 1, 1)

        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")
        frame.add(item)

        self.limits[option] = {
            "row": frame,
            "scale": scale,
        }

        limits = sorted(self.limits)
        pos = limits.index(option)

        self.grid.insert_row(pos)
        self.grid.attach(self.limits[option]['row'], 0, pos, 1, 1)
        self.grid.show_all()

    def reset_value(self, widget, option):
        for x in self.options:
            if x["option"] == option:
                self.update_option(option, x["max"])
        self.set_opt_value(None, None, option)

    def set_opt_value(self, widget, event, opt):
        value = self.limits[opt]['scale'].get_value()

        if opt == "max_accel":
            self._screen._ws.klippy.gcode_script("SET_VELOCITY_LIMIT ACCEL=%s" % value)
        elif opt == "max_accel_to_decel":
            self._screen._ws.klippy.gcode_script("SET_VELOCITY_LIMIT ACCEL_TO_DECEL=%s" % value)
        elif opt == "max_velocity":
            self._screen._ws.klippy.gcode_script("SET_VELOCITY_LIMIT VELOCITY=%s" % value)
        elif opt == "square_corner_velocity":
            self._screen._ws.klippy.gcode_script("SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=%s" % value)
