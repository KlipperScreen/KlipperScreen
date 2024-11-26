import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel

# TODO multi-extruder support


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Pressure advance")
        super().__init__(screen, title)
        self.current_extruder = "extruder"
        self.current_extruder_label = Gtk.Label(
            label=_("Current") + f": {self.current_extruder}"
        )
        self.grid = Gtk.Grid()
        self.grid.attach(self.current_extruder_label, 0, 0, 1, 1)
        self.values = {}
        self.list = {}
        self.options = [
            {
                "name": _("Pressure Advance"),
                "units": _("mm"),
                "option": "pressure_advance",
                "value": 0,
                "digits": 2,
                "maxval": 1,
            },
            {
                "name": _("Smooth time"),
                "units": _("s"),
                "option": "smooth_time",
                "value": 0.04,
                "digits": 3,
                "maxval": 0.200,
            },
        ]

        for opt in self.options:
            self.add_option(opt)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.grid)

        self.content.add(scroll)
        self.content.show_all()

    def add_option(self, option_data):
        option = option_data["option"]
        optname = option_data["name"]
        units = option_data["units"]
        value = option_data["value"]
        digits = option_data["digits"]
        maxval = option_data["maxval"]

        logging.info(f"Adding option: {option}")

        name_label = Gtk.Label()
        name_label.set_markup(f"<big><b>{optname}</b></big> ({units})")

        adjustment = Gtk.Adjustment(
            value,
            0,
            maxval,
            0.05 if option.startswith("pressure") else 0.005,
            0.1 if option.startswith("pressure") else 0.01,
            0,
        )

        scale = Gtk.Scale(
            adjustment=adjustment,
            digits=digits,
            hexpand=True,
            has_origin=True,
        )
        scale.get_style_context().add_class("option_slider")
        scale.connect("button-release-event", self.set_opt_value, option)

        reset_button = self._gtk.Button("refresh", style="color1")
        reset_button.connect("clicked", self.reset_value, option)
        reset_button.set_hexpand(False)

        item = Gtk.Grid()
        item.attach(name_label, 0, 0, 2, 1)
        item.attach(scale, 0, 1, 1, 1)
        item.attach(reset_button, 1, 1, 1, 1)

        self.list[option] = {
            "row": item,
            "scale": scale,
            "adjustment": adjustment,
        }

        pos = sorted(self.list).index(option) + 1
        self.grid.attach(self.list[option]["row"], 0, pos, 1, 1)
        self.grid.show_all()

    def reset_value(self, widget, option):
        for opt in self.options:
            if opt["option"] == option:
                self.update_option(option, opt["value"])
        self.set_opt_value(None, None, option)

    def set_opt_value(self, widget, event, opt):
        value = self.list[opt]["scale"].get_value()
        if opt == "pressure_advance":
            self._screen._ws.klippy.gcode_script(
                f"SET_PRESSURE_ADVANCE EXTRUDER={self.current_extruder} ADVANCE={value}"
            )
        if opt == "smooth_time":
            self._screen._ws.klippy.gcode_script(
                f"SET_PRESSURE_ADVANCE EXTRUDER={self.current_extruder} SMOOTH_TIME={value}"
            )

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        if (
            "toolhead" in data
            and "extruder" in data["toolhead"]
            and data["toolhead"]["extruder"]
        ):
            self.current_extruder = data["toolhead"]["extruder"]
            logging.debug(f"Changing to {self.current_extruder}")
            self.current_extruder_label.set_label(
                _("Current") + f": {self.current_extruder}"
            )
            for opt in self.list:
                if opt in self._printer.data[self.current_extruder]:
                    self.update_option(
                        opt, self._printer.data[self.current_extruder][opt]
                    )
        if self.current_extruder in data:
            for opt in self.list:
                if opt in data[self.current_extruder]:
                    self.update_option(opt, data[self.current_extruder][opt])

    def update_option(self, option, value):
        if option not in self.list:
            return

        if self.list[option]["scale"].has_grab():
            return

        self.values[option] = float(value)

        # Infinite scale
        for opt in self.options:
            if opt["option"] == option and not option.startswith("smooth_time"):
                if self.values[option] > opt["maxval"] * 0.75:
                    self.list[option]["adjustment"].set_upper(self.values[option] * 1.5)
                else:
                    self.list[option]["adjustment"].set_upper(opt["maxval"])
                break
        self.list[option]["scale"].set_value(self.values[option])
        self.list[option]["scale"].disconnect_by_func(self.set_opt_value)
        self.list[option]["scale"].connect(
            "button-release-event", self.set_opt_value, option
        )
