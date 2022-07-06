import gi
import logging
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return FWRetractionPanel(*args)


class FWRetractionPanel(ScreenPanel):
    values = {}
    list = {}

    def initialize(self, panel_name):

        self.grid = Gtk.Grid()

        conf = self._printer.get_config_section("firmware_retraction")

        retract_length = float(conf['retract_length']) if 'retract_length' in conf else 0
        retract_speed = int(float((conf['retract_speed']))) if 'retract_speed' in conf else 20
        unretract_extra_length = float(conf['unretract_extra_length']) if 'unretract_extra_length' in conf else 0
        unretract_speed = int(float((conf['unretract_speed']))) if 'unretract_speed' in conf else 10
        maxlength = retract_length * 1.2 if retract_length >= 6 else 6
        maxspeed = retract_speed * 1.2 if retract_speed >= 100 else 100

        self.options = [
            {"name": _("Retraction Length"),
             "units": _("mm"),
             "option": "retract_length",
             "value": retract_length,
             "digits": 2,
             "maxval": maxlength},
            {"name": _("Retraction Speed"),
             "units": _("mm/s"),
             "option": "retract_speed",
             "value": retract_speed,
             "digits": 0,
             "maxval": maxspeed},
            {"name": _("Unretract Extra Length"),
             "units": _("mm"),
             "option": "unretract_extra_length",
             "value": unretract_extra_length,
             "digits": 2,
             "maxval": maxlength},
            {"name": _("Unretract Speed"),
             "units": _("mm/s"),
             "option": "unretract_speed",
             "value": unretract_speed,
             "digits": 0,
             "maxval": maxspeed}
        ]

        for opt in self.options:
            self.add_option(opt['option'], opt['name'], opt['units'], opt['value'], opt['digits'], opt["maxval"])

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.grid)

        self.content.add(scroll)
        self.content.show_all()

    def activate(self):
        self._screen._ws.klippy.gcode_script("GET_RETRACTION")

    def process_update(self, action, data):
        if action == "notify_status_update" and "firmware_retraction" in data:
            for opt in self.list:
                if opt in data["firmware_retraction"]:
                    self.update_option(opt, data["firmware_retraction"][opt])
        elif action == "notify_gcode_response":
            # // RETRACT_LENGTH=0.00000 RETRACT_SPEED=20.00000 UNRETRACT_EXTRA_LENGTH=0.00000 UNRETRACT_SPEED=10.00000
            result = re.match(
                "^// [RETRACT_LENGTH= ]+([\\-0-9\\.]+)" +
                "[RETRACT_SPEED= ]+([\\-0-9\\.]+)" +
                "[UNRETRACT_EXTRA_LENGTH= ]+([\\-0-9\\.]+)" +
                "[UNRETRACT_SPEED= ]+([\\-0-9\\.]+)",
                data
            )
            if result:
                self.update_option('retract_length', result.group(1))
                self.update_option('retract_speed', result.group(2))
                self.update_option('unretract_extra_length', result.group(3))
                self.update_option('unretract_speed', result.group(4))

    def update_option(self, option, value):
        if option not in self.list:
            return

        if self.list[option]['scale'].has_grab():
            return

        self.values[option] = float(value)
        self.list[option]['scale'].disconnect_by_func(self.set_opt_value)
        self.list[option]['scale'].set_value(self.values[option])
        self.list[option]['scale'].connect("button-release-event", self.set_opt_value, option)

    def add_option(self, option, optname, units, value, digits, maxval):
        logging.info("Adding option: %s" % option)

        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big> (%s)" % (optname, units))
        name.set_hexpand(True)
        name.set_vexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        if option in ["retract_speed", "unretract_speed"]:
            adj = Gtk.Adjustment(0, 1, maxval, 1, 5, 0)
        else:
            adj = Gtk.Adjustment(0, 0, maxval, 1, 5, 0)
        self.values[option] = value
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_value(self.values[option])
        scale.set_digits(digits)
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

        self.list[option] = {
            "row": frame,
            "scale": scale,
        }

        pos = sorted(self.list).index(option)
        self.grid.attach(self.list[option]['row'], 0, pos, 1, 1)
        self.grid.show_all()

    def reset_value(self, widget, option):
        for x in self.options:
            if x["option"] == option:
                self.update_option(option, x["value"])
        self.set_opt_value(None, None, option)

    def set_opt_value(self, widget, event, opt):
        value = self.list[opt]['scale'].get_value()

        if opt == "retract_speed":
            self._screen._ws.klippy.gcode_script("SET_RETRACTION RETRACT_SPEED=%s" % value)
        elif opt == "retract_length":
            self._screen._ws.klippy.gcode_script("SET_RETRACTION RETRACT_LENGTH=%s" % value)
        elif opt == "unretract_extra_length":
            self._screen._ws.klippy.gcode_script("SET_RETRACTION UNRETRACT_EXTRA_LENGTH=%s" % value)
        elif opt == "unretract_speed":
            self._screen._ws.klippy.gcode_script("SET_RETRACTION UNRETRACT_SPEED=%s" % value)
