import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Retraction")
        super().__init__(screen, title)
        self.options = None
        self.grid = Gtk.Grid()
        self.values = {}
        self.list = {}
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

    def update_option(self, option, value):
        if option not in self.list:
            return

        if self.list[option]['scale'].has_grab():
            return

        self.values[option] = float(value)
        # Infinite scale
        for opt in self.options:
            if opt['option'] == option:
                if self.values[option] > opt["maxval"] * .75:
                    self.list[option]['adjustment'].set_upper(self.values[option] * 1.5)
                else:
                    self.list[option]['adjustment'].set_upper(opt["maxval"])
                break
        self.list[option]['scale'].set_value(self.values[option])
        self.list[option]['scale'].disconnect_by_func(self.set_opt_value)
        self.list[option]['scale'].connect("button-release-event", self.set_opt_value, option)

    def add_option(self, option, optname, units, value, digits, maxval):
        logging.info(f"Adding option: {option}")

        name = Gtk.Label(
            hexpand=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        name.set_markup(f"<big><b>{optname}</b></big> ({units})")
        minimum = 1 if option in ["retract_speed", "unretract_speed"] else 0
        self.values[option] = value
        # adj (value, lower, upper, step_increment, page_increment, page_size)
        adj = Gtk.Adjustment(value, minimum, maxval, 1, 5, 0)
        scale = Gtk.Scale(adjustment=adj, digits=digits, hexpand=True,
                          has_origin=True)
        scale.get_style_context().add_class("option_slider")
        scale.connect("button-release-event", self.set_opt_value, option)

        reset = self._gtk.Button("refresh", style="color1")
        reset.connect("clicked", self.reset_value, option)
        reset.set_hexpand(False)

        item = Gtk.Grid()
        item.attach(name, 0, 0, 2, 1)
        item.attach(scale, 0, 1, 1, 1)
        item.attach(reset, 1, 1, 1, 1)

        self.list[option] = {
            "row": item,
            "scale": scale,
            "adjustment": adj,
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
            self._screen._ws.klippy.gcode_script(f"SET_RETRACTION RETRACT_SPEED={value}")
        elif opt == "retract_length":
            self._screen._ws.klippy.gcode_script(f"SET_RETRACTION RETRACT_LENGTH={value}")
        elif opt == "unretract_extra_length":
            self._screen._ws.klippy.gcode_script(f"SET_RETRACTION UNRETRACT_EXTRA_LENGTH={value}")
        elif opt == "unretract_speed":
            self._screen._ws.klippy.gcode_script(f"SET_RETRACTION UNRETRACT_SPEED={value}")
