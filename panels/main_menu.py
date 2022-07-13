import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from panels.menu import MenuPanel

from ks_includes.widgets.graph import HeaterGraph
from ks_includes.widgets.keypad import Keypad


def create_panel(*args):
    return MainPanel(*args)


class MainPanel(MenuPanel):
    def __init__(self, screen, title, back=False):
        super().__init__(screen, title, False)
        self.popover_device = None
        self.items = None
        self.grid = self._gtk.HomogeneousGrid()
        self.grid.set_hexpand(True)
        self.grid.set_vexpand(True)
        self.devices = {}
        self.graph_update = None
        self.active_heater = None
        self.h = 1

    def initialize(self, panel_name, items, extrudercount):
        logging.info("### Making MainMenu")

        self.items = items
        self.create_menu_items()
        self._gtk.reset_temp_color()

        leftpanel = self.create_left_panel()
        grid = self._gtk.HomogeneousGrid()
        grid.attach(leftpanel, 0, 0, 1, 1)
        if self._screen.vertical_mode:
            self.labels['menu'] = self.arrangeMenuItems(items, 3, True)
            grid.attach(self.labels['menu'], 0, 1, 1, 1)
        else:
            self.labels['menu'] = self.arrangeMenuItems(items, 2, True)
            grid.attach(self.labels['menu'], 1, 0, 1, 1)
        self.grid = grid
        self.content.add(self.grid)
        self.layout.show_all()

    def activate(self):
        if self.graph_update is None:
            # This has a high impact on load
            self.graph_update = GLib.timeout_add_seconds(5, self.update_graph)
        return

    def deactivate(self):
        if self.graph_update is not None:
            GLib.source_remove(self.graph_update)
            self.graph_update = None

    def add_device(self, device):

        logging.info(f"Adding device: {device}")

        temperature = self._printer.get_dev_stat(device, "temperature")
        if temperature is None:
            return False

        if not (device.startswith("extruder") or device.startswith("heater_bed")):
            devname = " ".join(device.split(" ")[1:])
            # Support for hiding devices by name
            if devname.startswith("_"):
                return False
        else:
            devname = device

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

        can_target = self._printer.get_temp_store_device_has_target(device)
        self.labels['da'].add_object(device, "temperatures", rgb, False, True)
        if can_target:
            self.labels['da'].add_object(device, "targets", rgb, True, False)

        name = self._gtk.ButtonImage(image, devname.capitalize().replace("_", " "),
                                     None, .5, Gtk.PositionType.LEFT, False)
        name.connect('clicked', self.on_popover_clicked, device)
        name.set_alignment(0, .5)
        name.get_style_context().add_class(class_name)
        child = name.get_children()[0].get_children()[0].get_children()[1]
        child.set_ellipsize(Pango.EllipsizeMode.END)

        temp = self._gtk.Button("")
        temp.connect('clicked', self.on_popover_clicked, device)

        self.devices[device] = {
            "class": class_name,
            "name": name,
            "temp": temp,
            "can_target": can_target
        }

        devices = sorted(self.devices)
        pos = devices.index(device) + 1

        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(name, 0, pos, 1, 1)
        self.labels['devices'].attach(temp, 1, pos, 1, 1)
        self.labels['devices'].show_all()
        return True

    def change_target_temp(self, temp):

        max_temp = int(float(self._printer.get_config_section(self.active_heater)['max_temp']))
        if temp > max_temp:
            self._screen.show_popup_message(_("Can't set above the maximum:") + f' {max_temp}')
            return
        temp = max(temp, 0)

        if self.active_heater.startswith('extruder'):
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(self.active_heater), temp)
        elif self.active_heater == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(temp)
        elif self.active_heater.startswith('heater_generic '):
            self._screen._ws.klippy.set_heater_temp(" ".join(self.active_heater.split(" ")[1:]), temp)
        elif self.active_heater.startswith('temperature_fan '):
            self._screen._ws.klippy.set_temp_fan_temp(" ".join(self.active_heater.split(" ")[1:]), temp)
        else:
            logging.info(f"Unknown heater: {self.active_heater}")
            self._screen.show_popup_message(_("Unknown Heater") + " " + self.active_heater)
        self._printer.set_dev_stat(self.active_heater, "target", temp)

    def create_left_panel(self):

        self.labels['devices'] = Gtk.Grid()
        self.labels['devices'].get_style_context().add_class('heater-grid')
        self.labels['devices'].set_vexpand(False)

        name = Gtk.Label("")
        temp = Gtk.Label(_("Temp (°C)"))
        temp.set_size_request(round(self._gtk.get_font_size() * 7.7), -1)

        self.labels['devices'].attach(name, 0, 0, 1, 1)
        self.labels['devices'].attach(temp, 1, 0, 1, 1)

        self.labels['da'] = HeaterGraph(self._printer, self._gtk.get_font_size())
        self.labels['da'].set_vexpand(True)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.labels['devices'])

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.add(scroll)
        box.add(self.labels['da'])

        self.labels['graph_settemp'] = self._gtk.Button(label=_("Set Temp"))
        self.labels['graph_settemp'].connect("clicked", self.show_numpad)
        self.labels['graph_hide'] = self._gtk.Button(label=_("Hide"))
        self.labels['graph_hide'].connect("clicked", self.graph_show_device, False)
        self.labels['graph_show'] = self._gtk.Button(label=_("Show"))
        self.labels['graph_show'].connect("clicked", self.graph_show_device)

        popover = Gtk.Popover()
        self.labels['popover_vbox'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        popover.add(self.labels['popover_vbox'])
        popover.set_position(Gtk.PositionType.BOTTOM)
        self.labels['popover'] = popover

        for d in self._printer.get_temp_store_devices():
            self.add_device(d)

        return box

    def graph_show_device(self, widget, show=True):
        logging.info(f"Graph show: {self.popover_device} {show}")
        self.labels['da'].set_showing(self.popover_device, show)
        if show:
            self.devices[self.popover_device]['name'].get_style_context().remove_class("graph_label_hidden")
            self.devices[self.popover_device]['name'].get_style_context().add_class(
                self.devices[self.popover_device]['class'])
        else:
            self.devices[self.popover_device]['name'].get_style_context().remove_class(
                self.devices[self.popover_device]['class'])
            self.devices[self.popover_device]['name'].get_style_context().add_class("graph_label_hidden")
        self.labels['da'].queue_draw()
        self.popover_populate_menu()
        self.labels['popover'].show_all()

    def hide_numpad(self, widget):
        self.devices[self.active_heater]['name'].get_style_context().remove_class("button_active")
        self.active_heater = None

        if self._screen.vertical_mode:
            self.grid.remove_row(1)
            self.grid.attach(self.labels['menu'], 0, 1, 1, 1)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self.labels['menu'], 1, 0, 1, 1)
        self.grid.show_all()

    def on_popover_clicked(self, widget, device):
        self.popover_device = device
        po = self.labels['popover']
        po.set_relative_to(widget)
        self.popover_populate_menu()
        po.show_all()

    def popover_populate_menu(self):
        pobox = self.labels['popover_vbox']
        for child in pobox.get_children():
            pobox.remove(child)

        if self.labels['da'].is_showing(self.popover_device):
            pobox.pack_start(self.labels['graph_hide'], True, True, 5)
        else:
            pobox.pack_start(self.labels['graph_show'], True, True, 5)
        if self.devices[self.popover_device]["can_target"]:
            pobox.pack_start(self.labels['graph_settemp'], True, True, 5)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        for x in self._printer.get_tools():
            self.update_temp(
                x,
                self._printer.get_dev_stat(x, "temperature"),
                self._printer.get_dev_stat(x, "target")
            )
        for h in self._printer.get_heaters():
            self.update_temp(
                h,
                self._printer.get_dev_stat(h, "temperature"),
                self._printer.get_dev_stat(h, "target"),
            )
        return

    def show_numpad(self, widget):

        if self.active_heater is not None:
            self.devices[self.active_heater]['name'].get_style_context().remove_class("button_active")
        self.active_heater = self.popover_device
        self.devices[self.active_heater]['name'].get_style_context().add_class("button_active")

        if "keypad" not in self.labels:
            self.labels["keypad"] = Keypad(self._screen, self.change_target_temp, self.hide_numpad)
        self.labels["keypad"].clear()

        if self._screen.vertical_mode:
            self.grid.remove_row(1)
            self.grid.attach(self.labels["keypad"], 0, 1, 1, 1)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self.labels["keypad"], 1, 0, 1, 1)
        self.grid.show_all()

        self.labels['popover'].popdown()

    def update_graph(self):
        self.labels['da'].queue_draw()
        return True

    def update_temp(self, device, temp, target):
        if device not in self.devices:
            return
        if self.devices[device]["can_target"] and target > 0:
            self.devices[device]["temp"].get_child().set_label(f"{temp:.1f} / {target:.0f}")
        else:
            self.devices[device]["temp"].get_child().set_label(f"{temp:.1f}")
