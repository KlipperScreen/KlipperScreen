import logging
import re
import contextlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return FineTunePanel(*args)


class FineTunePanel(ScreenPanel):
    bs_deltas = ["0.01", "0.05"]
    bs_delta = bs_deltas[-1]
    percent_deltas = ['1', '5', '10', '25']
    percent_delta = percent_deltas[-2]
    speed = extrusion = 100

    def __init__(self, screen, title):
        super().__init__(screen, title)
        if self.ks_printer_cfg is not None:
            bs = self.ks_printer_cfg.get("z_babystep_values", "0.01, 0.05")
            if re.match(r'^[0-9,\.\s]+$', bs):
                bs = [str(i.strip()) for i in bs.split(',')]
                if 1 < len(bs) < 3:
                    self.bs_deltas = bs
                    self.bs_delta = self.bs_deltas[-1]

        # babystepping grid
        bsgrid = Gtk.Grid()
        for j, i in enumerate(self.bs_deltas):
            self.labels[f"bdelta{i}"] = self._gtk.Button(label=i)
            self.labels[f"bdelta{i}"].connect("clicked", self.change_bs_delta, float(i))
            ctx = self.labels[f"bdelta{i}"].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.bs_deltas) - 1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.bs_delta:
                ctx.add_class("distbutton_active")
            bsgrid.attach(self.labels[f"bdelta{i}"], j, 0, 1, 1)
        # Grid for percentage
        deltgrid = Gtk.Grid()
        for j, i in enumerate(self.percent_deltas):
            self.labels[f"pdelta{i}"] = self._gtk.Button(label=f"{i}%")
            self.labels[f"pdelta{i}"].connect("clicked", self.change_percent_delta, int(i))
            ctx = self.labels[f"pdelta{i}"].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.percent_deltas) - 1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == self.percent_delta:
                ctx.add_class("distbutton_active")
            deltgrid.attach(self.labels[f"pdelta{i}"], j, 0, 1, 1)

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)

        self.labels['z+'] = self._gtk.Button("z-farther", "Z+", "color1")
        self.labels['z-'] = self._gtk.Button("z-closer", "Z-", "color1")
        self.labels['zoffset'] = self._gtk.Button("refresh", '  0.00' + _("mm"),
                                                  "color1", self.bts, Gtk.PositionType.LEFT, 1)
        self.labels['speed+'] = self._gtk.Button("speed+", _("Speed +"), "color3")
        self.labels['speed-'] = self._gtk.Button("speed-", _("Speed -"), "color3")
        self.labels['speedfactor'] = self._gtk.Button("refresh", "  100%",
                                                      "color3", self.bts, Gtk.PositionType.LEFT, 1)

        self.labels['extrude+'] = self._gtk.Button("flow+", _("Extrusion +"), "color4")
        self.labels['extrude-'] = self._gtk.Button("flow-", _("Extrusion -"), "color4")
        self.labels['extrudefactor'] = self._gtk.Button("refresh", "  100%",
                                                        "color4", self.bts, Gtk.PositionType.LEFT, 1)
        if self._screen.vertical_mode:
            grid.attach(self.labels['z+'], 0, 0, 1, 1)
            grid.attach(self.labels['z-'], 1, 0, 1, 1)
            grid.attach(self.labels['zoffset'], 2, 0, 1, 1)
            grid.attach(bsgrid, 0, 1, 3, 1)
            grid.attach(self.labels['speed-'], 0, 2, 1, 1)
            grid.attach(self.labels['speed+'], 1, 2, 1, 1)
            grid.attach(self.labels['speedfactor'], 2, 2, 1, 1)
            grid.attach(self.labels['extrude-'], 0, 3, 1, 1)
            grid.attach(self.labels['extrude+'], 1, 3, 1, 1)
            grid.attach(self.labels['extrudefactor'], 2, 3, 1, 1)
            grid.attach(deltgrid, 0, 4, 3, 1)
        else:
            grid.attach(self.labels['zoffset'], 0, 0, 1, 1)
            grid.attach(self.labels['z+'], 0, 1, 1, 1)
            grid.attach(self.labels['z-'], 0, 2, 1, 1)
            grid.attach(bsgrid, 0, 3, 1, 1)
            grid.attach(self.labels['speedfactor'], 1, 0, 1, 1)
            grid.attach(self.labels['speed+'], 1, 1, 1, 1)
            grid.attach(self.labels['speed-'], 1, 2, 1, 1)
            grid.attach(self.labels['extrudefactor'], 2, 0, 1, 1)
            grid.attach(self.labels['extrude+'], 2, 1, 1, 1)
            grid.attach(self.labels['extrude-'], 2, 2, 1, 1)
            grid.attach(deltgrid, 1, 3, 2, 1)

        self.labels['z+'].connect("clicked", self.change_babystepping, "+")
        self.labels['zoffset'].connect("clicked", self.change_babystepping, "reset")
        self.labels['z-'].connect("clicked", self.change_babystepping, "-")
        self.labels['speed+'].connect("clicked", self.change_speed, "+")
        self.labels['speedfactor'].connect("clicked", self.change_speed, "reset")
        self.labels['speed-'].connect("clicked", self.change_speed, "-")
        self.labels['extrude+'].connect("clicked", self.change_extrusion, "+")
        self.labels['extrudefactor'].connect("clicked", self.change_extrusion, "reset")
        self.labels['extrude-'].connect("clicked", self.change_extrusion, "-")

        self.content.add(grid)

    def process_update(self, action, data):

        if action != "notify_status_update":
            return

        if "gcode_move" in data:
            if "homing_origin" in data["gcode_move"]:
                self.labels['zoffset'].set_label(f'  {data["gcode_move"]["homing_origin"][2]:.3f}mm')
            if "extrude_factor" in data["gcode_move"]:
                self.extrusion = round(float(data["gcode_move"]["extrude_factor"]) * 100)
                self.labels['extrudefactor'].set_label(f"  {self.extrusion:3}%")
            if "speed_factor" in data["gcode_move"]:
                self.speed = round(float(data["gcode_move"]["speed_factor"]) * 100)
                self.labels['speedfactor'].set_label(f"  {self.speed:3}%")

    def change_babystepping(self, widget, direction):
        if direction == "reset":
            self.labels['zoffset'].set_label('  0.00mm')
            self._screen._ws.klippy.gcode_script("SET_GCODE_OFFSET Z=0 MOVE=1")
        elif direction in ["+", "-"]:
            with contextlib.suppress(KeyError):
                z_offset = float(self._printer.data["gcode_move"]["homing_origin"][2])
                if direction == "+":
                    z_offset += float(self.bs_delta)
                else:
                    z_offset -= float(self.bs_delta)
                self.labels['zoffset'].set_label(f'  {z_offset:.3f}mm')
            self._screen._ws.klippy.gcode_script(f"SET_GCODE_OFFSET Z_ADJUST={direction}{self.bs_delta} MOVE=1")

    def change_bs_delta(self, widget, bs):
        logging.info(f"### BabyStepping {bs}")
        self.labels[f"bdelta{self.bs_delta}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"bdelta{bs}"].get_style_context().add_class("distbutton_active")
        self.bs_delta = bs

    def change_extrusion(self, widget, direction):
        if direction == "+":
            self.extrusion += int(self.percent_delta)
        elif direction == "-":
            self.extrusion -= int(self.percent_delta)
        elif direction == "reset":
            self.extrusion = 100

        self.extrusion = max(self.extrusion, 1)
        self.labels['extrudefactor'].set_label(f"  {self.extrusion:3}%")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.set_extrusion_rate(self.extrusion))

    def change_speed(self, widget, direction):
        if direction == "+":
            self.speed += int(self.percent_delta)
        elif direction == "-":
            self.speed -= int(self.percent_delta)
        elif direction == "reset":
            self.speed = 100

        self.speed = max(self.speed, 1)
        self.labels['speedfactor'].set_label(f"  {self.speed:3}%")
        self._screen._ws.klippy.gcode_script(KlippyGcodes.set_speed_rate(self.speed))

    def change_percent_delta(self, widget, delta):
        logging.info(f"### Delta {delta}")
        self.labels[f"pdelta{self.percent_delta}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"pdelta{delta}"].get_style_context().add_class("distbutton_active")
        self.percent_delta = delta
