import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return ExtrudePanel(*args)


class ExtrudePanel(ScreenPanel):

    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        self.speeds = ['1', '2', '5', '25']
        self.speed = 1
        self.distances = ['5', '10', '15', '25']
        self.distance = 5
        macros = self._screen.printer.get_gcode_macros()
        self.load_filament = any("LOAD_FILAMENT" in macro.upper() for macro in macros)
        self.unload_filament = any("UNLOAD_FILAMENT" in macro.upper() for macro in macros)

    def initialize(self, panel_name):
        self.labels['extrude'] = self._gtk.ButtonImage("extrude", _("Extrude"), "color4")
        self.labels['extrude'].connect("clicked", self.extrude, "+")
        self.labels['load'] = self._gtk.ButtonImage("arrow-down", _("Load"), "color3")

        self.labels['load'].connect("clicked", self.load_unload, "+")
        self.labels['unload'] = self._gtk.ButtonImage("arrow-up", _("Unload"), "color2")

        self.labels['unload'].connect("clicked", self.load_unload, "-")
        self.labels['retract'] = self._gtk.ButtonImage("retract", _("Retract"), "color1")
        self.labels['retract'].connect("clicked", self.extrude, "-")
        self.labels['temperature'] = self._gtk.ButtonImage("heat-up", _("Temperature"), "color4")
        self.labels['temperature'].connect("clicked", self.menu_item_clicked, "temperature", {
            "name": "Temperature",
            "panel": "temperature"
        })

        extgrid = self._gtk.HomogeneousGrid()
        limit = 5
        i = 0
        for extruder in self._printer.get_tools():
            if self._printer.extrudercount > 1:
                self.labels[extruder] = self._gtk.ButtonImage(f"extruder-{i}",
                                                              f"T{self._printer.get_tool_number(extruder)}")
            else:
                self.labels[extruder] = self._gtk.ButtonImage("extruder", "")
            self.labels[extruder].connect("clicked", self.change_extruder, extruder)
            if extruder == self.current_extruder:
                self.labels[extruder].get_style_context().add_class("button_active")
            if i < limit:
                extgrid.attach(self.labels[extruder], i, 0, 1, 1)
                i += 1
        if i < (limit - 1):
            extgrid.attach(self.labels['temperature'], i + 1, 0, 1, 1)

        distgrid = Gtk.Grid()
        for j, i in enumerate(self.distances):
            self.labels[f"dist{i}"] = self._gtk.ToggleButton(i)
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
            if i == "5":
                ctx.add_class("distbutton_active")
            distgrid.attach(self.labels[f"dist{i}"], j, 0, 1, 1)
        self.labels["dist5"].set_active(True)

        speedgrid = Gtk.Grid()
        for j, i in enumerate(self.speeds):
            self.labels[f"speed{i}"] = self._gtk.ToggleButton(_(i))
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
            if i == "2":
                ctx.add_class("distbutton_active")
            speedgrid.attach(self.labels[f"speed{i}"], j, 0, 1, 1)
        self.labels["speed2"].set_active(True)

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
                self.labels[x]['switch'].set_property("width-request", round(self._gtk.get_font_size() * 2))
                self.labels[x]['switch'].set_property("height-request", round(self._gtk.get_font_size()))
                self.labels[x]['switch'].connect("notify::active", self.enable_disable_fs, name, x)
                self.labels[x]['box'].pack_start(self.labels[x]['label'], True, True, 5)
                self.labels[x]['box'].pack_start(self.labels[x]['switch'], False, False, 5)
                self.labels[x]['box'].get_style_context().add_class("filament_sensor")
                self.labels[x]['box'].set_hexpand(True)
                if self._printer.get_dev_stat(x, "filament_detected"):
                    self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
                else:
                    self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
                sensors.attach(self.labels[x]['box'], s, 0, 1, 1)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.attach(extgrid, 0, 0, 4, 1)

        if self._screen.vertical_mode:
            grid.attach(self.labels['extrude'], 0, 1, 2, 1)
            grid.attach(self.labels['retract'], 2, 1, 2, 1)
            grid.attach(self.labels['load'], 0, 2, 2, 1)
            grid.attach(self.labels['unload'], 2, 2, 2, 1)
            grid.attach(distbox, 0, 3, 4, 1)
            grid.attach(speedbox, 0, 4, 4, 1)
            grid.attach(sensors, 0, 5, 4, 1)
        else:
            grid.attach(self.labels['extrude'], 0, 2, 1, 1)
            grid.attach(self.labels['load'], 1, 2, 1, 1)
            grid.attach(self.labels['unload'], 2, 2, 1, 1)
            grid.attach(self.labels['retract'], 3, 2, 1, 1)
            grid.attach(distbox, 0, 3, 2, 1)
            grid.attach(speedbox, 2, 3, 2, 1)
            grid.attach(sensors, 0, 4, 4, 1)

        self.content.add(grid)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for x in self._printer.get_tools():
            self.update_temp(
                x,
                self._printer.get_dev_stat(x, "temperature"),
                self._printer.get_dev_stat(x, "target")
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
                    logging.info(f"{x} Enabled: {data[x]['enabled']}")
                if 'filament_detected' in data[x]:
                    self._printer.set_dev_stat(x, "filament_detected", data[x]['filament_detected'])
                    if data[x]['filament_detected']:
                        self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
                        self.labels[x]['box'].get_style_context().add_class("filament_sensor_detected")
                    else:
                        self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")
                        self.labels[x]['box'].get_style_context().add_class("filament_sensor_empty")
                    logging.info(f"{x}: Filament detected: {data[x]['filament_detected']}")

    def change_distance(self, widget, distance):
        if self.distance == distance:
            return
        logging.info(f"### Distance {distance}")

        ctx = self.labels[f"dist{self.distance}"].get_style_context()
        ctx.remove_class("distbutton_active")

        self.distance = distance
        ctx = self.labels[f"dist{self.distance}"].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.distances:
            if i == self.distance:
                continue
            self.labels[f"dist{i}"].set_active(False)

    def change_extruder(self, widget, extruder):
        logging.info(f"Changing extruder to {extruder}")
        for tool in self._printer.get_tools():
            self.labels[tool].get_style_context().remove_class("button_active")
        self.labels[extruder].get_style_context().add_class("button_active")

        self._screen._ws.klippy.gcode_script(f"T{self._printer.get_tool_number(extruder)}")

    def change_speed(self, widget, speed):
        if self.speed == speed:
            return
        logging.info(f"### Speed {speed}")

        self.labels[f"speed{self.speed}"].get_style_context().remove_class("distbutton_active")

        self.speed = speed
        self.labels[f"speed{self.speed}"].get_style_context().add_class("distbutton_active")
        for i in self.speeds:
            if i == self.speed:
                continue
            self.labels[f"speed{i}"].set_active(False)

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
        else:
            self._printer.set_dev_stat(x, "enabled", False)
            self._screen._ws.klippy.gcode_script(f"SET_FILAMENT_SENSOR SENSOR={name} ENABLE=0")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_empty")
            self.labels[x]['box'].get_style_context().remove_class("filament_sensor_detected")

    def update_temp(self, dev, temp, target):
        if dev in self.labels and temp is not None:
            if target > 0:
                self.labels[dev].set_label(f"{temp:.1f}°C\n({target:.0f})")
            else:
                self.labels[dev].set_label(f"{temp:.1f}°C")
