import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from panels.menu import Panel as MenuPanel
from ks_includes.widgets.heatergraph import HeaterGraph
from ks_includes.widgets.keypad import Keypad
from ks_includes.KlippyGtk import find_widget


class Panel(MenuPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title, items)
        self.left_panel = None
        self.devices = {}
        self.graph_update = None
        self.active_heater = None
        self.h = self.f = 0
        self.main_menu = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, hexpand=True, vexpand=True)
        scroll = self._gtk.ScrolledWindow()
        self.numpad_visible = False

        logging.info("### Making MainMenu")

        stats = self._printer.get_printer_status_data()["printer"]
        if stats["temperature_devices"]["count"] > 0 or stats["extruders"]["count"] > 0:
            self._gtk.reset_temp_color()
        if self._screen.vertical_mode:
            self.main_menu.attach(self.create_left_panel(), 0, 0, 1, 3)
            self.labels['menu'] = self.arrangeMenuItems(items, 3, True)
            scroll.add(self.labels['menu'])
            self.main_menu.attach(scroll, 0, 3, 1, 2)
        else:
            self.main_menu.attach(self.create_left_panel(), 0, 0, 1, 1)
            self.labels['menu'] = self.arrangeMenuItems(items, 2, True)
            scroll.add(self.labels['menu'])
            self.main_menu.attach(scroll, 1, 0, 1, 1)
        self.content.add(self.main_menu)

    def update_graph_visibility(self, force_hide=False):
        if self.left_panel is None:
            logging.info("No left panel")
            return
        count = 0
        for device in self.devices:
            visible = self._config.get_config().getboolean(f"graph {self._screen.connected_printer}",
                                                           device, fallback=True)
            self.devices[device]['visible'] = visible
            self.labels['da'].set_showing(device, visible)
            if visible:
                count += 1
                self.devices[device]['name'].get_style_context().add_class("graph_label")
            else:
                self.devices[device]['name'].get_style_context().remove_class("graph_label")
        if count > 0 and not force_hide:
            if self.labels['da'] not in self.left_panel:
                self.left_panel.add(self.labels['da'])
            self.labels['da'].queue_draw()
            self.labels['da'].show()
            if self.graph_update is None:
                # This has a high impact on load
                self.graph_update = GLib.timeout_add_seconds(5, self.update_graph)
        elif self.labels['da'] in self.left_panel:
            self.left_panel.remove(self.labels['da'])
            if self.graph_update is not None:
                GLib.source_remove(self.graph_update)
                self.graph_update = None
        return False

    def activate(self):
        if not self._printer.tempstore:
            self._screen.init_tempstore()
        self.update_graph_visibility()

    def deactivate(self):
        if self.graph_update is not None:
            GLib.source_remove(self.graph_update)
            self.graph_update = None
        if self.active_heater is not None:
            self.hide_numpad()

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

        can_target = self._printer.device_has_target(device)
        self.labels['da'].add_object(device, "temperatures", rgb, False, False)
        if can_target:
            self.labels['da'].add_object(device, "targets", rgb, False, True)
        if self._show_heater_power and self._printer.device_has_power(device):
            self.labels['da'].add_object(device, "powers", rgb, True, False)

        name = self._gtk.Button(image, self.prettify(devname), None, self.bts, Gtk.PositionType.LEFT, 1)
        name.connect("clicked", self.toggle_visibility, device)
        name.set_alignment(0, .5)
        name.get_style_context().add_class(class_name)
        visible = self._config.get_config().getboolean(f"graph {self._screen.connected_printer}", device, fallback=True)
        if visible:
            name.get_style_context().add_class("graph_label")
        self.labels['da'].set_showing(device, visible)

        temp = self._gtk.Button(label="", lines=1)
        find_widget(temp, Gtk.Label).set_ellipsize(False)
        if can_target:
            temp.connect("clicked", self.show_numpad, device)

        self.devices[device] = {
            "class": class_name,
            "name": name,
            "temp": temp,
            "can_target": can_target,
            "visible": visible
        }

        devices = sorted(self.devices)
        pos = devices.index(device) + 1

        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(name, 0, pos, 1, 1)
        self.labels['devices'].attach(temp, 1, pos, 1, 1)
        self.labels['devices'].show_all()
        return True

    def toggle_visibility(self, widget, device):
        self.devices[device]['visible'] ^= True
        logging.info(f"Graph show {self.devices[device]['visible']}: {device}")

        section = f"graph {self._screen.connected_printer}"
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, f"{device}", f"{self.devices[device]['visible']}")
        self._config.save_user_config_options()

        self.update_graph_visibility()

    def change_target_temp(self, temp):
        name = self.active_heater.split()[1] if len(self.active_heater.split()) > 1 else self.active_heater
        temp = self.verify_max_temp(temp)
        if temp is False:
            return

        if self.active_heater.startswith('extruder'):
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(self.active_heater), temp)
        elif self.active_heater == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(temp)
        elif self.active_heater.startswith('heater_generic '):
            self._screen._ws.klippy.set_heater_temp(name, temp)
        elif self.active_heater.startswith('temperature_fan '):
            self._screen._ws.klippy.set_temp_fan_temp(name, temp)
        else:
            logging.info(f"Unknown heater: {self.active_heater}")
            self._screen.show_popup_message(_("Unknown Heater") + " " + self.active_heater)

    def verify_max_temp(self, temp):
        temp = int(temp)
        max_temp = int(float(self._printer.get_config_section(self.active_heater)['max_temp']))
        logging.debug(f"{temp}/{max_temp}")
        if temp > max_temp:
            self._screen.show_popup_message(_("Can't set above the maximum:") + f' {max_temp}')
            return False
        return max(temp, 0)

    def pid_calibrate(self, temp):
        heater = self.active_heater.split(' ', maxsplit=1)[-1]
        if self.verify_max_temp(temp):
            script = {"script": f"PID_CALIBRATE HEATER={heater} TARGET={temp}"}
            self._screen._confirm_send_action(
                None,
                _("Initiate a PID calibration for:")
                + f" {heater} @ {temp} ºC"
                + "\n\n"
                + _("It may take more than 5 minutes depending on the heater power."),
                "printer.gcode.script",
                script
            )

    def create_left_panel(self):

        self.labels['devices'] = Gtk.Grid(vexpand=False)
        self.labels['devices'].get_style_context().add_class('heater-grid')

        name = Gtk.Label()
        temp = Gtk.Label(label=_("Temp (°C)"))

        self.labels['devices'].attach(name, 0, 0, 1, 1)
        self.labels['devices'].attach(temp, 1, 0, 1, 1)

        self.labels['da'] = HeaterGraph(self._screen, self._printer, self._gtk.font_size)

        scroll = self._gtk.ScrolledWindow(steppers=False)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.get_style_context().add_class('heater-list')
        scroll.add(self.labels['devices'])

        self.left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.left_panel.add(scroll)

        for d in self._printer.get_temp_devices():
            self.add_device(d)

        return self.left_panel

    def hide_numpad(self, widget=None):
        self.devices[self.active_heater]['name'].get_style_context().remove_class("button_active")
        self.active_heater = None

        if self._screen.vertical_mode:
            if not self._gtk.ultra_tall:
                self.update_graph_visibility(force_hide=False)
            top = self.main_menu.get_child_at(0, 0)
            bottom = self.main_menu.get_child_at(0, 2)
            self.main_menu.remove(top)
            self.main_menu.remove(bottom)
            self.main_menu.attach(top, 0, 0, 1, 3)
            self.main_menu.attach(self.labels["menu"], 0, 3, 1, 2)
        else:
            self.main_menu.remove_column(1)
            self.main_menu.attach(self.labels["menu"], 1, 0, 1, 1)
        self.main_menu.show_all()
        self.numpad_visible = False
        self._screen.base_panel.set_control_sensitive(False, control='back')

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

    def show_numpad(self, widget, device):

        if self.active_heater is not None:
            self.devices[self.active_heater]['name'].get_style_context().remove_class("button_active")
        self.active_heater = device
        self.devices[self.active_heater]['name'].get_style_context().add_class("button_active")

        if "keypad" not in self.labels:
            self.labels["keypad"] = Keypad(self._screen, self.change_target_temp, self.pid_calibrate, self.hide_numpad)
        can_pid = self._printer.state not in ("printing", "paused") \
            and self._screen.printer.config[self.active_heater]['control'] == 'pid'
        self.labels["keypad"].show_pid(can_pid)
        self.labels["keypad"].clear()

        if self._screen.vertical_mode:
            if not self._gtk.ultra_tall:
                self.update_graph_visibility(force_hide=True)
            top = self.main_menu.get_child_at(0, 0)
            bottom = self.main_menu.get_child_at(0, 3)
            self.main_menu.remove(top)
            self.main_menu.remove(bottom)
            self.main_menu.attach(top, 0, 0, 1, 2)
            self.main_menu.attach(self.labels["keypad"], 0, 2, 1, 2)
        else:
            self.main_menu.remove_column(1)
            self.main_menu.attach(self.labels["keypad"], 1, 0, 1, 1)
        self.main_menu.show_all()
        self.numpad_visible = True
        self._screen.base_panel.set_control_sensitive(True, control='back')

    def update_graph(self):
        self.labels['da'].queue_draw()
        return True

    def back(self):
        if self.numpad_visible:
            self.hide_numpad()
            return True
        return False
