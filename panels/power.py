import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Power")
        super().__init__(screen, title)
        self.devices = {}

        # Create a grid for all devices
        self.labels['devices'] = Gtk.Grid(valign=Gtk.Align.CENTER)

        self.load_power_devices()

        # Create a scroll window for the power devices
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels['devices'])

        self.content.add(scroll)

    def activate(self):
        devices = self._printer.get_power_devices()
        for x in devices:
            self.devices[x]['switch'].disconnect_by_func(self.on_switch)
            self.devices[x]['switch'].set_active(self._printer.get_power_device_status(x) == "on")

            self.devices[x]['switch'].connect("notify::active", self.on_switch, x)

    def add_device(self, device):
        name = Gtk.Label(
            hexpand=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        name.set_markup(f"<big><b>{device}</b></big>")
        switch = Gtk.Switch(hexpand=False, active=(self._printer.get_power_device_status(device) == "on"),
                            width_request=round(self._gtk.font_size * 7),
                            height_request=round(self._gtk.font_size * 3.5))
        switch.connect("notify::active", self.on_switch, device)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)

        dev = Gtk.Box(
            spacing=5, hexpand=True, vexpand=False, valign=Gtk.Align.CENTER)
        dev.add(labels)
        dev.add(switch)

        self.devices[device] = {
            "row": dev,
            "switch": switch
        }

        devices = sorted(self.devices)
        pos = devices.index(device)

        self.labels['devices'].insert_row(pos)
        self.labels['devices'].attach(self.devices[device]['row'], 0, pos, 1, 1)
        self.labels['devices'].show_all()

    def load_power_devices(self):
        devices = self._printer.get_power_devices()
        for x in devices:
            self.add_device(x)

    def on_switch(self, switch, gparam, device):
        logging.debug(f"Power toggled {device}")
        if switch.get_active():
            self._screen._ws.klippy.power_device_on(device)
        else:
            self._screen._ws.klippy.power_device_off(device)

    def process_update(self, action, data):
        if action != "notify_power_changed":
            return

        if data['device'] not in self.devices:
            return
        device = data['device']
        self.devices[device]['switch'].disconnect_by_func(self.on_switch)
        self.devices[device]['switch'].set_active(data['status'] == "on")
        self.devices[device]['switch'].connect("notify::active", self.on_switch, device)
