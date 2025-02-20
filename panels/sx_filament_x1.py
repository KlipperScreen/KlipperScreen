import logging
import re
import configparser
import io
from time import sleep

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.autogrid import AutoGrid
from ks_includes.KlippyGtk import find_widget
from ks_includes.printer import Printer
from ks_includes.config import KlipperScreenConfig
from ks_includes.KlippyRest import KlippyRest

class Panel(ScreenPanel):

    def __init__(self, screen, title):
        self._printer: Printer
        self._config: KlipperScreenConfig
        self.apiclient: KlippyRest = screen.apiclient

        title = title or _("Filament")
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
            'spoolman': self._gtk.Button("spoolman", "Spoolman", "color3"),
        }
        self.buttons['extrude'].connect("clicked", self.check_min_temp, "extrude", "+")
        self.buttons['load'].connect("clicked", self.check_min_temp, "load_unload", "+")
        self.buttons['unload'].connect("clicked", self.check_min_temp, "load_unload", "-")
        self.buttons['retract'].connect("clicked", self.check_min_temp, "extrude", "-")
        self.buttons['spoolman'].connect("clicked", self.menu_item_clicked, {
            "panel": "spoolman"
        })

        xbox = Gtk.Box(homogeneous=True)
        limit = 4
        i = 0
        extruder_buttons = []
        self.labels = {}
        self.extruder_grids = {}
        self.nozzle_button = self._gtk.Button("extrude", _("Nozzle"), "color4")
        self.nozzle_button.connect("clicked", self.open_nozzle_panel, "extruder")
        xbox.add(self.nozzle_button)
        for extruder in self._printer.get_tools():
            n = self._printer.get_tool_number(extruder)
            self.labels[extruder] = self._gtk.Button(f"extruder-{n}", f"T{n}")
            self.labels[extruder].connect("clicked", self.change_extruder, extruder)
            if extruder == self.current_extruder:
                self.labels[extruder].get_style_context().add_class("button_active")
            extruder_grid = Gtk.Grid()
            extruder_grid.attach(self.labels[extruder], 0, 0, 2, 1)

            self.extruder_grids[extruder] = {}
            self.extruder_grids[extruder]["grid"] = extruder_grid

            materials_button = self._gtk.Button("filament", _("Materials"), "color4")
            materials_button.connect("clicked", self.open_materials_panel, extruder)
            self.extruder_grids[extruder]["materials_button"] = materials_button

            extruder_grid.attach(materials_button, 0, 1, 2, 1)
            
            xbox.add(extruder_grid)
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

        grid = Gtk.Grid(column_homogeneous=True)
        grid.attach(xbox, 0, 0, 4, 1)

        if self._screen.vertical_mode:
            grid.attach(self.buttons['extrude'], 0, 1, 2, 1)
            grid.attach(self.buttons['retract'], 2, 1, 2, 1)
            grid.attach(self.buttons['load'], 0, 2, 2, 1)
            grid.attach(self.buttons['unload'], 2, 2, 2, 1)
            settings_box = Gtk.Box(homogeneous=True)
            grid.attach(settings_box, 0, 3, 4, 1)
            grid.attach(distbox, 0, 4, 4, 1)
            grid.attach(speedbox, 0, 5, 4, 1)
        else:
            grid.attach(self.buttons['extrude'], 0, 2, 1, 1)
            grid.attach(self.buttons['load'], 1, 2, 1, 1)
            grid.attach(self.buttons['unload'], 2, 2, 1, 1)
            grid.attach(self.buttons['retract'], 3, 2, 1, 1)
            grid.attach(distbox, 0, 3, 2, 1)
            grid.attach(speedbox, 2, 3, 2, 1)

        self.menu = ['extrude_menu']
        self.labels['extrude_menu'] = grid
        self.content.add(self.labels['extrude_menu'])

    def open_materials_panel(self, widget, extruder):
        # HACK: Do this to ensure it is done in the right sequence
        self.delete_panel("sx_materials")
        sleep(1)
        self.change_config_extruder(extruder)
        self.menu_item_clicked(None, { "panel": "sx_materials" })

    def open_nozzle_panel(self, widget, extruder):
        # HACK: Do this to ensure it is done in the right sequence
        self.change_config_extruder(extruder)
        self.menu_item_clicked(None, { "panel": "sx_nozzle" })

    def enable_buttons(self, enable):
        for button in self.buttons:
            if button in ("spoolman"):
                continue
            self.buttons[button].set_sensitive(enable)

    def activate(self):
        self.enable_buttons(self._printer.state in ("ready", "paused"))

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
                current_extruder = self._printer.get_stat("toolhead", "extruder")
                material = self._config.materials[current_extruder]
                nozzle = self._config.nozzles[current_extruder]
                load_filament = f"LOAD_FILAMENT M='{material}' NZ='{nozzle}'"
                self._screen._send_action(widget, "printer.gcode.script",
                                          {"script": load_filament})

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

    def change_config_extruder(self, extruder: str):
        self._config.extruder = extruder
        # Try to read nozzle variable
        try:
            variables_content = self.apiclient.send_request("/server/files/config/variables.cfg", json=False)
            variables_str = variables_content.decode("utf-8")
            variables_file = io.StringIO(variables_str)

            config = configparser.ConfigParser()
            config.read_file(variables_file)
            nozzle = config.get("Variables", "nozzle")
            self._config.nozzle = nozzle.replace("'", "")
            logging.info(self._config.nozzle)
        except Exception as e:
            # nozzle variable not found
            logging.error(e)

    def delete_panel(self, panel_name):
        if panel_name in self._screen.panels:
            del self._screen.panels[panel_name]

    def process_update(self, action, data):
        # if action == "notify_gcode_response":
        #     if "action:cancel" in data or "action:paused" in data:
        #         self.enable_buttons(True)
        #     elif "action:resumed" in data:
        #         self.enable_buttons(False)
        #     return
        # if action != "notify_status_update":
        #     return
        # for x in self._printer.get_tools():
        #     if x in data:
        #         self.update_temp(
        #             x,
        #             self._printer.get_stat(x, "temperature"),
        #             self._printer.get_stat(x, "target"),
        #             self._printer.get_stat(x, "power"),
        #         )
        # if "current_extruder" in self.labels:
        #     self.labels["current_extruder"].set_label(self.labels[self.current_extruder].get_label())

        # if ("toolhead" in data and "extruder" in data["toolhead"] and
        #         data["toolhead"]["extruder"] != self.current_extruder):
        #     for extruder in self._printer.get_tools():
        #         self.labels[extruder].get_style_context().remove_class("button_active")
        #     self.current_extruder = data["toolhead"]["extruder"]
        #     self.labels[self.current_extruder].get_style_context().add_class("button_active")
        #     if "current_extruder" in self.labels:
        #         n = self._printer.get_tool_number(self.current_extruder)
        #         self.labels["current_extruder"].set_image(self._gtk.Image(f"extruder-{n}"))
        try:
            variables_content = self.apiclient.send_request("/server/files/config/variables.cfg", json=False)
            variables_str = variables_content.decode("utf-8")
            variables_file = io.StringIO(variables_str)
            
            config = configparser.ConfigParser()
            config.read_file(variables_file)
            if config.has_section("Variables"):
                variables = config["Variables"].keys()
            else:
                return
            if "material_ext0" in variables:
                # Change material label
                material = config.get("Variables", "material_ext0")
                material = material.replace("'", "")
                self.extruder_grids["extruder"]["materials_button"].set_label(material)

                # Save material variable
                self._config.materials["extruder"] = material
            if "material_ext1" in variables:
                # Change nozzle label
                material = config.get("Variables", "material_ext1")
                material = material.replace("'", "")
                self.extruder_grids["extruder_stepper extruder1"]["materials_button"].set_label(material)

                self._config.materials["extruder_stepper extruder1"] = material
            if "nozzle" in variables:
                # Change nozzle label
                nozzle = config.get("Variables", "nozzle")
                nozzle = nozzle.replace("'", "")
                self.nozzle_button.set_label(nozzle)

                # Save nozzle variable
                self._config.nozzles["extruder"] = nozzle
        except:
            pass