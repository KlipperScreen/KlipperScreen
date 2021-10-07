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
            class_name = "graph_label_%s" % device
            rgb, color = self._gtk.get_temp_color("extruder")
        elif device == "heater_bed":
            image = "bed"
            devname = "Heater Bed"
            class_name = "graph_label_heater_bed"
            rgb = [1, 0, 0]
            rgb, color = self._gtk.get_temp_color("bed")
        else:
            s = 1
            for d in self.devices:
                if "sensor" in d:
                    s += 1
            image = "heat-up"
            class_name = "graph_label_sensor_%s" % s
            rgb = [1, 0, 0]
            rgb, color = self._gtk.get_temp_color("sensor")


        can_target = self._printer.get_temp_store_device_has_target(device)
        self.labels['da'].add_object(device, "temperatures", rgb, False, True)
        if can_target:
            self.labels['da'].add_object(device, "targets", rgb, True, False)

        text = "<span underline='double' underline_color='#%s'>%s</span>" % (color, devname.capitalize())
        name = self._gtk.ButtonImage(image, devname.capitalize(), None, .5, .5, Gtk.PositionType.LEFT, False)
        # name['b'].set_hexpand(True)
        name.connect('clicked', self.on_popover_clicked, device)
        name.set_alignment(0, .5)
        name.get_style_context().add_class(class_name)
        child = name.get_children()[0].get_children()[0].get_children()[1]
        child.set_ellipsize(True)
        child.set_ellipsize(Pango.EllipsizeMode.END)
        logging.info("DClass %s %s" % (device, class_name))


        temp = Gtk.Label("")
        temp.set_markup(self.format_temp(self._printer.get_dev_stat(device, "temperature")))

        if can_target:
            target = Gtk.Label("")
            target.set_markup(self.format_target(self._printer.get_dev_stat(device, "target")))

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        dev.set_hexpand(True)
        dev.set_vexpand(False)
        dev.add(labels)

        self.devices[device] = {
            "name": name,
            "temp": temp
        }
        if can_target:
            self.devices[device]["target"] = target

        devices = sorted(self.devices)
        pos = devices.index(device) + 1

        self.labels['devices'].insert_row(pos)
        # self.labels['devices'].attach(name['b'], 0, pos, 1, 1)
        self.labels['devices'].attach(name, 0, pos, 1, 1)
        self.labels['devices'].attach(temp, 1, pos, 1, 1)
        if can_target:
            self.labels['devices'].attach(target, 2, pos, 1, 1)
        self.labels['devices'].show_all()

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

    def graph_show_device(self, widget, show=True):
        logging.info("Graph show: %s %s" % (self.popover_device, show))
        self.labels['da'].set_showing(self.popover_device, show)
        self.labels['da'].queue_draw()
        self.popover_populate_menu()
        self.labels['popover'].show_all()

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

        da = HeaterGraph(self._printer)
        da.set_vexpand(True)
        self.labels['da'] = da

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.add(self.labels['devices'])
        box.add(da)


        self.labels['graph_hide'] = self._gtk.Button(label="Hide")
        self.labels['graph_hide'].connect("clicked", self.graph_show_device, False)
        self.labels['graph_show'] = self._gtk.Button(label="Show")
        self.labels['graph_show'].connect("clicked", self.graph_show_device)

        popover = Gtk.Popover()
        self.labels['popover_vbox'] = Gtk.VBox()
        # vbox.pack_start(Gtk.Button(label="Hide"), False, True, 10)
        # vbox.pack_start(Gtk.Label(label="Item 2"), False, True, 10)
        popover.add(self.labels['popover_vbox'])
        popover.set_position(Gtk.PositionType.BOTTOM)
        self.labels['popover'] = popover

        for d in self._printer.get_temp_store_devices():
            self.add_device(d)

        return box

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
