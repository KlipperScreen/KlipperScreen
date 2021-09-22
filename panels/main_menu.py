import datetime
import gi
import math
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from panels.menu import MenuPanel
from ks_includes.graph import HeaterGraph

def create_panel(*args):
    return MainPanel(*args)

class MainPanel(MenuPanel):
    def __init__(self, screen, title, back=False):
        super().__init__(screen, title, False)
        self.devices = {}
        self.graph_update = None

    def initialize(self, panel_name, items, extrudercount):
        print("### Making MainMenu")

        grid = self._gtk.HomogeneousGrid()
        grid.set_hexpand(True)
        grid.set_vexpand(True)

        self.items = items
        self.create_menu_items()

        self.grid = Gtk.Grid()
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(True)

        leftpanel = self.create_left_panel()
        grid.attach(leftpanel, 0, 0, 1, 1)
        grid.attach(self.arrangeMenuItems(items, 2, True), 1, 0, 1, 1)

        self.grid = grid

        self.content.add(self.grid)
        self.layout.show_all()

    def activate(self):
        if self.graph_update is None:
            self.graph_update = GLib.timeout_add_seconds(1, self.update_graph)
        return

    def deactivate(self):
        if self.graph_update is not None:
            GLib.source_remove(self.graph_update)
            self.graph_update = None

    def add_device(self, device):
        logging.info("Adding device: %s" % device)

        if not (device.startswith("extruder") or device.startswith("heater_bed")):
            devname = " ".join(device.split(" ")[1:])
        else:
            devname = device

        if device.startswith("extruder"):
            i = 0
            for d in self.devices:
                if d.startswith('extruder'):
                    i += 1
            image = "extruder-%s" % i
        elif device == "heater_bed":
            image = "bed"
            devname = "Heater Bed"
        else:
            image = "heat-up"

        name = self._gtk.ImageLabel(image, devname.capitalize(), 20, False, .5, .5)
        name['b'].set_hexpand(True)

        temp = Gtk.Label("")
        temp.set_markup(self.format_temp(self._printer.get_dev_stat(device, "temperature")))
        target = Gtk.Label("")
        target.set_markup(self.format_target(self._printer.get_dev_stat(device, "target")))

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.add(labels)

        self.devices[device] = {
            "name": name,
            "target": target,
            "temp": temp,

        }

        devices = sorted(self.devices)
        pos = devices.index(device) + 1

        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(name['b'], 0, pos, 1, 1)
        self.labels['devices'].attach(temp, 1, pos, 1, 1)
        self.labels['devices'].attach(target, 2, pos, 1, 1)
        self.labels['devices'].show_all()

    def create_left_panel(self):
        _ = self.lang.gettext

        self.labels['devices'] = Gtk.Grid()
        self.labels['devices'].get_style_context().add_class('heater-grid')
        self.labels['devices'].set_vexpand(False)

        name = Gtk.Label("")
        temp = Gtk.Label(_("Temp"))
        temp.set_size_request(round(self._gtk.get_font_size() * 5.5), 0)
        target = Gtk.Label(_("Target"))

        self.labels['devices'].attach(name, 0, 0, 1, 1)
        self.labels['devices'].attach(temp, 1, 0, 1, 1)
        self.labels['devices'].attach(target, 2, 0, 1, 1)

        rgbs = [
            [0, 1, 0],
            [1, 0, 0],
            [0, 0, 1]
        ]
        heaters = ['heater_bed', 'extruder']
        i = 0
        da = HeaterGraph(self._printer)
        da.set_vexpand(True)
        for h in heaters:
            da.add_object(h, "temperatures", rgbs[i], False, True)
            da.add_object(h, "targets", rgbs[i], True, False)
            i += 1
        self.labels['da'] = da

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.add(self.labels['devices'])
        box.add(da)

        self.load_devices()

        return box

    def load_devices(self):
        self.heaters = []

        i = 0
        for x in self._printer.get_tools():
            self.labels[x] = self._gtk.ButtonImage("extruder-"+str(i), self._gtk.formatTemperatureString(0, 0))
            self.heaters.append(x)
            i += 1

        add_heaters = self._printer.get_heaters()
        for h in add_heaters:
            if h == "heater_bed":
                self.labels[h] = self._gtk.ButtonImage("bed", self._gtk.formatTemperatureString(0, 0))
            else:
                name = " ".join(h.split(" ")[1:])
                self.labels[h] = self._gtk.ButtonImage("heat-up", name)
            self.heaters.append(h)

        for d in self.heaters:
            self.add_device(d)
        logging.info("Heaters: %s" % self.heaters)

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

    def update_graph(self):
        self.labels['da'].queue_draw()
        alloc = self.labels['devices'].get_allocation()
        logging.info("Devices height: %s" % alloc.height)
        alloc = self.labels['da'].get_allocation()
        logging.info("DA height: %s" % alloc.height)
        return True

    def update_temp(self, device, temp, target):
        if device not in self.devices:
            return

        self.devices[device]["temp"].set_markup(self.format_temp(temp))
        if "target" in self.devices[device]:
            self.devices[device]["target"].set_markup(self.format_target(target))
