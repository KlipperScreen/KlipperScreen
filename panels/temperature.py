import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from contextlib import suppress
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.heatergraph import HeaterGraph
from ks_includes.widgets.keypad import Keypad
from ks_includes.KlippyGtk import find_widget


class Panel(ScreenPanel):
    graph_update = None
    active_heater = None

    def __init__(self, screen, title, **kwargs):
        title = title or _("Temperature")
        super().__init__(screen, title)
        self.left_panel = None
        self.devices = {}
        self.popover = Gtk.Popover(position=Gtk.PositionType.BOTTOM)
        self.popover_buttons = {}
        self.long_press = {}
        self.popover_device = None
        self.h = self.f = 0
        self.tempdeltas = ["1", "5", "10", "25"]
        self.tempdelta = self.tempdeltas[-2]
        self.show_preheat = self._printer.state not in ("printing", "paused")
        self.preheat_options = self._screen._config.get_preheat_options()
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        self._gtk.reset_temp_color()
        self.extra_selection = None

        if self._screen.vertical_mode:
            self.grid.attach(self.create_left_panel(), 0, 0, 1, 3)
            self.grid.attach(self.create_right_panel(), 0, 3, 1, 2)
        else:
            self.grid.attach(self.create_left_panel(), 0, 0, 1, 1)
            self.grid.attach(self.create_right_panel(), 1, 0, 1, 1)

        self.content.add(self.grid)

    def create_right_panel(self):
        cooldown = self._gtk.Button(
            "cool-down", _("Cooldown"), "color4", self.bts, Gtk.PositionType.LEFT, 1
        )
        adjust = self._gtk.Button(
            "fine-tune", None, "color3", self.bts * 1.4, Gtk.PositionType.LEFT, 1
        )
        cooldown.connect("clicked", self.set_temperature, "cooldown")
        adjust.connect("clicked", self.switch_preheat_adjust)

        right = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        right.attach(cooldown, 0, 0, 2, 1)
        right.attach(adjust, 2, 0, 1, 1)
        if self.show_preheat:
            right.attach(self.preheat(), 0, 1, 3, 2)
        else:
            right.attach(self.delta_adjust(), 0, 1, 3, 2)
        return right

    def switch_preheat_adjust(self, widget):
        self.show_preheat ^= True
        if self._screen.vertical_mode:
            row = self.grid.get_child_at(0, 3)
            self.grid.remove(row)
            self.grid.attach(self.create_right_panel(), 0, 3, 1, 2)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self.create_right_panel(), 1, 0, 1, 1)
        self.grid.show_all()

    def preheat(self):
        self.labels["preheat_grid"] = Gtk.Grid(
            row_homogeneous=True, column_homogeneous=True
        )
        i = 0
        for option in self.preheat_options:
            if option != "cooldown":
                self.labels[option] = self._gtk.Button(
                    label=option, style=f"color{(i % 4) + 1}"
                )
                self.labels[option].connect("clicked", self.set_temperature, option)
                self.labels["preheat_grid"].attach(
                    self.labels[option], (i % 2), int(i / 2), 1, 1
                )
                i += 1
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels["preheat_grid"])
        return scroll

    def delta_adjust(self):
        # Create buttons for increase and decrease
        self.labels["increase"] = self._gtk.Button("increase", None, "color1")
        self.labels["increase"].connect("clicked", self.change_target_temp_incremental, "+")
        self.labels["decrease"] = self._gtk.Button("decrease", None, "color3")
        self.labels["decrease"].connect("clicked", self.change_target_temp_incremental, "-")

        # Create buttons for temperature deltas
        for i in self.tempdeltas:
            self.labels[f"deg{i}"] = self._gtk.Button(label=i)
            self.labels[f"deg{i}"].connect("clicked", self.change_temp_delta, i)
            ctx = self.labels[f"deg{i}"].get_style_context()
            ctx.add_class("horizontal_togglebuttons")
            if i == self.tempdelta:
                ctx.add_class("horizontal_togglebuttons_active")

        # Create grid for temperature deltas
        tempgrid = Gtk.Grid()
        for j, i in enumerate(self.tempdeltas):
            tempgrid.attach(self.labels[f"deg{i}"], j, 0, 1, 1)

        # Create grid for decrease button, increase button, temperature labels, and grid
        deltagrid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        if self._screen.vertical_mode:
            deltagrid.attach(self.labels["decrease"], 0, 1, 1, 1)
            deltagrid.attach(self.labels["increase"], 1, 1, 1, 1)
            deltagrid.attach(tempgrid, 0, 2, 2, 1)
        else:
            deltagrid.attach(self.labels["decrease"], 0, 1, 1, 3)
            deltagrid.attach(self.labels["increase"], 1, 1, 1, 3)
            deltagrid.attach(Gtk.Label(_("Temperature") + " (°C)"), 0, 4, 2, 1)
            deltagrid.attach(tempgrid, 0, 5, 2, 2)
        return deltagrid

    def change_temp_delta(self, widget, tempdelta):
        logging.info(f"### tempdelta {tempdelta}")
        self.labels[f"deg{self.tempdelta}"].get_style_context().remove_class(
            "horizontal_togglebuttons_active"
        )
        self.labels[f"deg{tempdelta}"].get_style_context().add_class(
            "horizontal_togglebuttons_active"
        )
        self.tempdelta = tempdelta

    def change_target_temp_incremental(self, widget, direction):

        if len(self.active_heaters) == 0:
            self._screen.show_popup_message(_("Nothing selected"))
        else:
            for heater in self.active_heaters:
                target = self._printer.get_stat(heater, "target")
                name = heater.split()[1] if len(heater.split()) > 1 else heater
                if direction == "+":
                    target += int(self.tempdelta)
                    max_temp = int(
                        float(self._printer.get_config_section(heater)["max_temp"])
                    )
                    if target > max_temp:
                        target = max_temp
                        self._screen.show_popup_message(
                            _("Can't set above the maximum:") + f" {target}"
                        )

                else:
                    target -= int(self.tempdelta)
                    target = max(target, 0)
                if heater.startswith("extruder"):
                    self._screen._ws.klippy.set_tool_temp(
                        self._printer.get_tool_number(heater), target
                    )
                elif heater.startswith("heater_bed"):
                    self._screen._ws.klippy.set_bed_temp(target)
                elif heater.startswith("heater_generic "):
                    self._screen._ws.klippy.set_heater_temp(name, target)
                elif heater.startswith("temperature_fan "):
                    self._screen._ws.klippy.set_temp_fan_temp(name, target)
                else:
                    logging.info(f"Unknown heater: {heater}")
                    self._screen.show_popup_message(_("Unknown Heater") + " " + heater)
                logging.info(f"Setting {heater} to {target}")

    def update_graph_visibility(self, force_hide=False):
        count = 0
        for device in self.devices:
            visible = self._config.get_config().getboolean(
                f"graph {self._screen.connected_printer}", device, fallback=True
            )
            self.devices[device]["visible"] = visible
            self.labels["da"].set_showing(device, visible)
            if visible:
                count += 1
                self.devices[device]["name_button"].get_style_context().add_class(
                    "graph_label"
                )
            else:
                self.devices[device]["name_button"].get_style_context().remove_class(
                    "graph_label"
                )
        if count > 0 and not force_hide:
            if self.labels["da"] not in self.left_panel:
                self.left_panel.add(self.labels["da"])
            self.labels["da"].queue_draw()
            self.labels["da"].show()
            if self.graph_update is None:
                # This has a high impact on load
                self.graph_update = GLib.timeout_add_seconds(5, self.update_graph)
        elif self.labels["da"] in self.left_panel:
            self.left_panel.remove(self.labels["da"])
            if self.graph_update is not None:
                GLib.source_remove(self.graph_update)
                self.graph_update = None

    def activate(self):
        if not self._printer.tempstore:
            self._screen.init_tempstore()
        self.update_graph_visibility()
        self.set_selection()

    def set_extra(self, extra=None, **kwargs):
        self.extra_selection = extra

    def set_selection(self):
        selection = []
        if self.extra_selection:
            selection.append(self.extra_selection)
        elif self._printer.state not in ("printing", "paused"):
            selection.extend(self._printer.get_temp_devices())
        elif 'toolhead' in self._printer.data and 'extruder' in self._printer.data['toolhead']:
            current_extruder = self._printer.data['toolhead']['extruder']
            selection.append(current_extruder)

        for heater in self.active_heaters:
            if heater not in selection:
                self.select_heater(None, heater)
        for heater in selection:
            if heater.startswith("temperature_sensor "):
                continue
            name = heater.split()[1] if len(heater.split()) > 1 else heater
            if heater not in self.active_heaters:
                self.select_heater(None, heater)
        self.extra_selection = None

    def deactivate(self):
        if self.graph_update is not None:
            GLib.source_remove(self.graph_update)
            self.graph_update = None
        if self.active_heater is not None:
            self.hide_numpad()

    def select_heater(self, widget, device):
        if (
            self.active_heater is None
            and device in self.devices
            and self._printer.device_has_target(device)
        ):
            if device in self.active_heaters:
                self.active_heaters.pop(self.active_heaters.index(device))
                self.devices[device]["name_button"].get_style_context().remove_class(
                    "button_active"
                )
                logging.info(f"Deselecting {device}")
                return
            self.active_heaters.append(device)
            self.devices[device]["name_button"].get_style_context().add_class(
                "button_active"
            )
            logging.info(f"Selecting {device}")
        return

    def set_temperature(self, widget, setting):
        if len(self.active_heaters) == 0:
            self._screen.show_popup_message(_("Nothing selected"))
        else:
            for heater in self.active_heaters:
                target = None
                max_temp = float(self._printer.get_config_section(heater)["max_temp"])
                name = heater.split()[1] if len(heater.split()) > 1 else heater
                with suppress(KeyError):
                    for i in self.preheat_options[setting]:
                        logging.info(f"{self.preheat_options[setting]}")
                        if i == name:
                            # Assign the specific target if available
                            target = self.preheat_options[setting][name]
                            logging.info(f"name match {name}")
                        elif i == heater:
                            target = self.preheat_options[setting][heater]
                            logging.info(f"heater match {heater}")
                if (
                    target is None
                    and setting == "cooldown"
                    and not heater.startswith("temperature_fan ")
                ):
                    target = 0
                if heater.startswith("extruder"):
                    if self.validate(heater, target, max_temp):
                        self._screen._ws.klippy.set_tool_temp(
                            self._printer.get_tool_number(heater), target
                        )
                elif heater.startswith("heater_bed"):
                    if target is None:
                        with suppress(KeyError):
                            target = self.preheat_options[setting]["bed"]
                    if self.validate(heater, target, max_temp):
                        self._screen._ws.klippy.set_bed_temp(target)
                elif heater.startswith("heater_generic "):
                    if target is None:
                        with suppress(KeyError):
                            target = self.preheat_options[setting]["heater_generic"]
                    if self.validate(heater, target, max_temp):
                        self._screen._ws.klippy.set_heater_temp(name, target)
                elif heater.startswith("temperature_fan "):
                    if target is None:
                        with suppress(KeyError):
                            target = self.preheat_options[setting]["temperature_fan"]
                    if self.validate(heater, target, max_temp):
                        self._screen._ws.klippy.set_temp_fan_temp(name, target)
            # This small delay is needed to properly update the target if the user configured something above
            # and then changed the target again using preheat gcode
            GLib.timeout_add(250, self.preheat_gcode, widget, setting)

    def validate(self, heater, target=None, max_temp=None):
        if target is not None and max_temp is not None:
            if 0 <= target <= max_temp:
                return True
            elif target > max_temp:
                self._screen.show_popup_message(
                    _("Can't set above the maximum:") + f" {max_temp}"
                )
                return False
        logging.debug(f"Invalid {heater} Target:{target}/{max_temp}")
        return False

    def preheat_gcode(self, widget, setting):
        with suppress(KeyError):
            script = {"script": self.preheat_options[setting]["gcode"]}
            self._screen._send_action(widget, "printer.gcode.script", script)
        return False

    def add_device(self, device):

        logging.info(f"Adding device: {device}")

        temperature = self._printer.get_stat(device, "temperature")
        if temperature is None:
            return False

        devname = device.split()[1] if len(device.split()) > 1 else device
        # Support for hiding devices by name
        if devname.startswith("_"):
            return False

        if device.startswith("extruder"):
            if self._printer.extrudercount > 1:
                image = f"extruder-{device[8:]}" if device[8:] else "extruder-0"
            else:
                image = "extruder"
            class_name = f"graph_label_{device}"
            dev_type = "extruder"
        elif device == "heater_bed":
            image = "bed"
            devname = "Heater Bed"
            class_name = "graph_label_heater_bed"
            dev_type = "bed"
        elif device.startswith("heater_generic"):
            self.h += 1
            image = "heater"
            class_name = f"graph_label_sensor_{self.h}"
            dev_type = "sensor"
        elif device.startswith("temperature_fan"):
            self.f += 1
            image = "fan"
            class_name = f"graph_label_fan_{self.f}"
            dev_type = "fan"
        elif self._config.get_main_config().getboolean("only_heaters", False):
            return False
        else:
            self.h += 1
            image = "heat-up"
            class_name = f"graph_label_sensor_{self.h}"
            dev_type = "sensor"

        rgb = self._gtk.get_temp_color(dev_type)

        name = self._gtk.Button(
            image, self.prettify(devname), None, self.bts, Gtk.PositionType.LEFT, 1
        )
        name.set_alignment(0, 0.5)
        name.get_style_context().add_class(class_name)
        visible = self._config.get_config().getboolean(
            f"graph {self._screen.connected_printer}", device, fallback=True
        )
        if visible:
            name.get_style_context().add_class("graph_label")

        self.labels["da"].add_object(device, "temperatures", rgb, False, False)
        temp = self._gtk.Button(label="", lines=1)
        find_widget(temp, Gtk.Label).set_ellipsize(False)

        if self._printer.device_has_target(device):
            temp.connect("clicked", self.show_numpad, device)
            self.labels["da"].add_object(device, "targets", rgb, False, True)
            name.connect("button-press-event", self.name_pressed, device)
            self.long_press[device] = Gtk.GestureLongPress.new(name)
            self.long_press[device].connect(
                "pressed", self.name_long_press, name, device
            )
            self.long_press[device].connect(
                "cancelled", self.name_long_press_cancelled, name, device
            )
        else:
            name.connect("clicked", self.toggle_visibility, device)
        if self._show_heater_power and self._printer.device_has_power(device):
            self.labels["da"].add_object(device, "powers", rgb, True, False)
        self.labels["da"].set_showing(device, visible)

        self.devices[device] = {
            "class": class_name,
            "name_button": name,
            "temp": temp,
            "visible": visible,
        }

        devices = sorted(self.devices)
        pos = devices.index(device) + 1

        self.labels["devices"].insert_row(pos)
        self.labels["devices"].attach(name, 0, pos, 1, 1)
        self.labels["devices"].attach(temp, 1, pos, 1, 1)
        self.labels["devices"].show_all()
        return True

    def name_pressed(self, widget, event, device):
        self.popover_device = device
        if event.button == 3:
            self.popover_popup(widget, device)

    def name_long_press_cancelled(self, gesture_long_press, widget, device):
        if self.active_heater:
            self.show_numpad(widget, device)
        else:
            self.select_heater(widget, device)

    def name_long_press(self, gesture_long_press, x, y, widget, device):
        self.popover_device = device
        self.popover_popup(widget, device)

    def toggle_visibility(self, widget, device=None):
        if device is None:
            device = self.popover_device
        self.devices[device]["visible"] ^= True
        logging.info(f"Graph show {self.devices[device]['visible']}: {device}")

        section = f"graph {self._screen.connected_printer}"
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, f"{device}", f"{self.devices[device]['visible']}")
        self._config.save_user_config_options()

        self.update_graph_visibility()
        if self._printer.device_has_target(device):
            self.popover_populate_menu()
            self.popover.show_all()

    def change_target_temp(self, temp):
        name = (
            self.active_heater.split()[1]
            if len(self.active_heater.split()) > 1
            else self.active_heater
        )
        temp = self.verify_max_temp(temp)
        if temp is False:
            return

        if self.active_heater.startswith("extruder"):
            self._screen._ws.klippy.set_tool_temp(
                self._printer.get_tool_number(self.active_heater), temp
            )
        elif self.active_heater == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(temp)
        elif self.active_heater.startswith("heater_generic "):
            self._screen._ws.klippy.set_heater_temp(name, temp)
        elif self.active_heater.startswith("temperature_fan "):
            self._screen._ws.klippy.set_temp_fan_temp(name, temp)
        else:
            logging.info(f"Unknown heater: {self.active_heater}")
            self._screen.show_popup_message(
                _("Unknown Heater") + " " + self.active_heater
            )

    def verify_max_temp(self, temp):
        temp = int(temp)
        max_temp = int(
            float(self._printer.get_config_section(self.active_heater)["max_temp"])
        )
        logging.debug(f"{temp}/{max_temp}")
        if temp > max_temp:
            self._screen.show_popup_message(
                _("Can't set above the maximum:") + f" {max_temp}"
            )
            return False
        return max(temp, 0)

    def pid_calibrate(self, temp):
        heater = self.active_heater.split(' ', maxsplit=1)[-1]
        if self.verify_max_temp(temp):
            script = {
                "script": f"PID_CALIBRATE HEATER={heater} TARGET={temp}"
            }
            self._screen._confirm_send_action(
                None,
                _("Initiate a PID calibration for:")
                + f" {heater} @ {temp} ºC"
                + "\n\n"
                + _("It may take more than 5 minutes depending on the heater power."),
                "printer.gcode.script",
                script,
            )

    def create_left_panel(self):

        self.labels["devices"] = Gtk.Grid(vexpand=False)
        self.labels["devices"].get_style_context().add_class("heater-grid")

        name = Gtk.Label()
        temp = Gtk.Label(_("Temp (°C)"))

        self.labels["devices"].attach(name, 0, 0, 1, 1)
        self.labels["devices"].attach(temp, 1, 0, 1, 1)

        self.labels["da"] = HeaterGraph(
            self._screen, self._printer, self._gtk.font_size
        )

        scroll = self._gtk.ScrolledWindow(steppers=False)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.get_style_context().add_class("heater-list")
        scroll.add(self.labels["devices"])

        self.left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.left_panel.add(scroll)

        self.popover_buttons = {
            "set_temp": self._gtk.Button(label=_("Set Temp")),
            "graph_show": self._gtk.Button(label=_("Show")),
        }
        self.popover_buttons["set_temp"].connect("clicked", self.show_numpad)
        self.popover_buttons["set_temp"].set_no_show_all(True)
        self.popover_buttons["graph_show"].connect("clicked", self.toggle_visibility)

        pobox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pobox.pack_start(self.popover_buttons["graph_show"], True, True, 5)
        pobox.pack_start(self.popover_buttons["set_temp"], True, True, 5)
        self.popover.add(pobox)
        self.popover.connect("closed", self.popover_closed)

        for d in self._printer.get_temp_devices():
            self.add_device(d)

        return self.left_panel

    def hide_numpad(self, widget=None):
        self.devices[self.active_heater][
            "name_button"
        ].get_style_context().remove_class("button_active")
        self.active_heater = None

        for d in self.active_heaters:
            self.devices[d]["name_button"].get_style_context().add_class(
                "button_active"
            )

        if self._screen.vertical_mode:
            if not self._gtk.ultra_tall:
                self.update_graph_visibility(force_hide=False)
            top = self.grid.get_child_at(0, 0)
            bottom = self.grid.get_child_at(0, 2)
            self.grid.remove(top)
            self.grid.remove(bottom)
            self.grid.attach(top, 0, 0, 1, 3)
            self.grid.attach(self.create_right_panel(), 0, 3, 1, 2)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self.create_right_panel(), 1, 0, 1, 1)
        self.grid.show_all()

    def popover_closed(self, widget):
        self.popover_device = None

    def popover_popup(self, widget, device):
        self.popover_device = device
        self.popover.set_relative_to(widget)
        self.popover_populate_menu()
        self.popover.show_all()

    def popover_populate_menu(self):
        if self.labels["da"].is_showing(self.popover_device):
            self.popover_buttons["graph_show"].set_label(_("Hide"))
        else:
            self.popover_buttons["graph_show"].set_label(_("Show"))
        if self._printer.device_has_target(self.popover_device):
            self.popover_buttons["set_temp"].show()
        else:
            self.popover_buttons["set_temp"].hide()

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        for x in self._printer.get_temp_devices():
            if x in data:
                self.update_temp(
                    x,
                    self._printer.get_stat(x, "temperature"),
                    self._printer.get_stat(x, "target"),
                    self._printer.get_stat(x, "power"),
                )

    def show_numpad(self, widget, device=None):
        for d in self.active_heaters:
            self.devices[d]["name_button"].get_style_context().remove_class(
                "button_active"
            )
        self.active_heater = self.popover_device if device is None else device
        self.devices[self.active_heater]["name_button"].get_style_context().add_class(
            "button_active"
        )

        if "keypad" not in self.labels:
            self.labels["keypad"] = Keypad(
                self._screen,
                self.change_target_temp,
                self.pid_calibrate,
                self.hide_numpad,
            )
        can_pid = (
            self._printer.state not in ("printing", "paused")
            and self._screen.printer.config[self.active_heater]["control"] == "pid"
        )
        self.labels["keypad"].show_pid(can_pid)
        self.labels["keypad"].clear()

        if self._screen.vertical_mode:
            if not self._gtk.ultra_tall:
                self.update_graph_visibility(force_hide=True)
            top = self.grid.get_child_at(0, 0)
            bottom = self.grid.get_child_at(0, 3)
            self.grid.remove(top)
            self.grid.remove(bottom)
            self.grid.attach(top, 0, 0, 1, 2)
            self.grid.attach(self.labels["keypad"], 0, 2, 1, 2)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self.labels["keypad"], 1, 0, 1, 1)
        self.grid.show_all()

        self.popover.popdown()

    def update_graph(self):
        self.labels["da"].queue_draw()
        return True
