import logging
import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return ExtrudePanel(*args)


class ExtrudePanel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        macros = self._printer.get_gcode_macros()
        self.load_filament = any("LOAD_FILAMENT" in macro.upper() for macro in macros)
        self.unload_filament = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)

        self.speeds = ['1', '2', '5', '25']
        self.distances = ['5', '10', '15', '25']
        if self.ks_printer_cfg is not None:
            dis = self.ks_printer_cfg.get("extrude_distances", '5, 10, 15, 25')
            if re.match(r'^[0-9,\s]+$', dis):
                dis = [str(i.strip()) for i in dis.split(',')]
                if 1 < len(dis) < 5:
                    self.distances = dis
            vel = self.ks_printer_cfg.get("extrude_speeds", '1, 2, 5, 25')
            if re.match(r'^[0-9,\s]+$', vel):
                vel = [str(i.strip()) for i in vel.split(',')]
                if 1 < len(vel) < 5:
                    self.speeds = vel

        self.distance = int(self.distances[1])
        self.speed = int(self.speeds[1])
        self.buttons = {
            'extrude': self._gtk.Button("extrude", _("Extrude"), "color4"),
            'load': self._gtk.Button("arrow-down", _("Load"), "color3"),
            'unload': self._gtk.Button("arrow-up", _("Unload"), "color2"),
            'retract': self._gtk.Button("retract", _("Retract"), "color1"),
            'temperature': self._gtk.Button("heat-up", _("Temperature"), "color4"),
        }
        self.buttons['extrude'].connect("clicked", self.extrude, "+")
        self.buttons['load'].connect("clicked", self.load_unload, "+")
        self.buttons['unload'].connect("clicked", self.load_unload, "-")
        self.buttons['retract'].connect("clicked", self.extrude, "-")
        self.buttons['temperature'].connect("clicked", self.menu_item_clicked, "temperature", {
            "name": "Temperature",
            "panel": "temperature"
        })

        extgrid = self._gtk.HomogeneousGrid()
        limit = 5
        i = 0
        for extruder in self._printer.get_tools():
            if self._printer.extrudercount > 1:
                self.labels[extruder] = self._gtk.Button(f"extruder-{i}", f"T{self._printer.get_tool_number(extruder)}")
            else:
                self.labels[extruder] = self._gtk.Button("extruder", "")
            self.labels[extruder].connect("clicked", self.change_extruder, extruder)
            if extruder == self.current_extruder:
                self.labels[extruder].get_style_context().add_class("button_active")
            if i < limit:
                extgrid.attach(self.labels[extruder], i, 0, 1, 1)
                i += 1
        if i < (limit - 1):
            extgrid.attach(self.buttons['temperature'], i + 1, 0, 1, 1)

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.labels[f"dist{i}"] = self._gtk.Button(label=i)
            self.labels[f"dist{i}"].connect("clicked", self.change_distance, int(i))
            ctx = self.labels[f"dist{i}"].get_style_context()
            if ((self._screen.lang_ltr is True and j == 0) or
                    (self._screen.lang_ltr is False and j == len(self.distances) - 1)):
                ctx.add_class("distbutton_top")
            elif ((self._screen.lang_ltr is False and j == 0) or
                  (self._screen.lang_ltr is True and j == len(self.distances) - 1)):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if int(i) == self.distance:
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[f"dist{i}"], j, 0, 1, 1)

        speedgrid = Gtk.Grid()
        for j, i in enumerate(self.speeds):
            self.labels[f"speed{i}"] = self._gtk.Button(label=i)
            self.labels[f"speed{i}"].connect("clicked", self.change_speed, int(i))
            ctx = self.labels[f"speed{i}"].get_style_context()
            if ((self._screen.lang_ltr is True and j == 0) or
                    (self._screen.lang_ltr is False and j == len(self.speeds) - 1)):
                ctx.add_class("distbutton_top")
            elif ((self._screen.lang_ltr is False and j == 0) or
                  (self._screen.lang_ltr is True and j == len(self.speeds) - 1)):
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if int(i) == self.speed:
                ctx.add_class("distbutton_active")
            speedgrid.attach(self.labels[f"speed{i}"], j, 0, 1, 1)

        distbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['extrude_dist'] = Gtk.Label(_("Distance (mm)"))
        distbox.pack_start(self.labels['extrude_dist'], True, True, 0)
        distbox.add(distgrid)
        speedbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['extrude_speed'] = Gtk.Label(_("Speed (mm/s)"))
        speedbox.pack_start(self.labels['extrude_speed'], True, True, 0)
        speedbox.add(speedgrid)

        filament_sensors = self._printer.get_filament_sensors()
        sensors = Gtk.Grid()
        if len(filament_sensors) > 0:
            sensors.set_column_spacing(5)
            sensors.set_row_spacing(5)
            sensors.set_halign(Gtk.Align.CENTER)
            sensors.set_valign(Gtk.Align.CENTER)
            for s, x in enumerate(filament_sensors):
                if s > limit:
                    break
                name = x[23:].strip()
                self.labels[x] = {
                    'label': Gtk.Label(name.capitalize().replace('_', ' ')),
                    'switch': Gtk.Switch(),
                    'box': Gtk.Box()
                }
                self.labels[x]['label'].set_halign(Gtk.Align.CENTER)
                self.labels[x]['label'].set_hexpand(True)
                self.labels[x]['label'].set_ellipsize(Pango.EllipsizeMode.END)
                self.labels[x]['switch'].set_property("width-request", round(self._gtk.font_size * 2))
                self.labels[x]['switch'].set_property("height-request", round(self._gtk.font_size))
                self.labels[x]['switch'].connect("notify::active", self.enable_disable_fs, name, x)
                self.labels[x]['box'].pack_start(self.labels[x]['label'], True, True, 5)
                self.labels[x]['box'].pack_start(self.labels[x]['switch'], False, False, 5)
                self.labels[x]['box'].get_style_context().add_class("filament_sensor")
                self.labels[x]['box'].set_hexpand(True)
                sensors.attach(self.labels[x]['box'], s, 0, 1, 1)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.attach(extgrid, 0, 0, 4, 1)

        if self._screen.vertical_mode:
            grid.attach(self.buttons['extrude'], 0, 1, 2, 1)
            grid.attach(self.buttons['retract'], 2, 1, 2, 1)
            grid.attach(self.buttons['load'], 0, 2, 2, 1)
            grid.attach(self.buttons['unload'], 2, 2, 2, 1)
            grid.attach(distbox, 0, 3, 4, 1)
            grid.attach(speedbox, 0, 4, 4, 1)
            grid.attach(sensors, 0, 5, 4, 1)
        else:
            grid.attach(self.buttons['extrude'], 0, 2, 1, 1)
            grid.attach(self.buttons['load'], 1, 2, 1, 1)
            grid.attach(self.buttons['unload'], 2, 2, 1, 1)
            grid.attach(self.buttons['retract'], 3, 2, 1, 1)
            grid.attach(distbox, 0, 3, 2, 1)
            grid.attach(speedbox, 2, 3, 2, 1)
            grid.attach(sensors, 0, 4, 4, 1)

        self.content.add(grid)

    def process_busy(self, busy):
        for button in self.buttons:
            if button == "temperature":
                continue
            self.buttons[button].set_sensitive((not busy))

    def process_update(self, action, data):
        if action == "notify_busy":
            self.process_busy(data)
            return
        if action != "notify_status_update":
            return
        for x in self._printer.get_tools():
            self.update_temp(
                x,
                self._printer.get_dev_stat(x, "temperature"),
                self._printer.get_dev_stat(x, "target"),
                self._printer.get_dev_stat(x, "power"),
                lines=2,
            )

        if ("toolhead" in data and "extruder" in data["toolhead"] and
                data["toolhead"]["extruder"] != self.current_extruder):
            for extruder in self._printer.get_tools():
                self.labels[extruder].get_style_context().remove_class("button_active")
            self.current_extruder = data["toolhead"]["extruder"]
            self.labels[self.current_extruder].get_style_context().add_class("button_active")

        for x in self._printer.get_filament_sensors():
            if x in data:
                if 'enabled' in data[x]:
                    self._printer.set_dev_stat(x, "enabled", data[x]['enabled'])
                    self.labels[x]['switch'].set_active(data[x]['enabled'])
                if 'filament_detected' in data[x]:
                    self._printer.set_dev_stat(x, "filament_detected", data[x]['filament_detected'])
                    if self._printer.get_stat(x, "enabled"):
                        if data[x]['filament_detected']:
                            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
                            self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
                        else:
                            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")
                            self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
                logging.info(f"{x}: {self._printer.get_stat(x)}")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"dist{self.distance}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"dist{distance}"].get_style_context().add_class("distbutton_active")
        self.distance = distance

    def change_extruder(self, widget, extruder):
        logging.info(f"Changing extruder to {extruder}")
        for tool in self._printer.get_tools():
            self.labels[tool].get_style_context().remove_class("button_active")
        self.labels[extruder].get_style_context().add_class("button_active")

        self._screen._ws.klippy.gcode_script(f"T{self._printer.get_tool_number(extruder)}")

    def change_speed(self, widget, speed):
        logging.info(f"### Speed {speed}")
        self.labels[f"speed{self.speed}"].get_style_context().remove_class("distbutton_active")
        self.labels[f"speed{speed}"].get_style_context().add_class("distbutton_active")
        self.speed = speed

    def extrude(self, widget, direction):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.EXTRUDE_REL)
        self._screen._ws.klippy.gcode_script(KlippyGcodes.extrude(f"{direction}{self.distance}", f"{self.speed * 60}"))

    def load_unload(self, widget, direction):
        if direction == "-":
            if not self.unload_filament:
                self._screen.show_popup_message("Macro UNLOAD_FILAMENT not found")
            else:
                self._screen._ws.klippy.gcode_script(f"UNLOAD_FILAMENT SPEED={self.speed * 60}")
        if direction == "+":
            if not self.load_filament:
                self._screen.show_popup_message("Macro LOAD_FILAMENT not found")
            else:
                self._screen._ws.klippy.gcode_script(f"LOAD_FILAMENT SPEED={self.speed * 60}")

    def enable_disable_fs(self, switch, gparams, name, x):
        if switch.get_active():
            self._printer.set_dev_stat(x, "enabled", True)
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=1")
            if self._printer.get_stat(x, "filament_detected"):
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
            else:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
        else:
            self._printer.set_dev_stat(x, "enabled", False)
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=0")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")
