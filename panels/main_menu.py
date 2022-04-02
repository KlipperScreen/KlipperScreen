import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from panels.menu import MenuPanel

from ks_includes.widgets.graph import HeaterGraph
from ks_includes.widgets.keypad import Keypad

def create_panel(*args):
    return MainPanel(*args)

class MainPanel(MenuPanel):
    def __init__(self, screen, title, back=False):
        super().__init__(screen, title, False)
        self.devices = {}
        self.graph_update = None
        self.active_heater = None

    def initialize(self, panel_name, items, extrudercount):
        print("### Making MainMenu")

        grid = self._gtk.HomogeneousGrid()
        grid.set_hexpand(True)
        grid.set_vexpand(True)

        self.items = items
        self.create_menu_items()
        self._gtk.reset_temp_color()

        self.grid = Gtk.Grid()
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(True)

        leftpanel = self.create_left_panel()
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
        _ = self.lang.gettext
        logging.info("Adding device: %s" % device)

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
            i = 0
            for d in self.devices:
                if d.startswith('extruder'):
                    i += 1
            if self._printer.extrudercount > 1:
                image = "extruder-%s" % i
            else:
                image = "extruder"
            class_name = "graph_label_%s" % device
            type = "extruder"
        elif device == "heater_bed":
            image = "bed"
            devname = "Heater Bed"
            class_name = "graph_label_heater_bed"
            type = "bed"
        elif device.startswith("heater_generic"):
            self.h = 1
            for d in self.devices:
                if "heater_generic" in d:
                    self.h += 1
            image = "heater"
            class_name = "graph_label_sensor_%s" % self.h
            type = "sensor"
        elif device.startswith("temperature_fan"):
            f = 1
            for d in self.devices:
                if "temperature_fan" in d:
                    f += 1
            image = "fan"
            class_name = "graph_label_fan_%s" % f
            type = "fan"
        elif self._config.get_main_config_option('only_heaters') == "True":
            return False
        else:
            s = 1
            try:
                s += self.h
            except Exception:
                pass
            for d in self.devices:
                if "sensor" in d:
                    s += 1
            image = "heat-up"
            class_name = "graph_label_sensor_%s" % s
            type = "sensor"

        rgb, color = self._gtk.get_temp_color(type)

        can_target = self._printer.get_temp_store_device_has_target(device)
        self.labels['da'].add_object(device, "temperatures", rgb, False, True)
        if can_target:
            self.labels['da'].add_object(device, "targets", rgb, True, False)

        text = "<span underline='double' underline_color='#%s'>%s</span>" % (color, devname.capitalize())
        name = self._gtk.ButtonImage(image, devname.capitalize().replace("_", " "),
                                     None, .5, Gtk.PositionType.LEFT, False)
        name.connect('clicked', self.on_popover_clicked, device)
        name.set_alignment(0, .5)
        name.get_style_context().add_class(class_name)
        child = name.get_children()[0].get_children()[0].get_children()[1]
        child.set_ellipsize(True)
        child.set_ellipsize(Pango.EllipsizeMode.END)

        temp = self._gtk.Button("")
        temp.connect('clicked', self.on_popover_clicked, device)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.add(labels)

        self.devices[device] = {
            "class": class_name,
            "type": type,
            "name": name,
            "temp": temp,
            "can_target": can_target
        }

        if self.devices[device]["can_target"]:
            temp.get_child().set_label("%.1f %s" %
                                       (temperature, self.format_target(self._printer.get_dev_stat(device, "target"))))
        else:
            temp.get_child().set_label("%.1f " % temperature)

        devices = sorted(self.devices)
        pos = devices.index(device) + 1

        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(name, 0, pos, 1, 1)
        self.labels['devices'].attach(temp, 1, pos, 1, 1)
        self.labels['devices'].show_all()
        return True

    def change_target_temp(self, temp):
        _ = self.lang.gettext

        MAX_TEMP = int(float(self._printer.get_config_section(self.active_heater)['max_temp']))
        if temp > MAX_TEMP:
            self._screen.show_popup_message(_("Can't set above the maximum:") + (" %s" % MAX_TEMP))
            return
        temp = 0 if temp < 0 else temp

        if self.active_heater.startswith('extruder'):
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(self.active_heater), temp)
        elif self.active_heater == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(temp)
        elif self.active_heater.startswith('heater_generic '):
            self._screen._ws.klippy.set_heater_temp(" ".join(self.active_heater.split(" ")[1:]), temp)
        elif self.active_heater.startswith('temperature_fan '):
            self._screen._ws.klippy.set_temp_fan_temp(" ".join(self.active_heater.split(" ")[1:]), temp)
        else:
            logging.info("Unknown heater: %s" % self.active_heater)
            self._screen.show_popup_message(_("Unknown Heater") + " " + self.active_heater)
        self._printer.set_dev_stat(self.active_heater, "target", temp)

    def create_left_panel(self):
        _ = self.lang.gettext

        self.labels['devices'] = Gtk.Grid()
        self.labels['devices'].get_style_context().add_class('heater-grid')
        self.labels['devices'].set_vexpand(False)

        name = Gtk.Label("")
        temp = Gtk.Label(_("Temp (°C)"))
        temp.set_size_request(round(self._gtk.get_font_size() * 7.7), 0)

        self.labels['devices'].attach(name, 0, 0, 1, 1)
        self.labels['devices'].attach(temp, 1, 0, 1, 1)

        da = HeaterGraph(self._printer, self._gtk.get_font_size())
        da.set_vexpand(True)
        self.labels['da'] = da

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.labels['devices'])

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.add(scroll)
        box.add(self.labels['da'])


        self.labels['graph_settemp'] = self._gtk.Button(label=_("Set Temp"))
        self.labels['graph_settemp'].connect("clicked", self.show_numpad)
        self.labels['graph_hide'] = self._gtk.Button(label=_("Hide"))
        self.labels['graph_hide'].connect("clicked", self.graph_show_device, False)
        self.labels['graph_show'] = self._gtk.Button(label=_("Show"))
        self.labels['graph_show'].connect("clicked", self.graph_show_device)

        popover = Gtk.Popover()
        self.labels['popover_vbox'] = Gtk.VBox()
        popover.add(self.labels['popover_vbox'])
        popover.set_position(Gtk.PositionType.BOTTOM)
        self.labels['popover'] = popover

        i = 2
        for d in self._printer.get_temp_store_devices():
            if self.add_device(d):
                i += 1
        if self._screen.vertical_mode:
            aux = 1.38
        else:
            aux = 1
        graph_height = max(0, self._screen.height / aux - (i * 5 * self._gtk.get_font_size()))
        self.labels['da'].set_size_request(0, graph_height)
        return box

    def graph_show_device(self, widget, show=True):
        logging.info("Graph show: %s %s" % (self.popover_device, show))
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
        self.devices[self.active_heater]['name'].get_style_context().remove_class("active_device")
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
            if self.devices[self.popover_device]['type'] != "sensor":
                pobox.pack_start(self.labels['graph_settemp'], True, True, 5)
        else:
            pobox.pack_start(self.labels['graph_show'], True, True, 5)
            if self.devices[self.popover_device]['type'] != "sensor":
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
        _ = self.lang.gettext

        if self.active_heater is not None:
            self.devices[self.active_heater]['name'].get_style_context().remove_class("active_device")
        self.active_heater = self.popover_device
        self.devices[self.active_heater]['name'].get_style_context().add_class("active_device")

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

        if self.devices[device]["can_target"]:
            self.devices[device]["temp"].get_child().set_label("%.1f %s" % (temp, self.format_target(target)))
        else:
            self.devices[device]["temp"].get_child().set_label("%.1f " % temp)
