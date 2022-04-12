import gi
import logging
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, Pango

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return FWRetractionPanel(*args)


class FWRetractionPanel(ScreenPanel):
    values = {}
    list = {}

    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.grid = Gtk.Grid()

        conf = self._printer.get_config_section("firmware_retraction")

        self.options = [
            {"name": _("Retraction Length"),
             "units": _("mm"),
             "option": "retract_length",
             "value": float(conf['retract_length']) if 'retract_length' in conf else 0,
             "digits":2,
             "maxval":4},
            {"name": _("Retraction Speed"),
             "units": _("mm/s"),
             "option": "retract_speed",
             "value": int(float((conf['retract_speed']))) if 'retract_speed' in conf else 20,
             "digits":0,
             "maxval":100},
            {"name": _("Unretract Extra Length"),
             "units": _("mm"),
             "option": "unretract_extra_length",
             "value": float(conf['unretract_extra_length']) if 'unretract_extra_length' in conf else 0,
             "digits":2,
             "maxval":15},
            {"name": _("Unretract Speed"),
             "units": _("mm/s"),
             "option": "unretract_speed",
             "value": int(float((conf['unretract_speed']))) if 'unretract_speed' in conf else 10,
             "digits":0,
             "maxval":60}
        ]

        for opt in self.options:
            self.add_option(opt['option'], opt['name'], opt['units'], opt['value'], opt['digits'], opt["maxval"])

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
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
            logging.info("data")
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
        scale.set_range(0, maxval)
        scale.set_value(self.values[option])
        scale.set_digits(digits)
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

        self.list[option] = {
            "row": frame,
            "scale": scale,
        }

        pos = sorted(self.list).index(option)
        self.grid.attach(self.list[option]['row'], 0, pos, 1, 1)
        self.grid.show_all()

    def set_opt_value(self, widget, event, opt):
        value = self.list[opt]['scale'].get_value()

        if opt == "retract_speed":
            self._screen._ws.klippy.gcode_script("SET_RETRACTION RETRACT_SPEED=%s" % (value))
        elif opt == "retract_length":
            self._screen._ws.klippy.gcode_script("SET_RETRACTION RETRACT_LENGTH=%s" % (value))
        elif opt == "unretract_extra_length":
            self._screen._ws.klippy.gcode_script("SET_RETRACTION UNRETRACT_EXTRA_LENGTH=%s" % (value))
        elif opt == "unretract_speed":
            self._screen._ws.klippy.gcode_script("SET_RETRACTION UNRETRACT_SPEED=%s" % (value))
