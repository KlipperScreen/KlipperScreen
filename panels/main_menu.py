import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from panels.menu import MenuPanel

from ks_includes.widgets.heatergraph import HeaterGraph
from ks_includes.widgets.keypad import Keypad


def create_panel(*args, **kwargs):
    return MainPanel(*args, **kwargs)


class MainPanel(MenuPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title, items)
        self.graph_retry_timeout = None
        self.left_panel = None
        self.devices = {}
        self.graph_update = None
        self.active_heater = None
        self.h = 1
        self.main_menu = self._gtk.HomogeneousGrid()
        self.main_menu.set_hexpand(True)
        self.main_menu.set_vexpand(True)
        self.graph_retry = 0

        logging.info("### Making MainMenu")

        stats = self._printer.get_printer_status_data()["printer"]
        if stats["temperature_devices"]["count"] > 0 or stats["extruders"]["count"] > 0:
            self._gtk.reset_temp_color()
            self.main_menu.attach(self.create_left_panel(), 0, 0, 1, 1)
        if self._screen.vertical_mode:
            self.labels['menu'] = self.arrangeMenuItems(items, 3, True)
            self.main_menu.attach(self.labels['menu'], 0, 1, 1, 1)
        else:
            self.labels['menu'] = self.arrangeMenuItems(items, 2, True)
            self.main_menu.attach(self.labels['menu'], 1, 0, 1, 1)
        self.content.add(self.main_menu)

    def update_graph_visibility(self):
        if self.left_panel is None or not self._printer.get_temp_store_devices():
            self.graph_retry += 1
            if self.graph_retry < 5:
                if self.graph_retry_timeout is None:
                    self.graph_retry_timeout = GLib.timeout_add_seconds(5, self.update_graph_visibility)
            else:
                logging.debug(f"Could not create graph {self.left_panel} {self._printer.get_temp_store_devices()}")
            return False
        count = 0
        for device in self.devices:
            visible = self._config.get_config().getboolean(f"graph {self._screen.connected_printer}",
                                                           device, fallback=True)
            self.devices[device]['visible'] = visible
            self.labels['da'].set_showing(device, visible)
            if visible:
                count += 1
                self.devices[device]['name'].get_style_context().add_class(self.devices[device]['class'])
                self.devices[device]['name'].get_style_context().remove_class("graph_label_hidden")
            else:
                self.devices[device]['name'].get_style_context().add_class("graph_label_hidden")
                self.devices[device]['name'].get_style_context().remove_class(self.devices[device]['class'])
        if count > 0:
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
        self.graph_retry = 0
        return False

    def activate(self):
        self.update_graph_visibility()
        self._screen.base_panel_show_all()

    def deactivate(self):
        if self.graph_update is not None:
            GLib.source_remove(self.graph_update)
            self.graph_update = None
        if self.graph_retry_timeout is not None:
            GLib.source_remove(self.graph_retry_timeout)
            self.graph_retry_timeout = None
        if self.active_heater is not None:
            self.hide_numpad()

    def add_device(self, device):

        logging.info(f"Adding device: {device}")

        temperature = self._printer.get_dev_stat(device, "temperature")
        if temperature is None:
            return False

        devname = device.split()[1] if len(device.split()) > 1 else device
        # Support for hiding devices by name
        if devname.startswith("_"):
            return False

        if device.startswith("extruder"):
            i = sum(d.startswith('extruder') for d in self.devices)
            image = f"extruder-{i}" if self._printer.extrudercount > 1 else "extruder"
            class_name = f"graph_label_{device}"
            dev_type = "extruder"
        elif device == "heater_bed":
            image = "bed"
            devname = "Heater Bed"
            class_name = "graph_label_heater_bed"
            dev_type = "bed"
        elif device.startswith("heater_generic"):
            self.h = sum("heater_generic" in d for d in self.devices)
            image = "heater"
            class_name = f"graph_label_sensor_{self.h}"
            dev_type = "sensor"
        elif device.startswith("temperature_fan"):
            f = 1 + sum("temperature_fan" in d for d in self.devices)
            image = "fan"
            class_name = f"graph_label_fan_{f}"
            dev_type = "fan"
        elif self._config.get_main_config().getboolean("only_heaters", False):
            return False
        else:
            self.h += sum("sensor" in d for d in self.devices)
            image = "heat-up"
            class_name = f"graph_label_sensor_{self.h}"
            dev_type = "sensor"

        rgb = self._gtk.get_temp_color(dev_type)

        can_target = self._printer.device_has_target(device)
        self.labels['da'].add_object(device, "temperatures", rgb, False, True)
        if can_target:
            self.labels['da'].add_object(device, "targets", rgb, True, False)

        name = self._gtk.Button(image, devname.capitalize().replace("_", " "), None, self.bts, Gtk.PositionType.LEFT, 1)
        name.connect("clicked", self.toggle_visibility, device)
        name.set_alignment(0, .5)
        visible = self._config.get_config().getboolean(f"graph {self._screen.connected_printer}", device, fallback=True)
        if visible:
            name.get_style_context().add_class(class_name)
        else:
            name.get_style_context().add_class("graph_label_hidden")
        self.labels['da'].set_showing(device, visible)

        temp = self._gtk.Button(label="", lines=1)
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

        max_temp = int(float(self._printer.get_config_section(self.active_heater)['max_temp']))
        if temp > max_temp:
            self._screen.show_popup_message(_("Can't set above the maximum:") + f' {max_temp}')
            return
        temp = max(temp, 0)
        name = self.active_heater.split()[1] if len(self.active_heater.split()) > 1 else self.active_heater

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
        self._printer.set_dev_stat(self.active_heater, "target", temp)

    def create_left_panel(self):

        self.labels['devices'] = Gtk.Grid()
        self.labels['devices'].get_style_context().add_class('heater-grid')
        self.labels['devices'].set_vexpand(False)

        name = Gtk.Label(label="")
        temp = Gtk.Label(_("Temp (°C)"))
        temp.get_style_context().add_class("heater-grid-temp")

        self.labels['devices'].attach(name, 0, 0, 1, 1)
        self.labels['devices'].attach(temp, 1, 0, 1, 1)

        self.labels['da'] = HeaterGraph(self._printer, self._gtk.font_size)
        self.labels['da'].set_vexpand(True)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.labels['devices'])

        self.left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.left_panel.add(scroll)

        for d in (self._printer.get_tools() + self._printer.get_heaters()):
            self.add_device(d)

        return self.left_panel

    def hide_numpad(self, widget=None):
        self.devices[self.active_heater]['name'].get_style_context().remove_class("button_active")
        self.active_heater = None

        if self._screen.vertical_mode:
            self.main_menu.remove_row(1)
            self.main_menu.attach(self.labels['menu'], 0, 1, 1, 1)
        else:
            self.main_menu.remove_column(1)
            self.main_menu.attach(self.labels['menu'], 1, 0, 1, 1)
        self.main_menu.show_all()

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        for x in (self._printer.get_tools() + self._printer.get_heaters()):
            self.update_temp(
                x,
                self._printer.get_dev_stat(x, "temperature"),
                self._printer.get_dev_stat(x, "target"),
                self._printer.get_dev_stat(x, "power"),
            )
        return False

    def show_numpad(self, widget, device):

        if self.active_heater is not None:
            self.devices[self.active_heater]['name'].get_style_context().remove_class("button_active")
        self.active_heater = device
        self.devices[self.active_heater]['name'].get_style_context().add_class("button_active")

        if "keypad" not in self.labels:
            self.labels["keypad"] = Keypad(self._screen, self.change_target_temp, self.hide_numpad)
        self.labels["keypad"].clear()

        if self._screen.vertical_mode:
            self.main_menu.remove_row(1)
            self.main_menu.attach(self.labels["keypad"], 0, 1, 1, 1)
        else:
            self.main_menu.remove_column(1)
            self.main_menu.attach(self.labels["keypad"], 1, 0, 1, 1)
        self.main_menu.show_all()

    def update_graph(self):
        self.labels['da'].queue_draw()
        return True
