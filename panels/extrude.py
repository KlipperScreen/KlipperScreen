import logging
import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.autogrid import AutoGrid
from ks_includes.KlippyGtk import find_widget


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Extrude")
        super().__init__(screen, title)
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        macros = self._printer.get_config_section_list("gcode_macro ")
        self.load_filament = any("LOAD_FILAMENT" in macro.upper() for macro in macros)
        self.unload_filament = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)

        self.speeds = ['1', '2', '5', '25']
        self.distances = ['5', '10', '15', '25']
        if self.ks_printer_cfg is not None:
            dis = self.ks_printer_cfg.get("extrude_distances", '')
            if re.match(r'^[0-9,\s]+$', dis):
                dis = [str(i.strip()) for i in dis.split(',')]
                if 1 < len(dis) < 5:
                    self.distances = dis
            vel = self.ks_printer_cfg.get("extrude_speeds", '')
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
            'spoolman': self._gtk.Button("spoolman", "Spoolman", "color3"),
            'pressure': self._gtk.Button("settings", _("Pressure Advance"), "color2"),
            'retraction': self._gtk.Button("settings", _("Retraction"), "color1")
        }
        self.buttons['extrude'].connect("clicked", self.check_min_temp, "extrude", "+")
        self.buttons['load'].connect("clicked", self.check_min_temp, "load_unload", "+")
        self.buttons['unload'].connect("clicked", self.check_min_temp, "load_unload", "-")
        self.buttons['retract'].connect("clicked", self.check_min_temp, "extrude", "-")
        self.buttons['temperature'].connect("clicked", self.menu_item_clicked, {
            "panel": "temperature"
        })
        self.buttons['spoolman'].connect("clicked", self.menu_item_clicked, {
            "panel": "spoolman"
        })
        self.buttons['pressure'].connect("clicked", self.menu_item_clicked, {
            "panel": "pressure_advance"
        })
        self.buttons['retraction'].connect("clicked", self.menu_item_clicked, {
            "panel": "retraction"
        })

        xbox = Gtk.Box(homogeneous=True)
        limit = 4
        i = 0
        extruder_buttons = []
        self.labels = {}
        for extruder in self._printer.get_tools():
            if self._printer.extrudercount == 1:
                self.labels[extruder] = self._gtk.Button("extruder", "")
            else:
                n = self._printer.get_tool_number(extruder)
                self.labels[extruder] = self._gtk.Button(f"extruder-{n}", f"T{n}")
                self.labels[extruder].connect("clicked", self.change_extruder, extruder)
            if extruder == self.current_extruder:
                self.labels[extruder].get_style_context().add_class("button_active")
            if self._printer.extrudercount < limit:
                xbox.add(self.labels[extruder])
                i += 1
            else:
                extruder_buttons.append(self.labels[extruder])
        for widget in self.labels.values():
            label = find_widget(widget, Gtk.Label)
            label.set_justify(Gtk.Justification.CENTER)
            label.set_line_wrap(True)
            label.set_lines(2)
        if extruder_buttons:
            self.labels['extruders'] = AutoGrid(extruder_buttons, vertical=self._screen.vertical_mode)
            self.labels['extruders_menu'] = self._gtk.ScrolledWindow()
            self.labels['extruders_menu'].add(self.labels['extruders'])
        if self._printer.extrudercount >= limit:
            changer = self._gtk.Button("toolchanger")
            changer.connect("clicked", self.load_menu, 'extruders', _('Extruders'))
            xbox.add(changer)
            self.labels["current_extruder"] = self._gtk.Button("extruder", "")
            xbox.add(self.labels["current_extruder"])
            self.labels["current_extruder"].connect("clicked", self.load_menu, 'extruders', _('Extruders'))
        if not self._screen.vertical_mode:
            xbox.add(self.buttons['pressure'])
            i += 1
        if self._printer.get_config_section("firmware_retraction") and not self._screen.vertical_mode:
            xbox.add(self.buttons['retraction'])
            i += 1
        if i < limit:
            xbox.add(self.buttons['temperature'])
        if i < (limit - 1) and self._printer.spoolman:
            xbox.add(self.buttons['spoolman'])

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.labels[f"dist{i}"] = self._gtk.Button(label=i)
            self.labels[f"dist{i}"].connect("clicked", self.change_distance, int(i))
            ctx = self.labels[f"dist{i}"].get_style_context()
            ctx.add_class("horizontal_togglebuttons")
            if self._screen.vertical_mode:
                ctx.add_class("horizontal_togglebuttons_smaller")
            if int(i) == self.distance:
                ctx.add_class("horizontal_togglebuttons_active")
            distgrid.attach(self.labels[f"dist{i}"], j, 0, 1, 1)

        speedgrid = Gtk.Grid()
        for j, i in enumerate(self.speeds):
            self.labels[f"speed{i}"] = self._gtk.Button(label=i)
            self.labels[f"speed{i}"].connect("clicked", self.change_speed, int(i))
            ctx = self.labels[f"speed{i}"].get_style_context()
            ctx.add_class("horizontal_togglebuttons")
            if self._screen.vertical_mode:
                ctx.add_class("horizontal_togglebuttons_smaller")
            if int(i) == self.speed:
                ctx.add_class("horizontal_togglebuttons_active")
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
        sensors = Gtk.Grid(valign=Gtk.Align.CENTER, row_spacing=5, column_spacing=5)
        with_switches = (
            len(filament_sensors) < 4
            and not (self._screen.vertical_mode and self._screen.height < 600)
        )
        for s, x in enumerate(filament_sensors):
            if s > 8:
                break
            name = x.split(" ", 1)[1].strip()
            self.labels[x] = {
                'label': Gtk.Label(
                    label=self.prettify(name), hexpand=True, halign=Gtk.Align.CENTER,
                    ellipsize=Pango.EllipsizeMode.START),
                'box': Gtk.Box()
            }
            self.labels[x]['box'].pack_start(self.labels[x]['label'], True, True, 10)
            if with_switches:
                self.labels[x]['switch'] = Gtk.Switch()
                self.labels[x]['switch'].connect("notify::active", self.enable_disable_fs, name, x)
                self.labels[x]['box'].pack_start(self.labels[x]['switch'], False, False, 0)

            self.labels[x]['box'].get_style_context().add_class("filament_sensor")
            if s // 2:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
            else:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
            sensors.attach(self.labels[x]['box'], s, 0, 1, 1)

        grid = Gtk.Grid(column_homogeneous=True)
        grid.attach(xbox, 0, 0, 4, 1)

        if self._screen.vertical_mode:
            grid.attach(self.buttons['extrude'], 0, 1, 2, 1)
            grid.attach(self.buttons['retract'], 2, 1, 2, 1)
            grid.attach(self.buttons['load'], 0, 2, 2, 1)
            grid.attach(self.buttons['unload'], 2, 2, 2, 1)
            settings_box = Gtk.Box(homogeneous=True)
            settings_box.add(self.buttons['pressure'])
            if self._printer.get_config_section("firmware_retraction"):
                settings_box.add(self.buttons['retraction'])
            grid.attach(settings_box, 0, 3, 4, 1)
            grid.attach(distbox, 0, 4, 4, 1)
            grid.attach(speedbox, 0, 5, 4, 1)
            grid.attach(sensors, 0, 6, 4, 1)
        else:
            grid.attach(self.buttons['extrude'], 0, 2, 1, 1)
            grid.attach(self.buttons['load'], 1, 2, 1, 1)
            grid.attach(self.buttons['unload'], 2, 2, 1, 1)
            grid.attach(self.buttons['retract'], 3, 2, 1, 1)
            grid.attach(distbox, 0, 3, 2, 1)
            grid.attach(speedbox, 2, 3, 2, 1)
            grid.attach(sensors, 0, 4, 4, 1)

        self.menu = ['extrude_menu']
        self.labels['extrude_menu'] = grid
        self.content.add(self.labels['extrude_menu'])

    def enable_buttons(self, enable):
        for button in self.buttons:
            if button in ("pressure", "retraction", "spoolman", "temperature"):
                continue
            self.buttons[button].set_sensitive(enable)

    def activate(self):
        self.enable_buttons(self._printer.state in ("ready", "paused"))

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            if "action:cancel" in data or "action:paused" in data:
                self.enable_buttons(True)
            elif "action:resumed" in data:
                self.enable_buttons(False)
            return
        if action != "notify_status_update":
            return
        for x in self._printer.get_tools():
            if x in data:
                self.update_temp(
                    x,
                    self._printer.get_stat(x, "temperature"),
                    self._printer.get_stat(x, "target"),
                    self._printer.get_stat(x, "power"),
                )
        if "current_extruder" in self.labels:
            self.labels["current_extruder"].set_label(self.labels[self.current_extruder].get_label())

        if ("toolhead" in data and "extruder" in data["toolhead"] and
                data["toolhead"]["extruder"] != self.current_extruder):
            for extruder in self._printer.get_tools():
                self.labels[extruder].get_style_context().remove_class("button_active")
            self.current_extruder = data["toolhead"]["extruder"]
            self.labels[self.current_extruder].get_style_context().add_class("button_active")
            if "current_extruder" in self.labels:
                n = self._printer.get_tool_number(self.current_extruder)
                self.labels["current_extruder"].set_image(self._gtk.Image(f"extruder-{n}"))

        for x in self._printer.get_filament_sensors():
            if x in data and x in self.labels:
                if 'enabled' in data[x] and 'switch' in self.labels[x]:
                    self.labels[x]['switch'].set_active(data[x]['enabled'])
                if 'filament_detected' in data[x] and self._printer.get_stat(x, "enabled"):
                    if data[x]['filament_detected']:
                        self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
                        self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
                    else:
                        self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")
                        self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")

    def change_distance(self, widget, distance):
        logging.info(f"### Distance {distance}")
        self.labels[f"dist{self.distance}"].get_style_context().remove_class("horizontal_togglebuttons_active")
        self.labels[f"dist{distance}"].get_style_context().add_class("horizontal_togglebuttons_active")
        self.distance = distance

    def change_extruder(self, widget, extruder):
        logging.info(f"Changing extruder to {extruder}")
        for tool in self._printer.get_tools():
            self.labels[tool].get_style_context().remove_class("button_active")
        self.labels[extruder].get_style_context().add_class("button_active")
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"T{self._printer.get_tool_number(extruder)}"})

    def change_speed(self, widget, speed):
        logging.info(f"### Speed {speed}")
        self.labels[f"speed{self.speed}"].get_style_context().remove_class("horizontal_togglebuttons_active")
        self.labels[f"speed{speed}"].get_style_context().add_class("horizontal_togglebuttons_active")
        self.speed = speed

    def check_min_temp(self, widget, method, direction):
        temp = float(self._printer.get_stat(self.current_extruder, 'temperature'))
        target = float(self._printer.get_stat(self.current_extruder, 'target'))
        min_extrude_temp = float(self._printer.config[self.current_extruder].get('min_extrude_temp', 170))
        if temp < min_extrude_temp:
            if target > min_extrude_temp:
                self._screen._send_action(
                    widget, "printer.gcode.script",
                    {"script": f"M109 S{target}"}
                )
        if method == "extrude":
            self.extrude(widget, direction)
        elif method == "load_unload":
            self.load_unload(widget, direction)

    def extrude(self, widget, direction):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.EXTRUDE_REL)
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"G1 E{direction}{self.distance} F{self.speed * 60}"})

    def load_unload(self, widget, direction):
        if direction == "-":
            if not self.unload_filament:
                self._screen.show_popup_message("Macro UNLOAD_FILAMENT not found")
            else:
                self._screen._send_action(widget, "printer.gcode.script",
                                          {"script": f"UNLOAD_FILAMENT SPEED={self.speed * 60}"})
        if direction == "+":
            if not self.load_filament:
                self._screen.show_popup_message("Macro LOAD_FILAMENT not found")
            else:
                self._screen._send_action(widget, "printer.gcode.script",
                                          {"script": f"LOAD_FILAMENT SPEED={self.speed * 60}"})

    def enable_disable_fs(self, switch, gparams, name, x):
        if switch.get_active():
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=1")
            if self._printer.get_stat(x, "filament_detected"):
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
            else:
                self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
        else:
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=0")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")

    def update_temp(self, extruder, temp, target, power):
        if not temp:
            return
        new_label_text = f"{temp or 0:.0f}"
        if target:
            new_label_text += f"/{target:.0f}"
        new_label_text += "°\n"
        if self._show_heater_power and power:
            new_label_text += f" {power * 100:.0f}%"
        find_widget(self.labels[extruder], Gtk.Label).set_text(new_label_text)
