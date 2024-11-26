import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        image = self._gtk.Image(
            "klipper", self._gtk.content_width * 0.2, self._gtk.content_height * 0.5
        )
        self.labels["text"] = Gtk.Label(
            label=_("Initializing printer..."),
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )

        self.labels["menu"] = self._gtk.Button("settings", _("Menu"), "color4")
        self.labels["menu"].connect("clicked", self._screen._go_to_submenu, "")
        self.labels["restart"] = self._gtk.Button(
            "refresh", _("Klipper Restart"), "color1"
        )
        self.labels["restart"].connect("clicked", self.restart_klipper)
        self.labels["firmware_restart"] = self._gtk.Button(
            "refresh", _("Firmware Restart"), "color2"
        )
        self.labels["firmware_restart"].connect("clicked", self.firmware_restart)
        self.labels["restart_system"] = self._gtk.Button(
            "refresh", _("System Restart"), "color1"
        )
        self.labels["restart_system"].connect("clicked", self.reboot_poweroff, "reboot")
        self.labels["shutdown"] = self._gtk.Button(
            "shutdown", _("System Shutdown"), "color2"
        )
        self.labels["shutdown"].connect("clicked", self.reboot_poweroff, "shutdown")
        self.labels["retry"] = self._gtk.Button("load", _("Retry"), "color3")
        self.labels["retry"].connect("clicked", self.retry)

        self.labels["actions"] = Gtk.Box(hexpand=True, vexpand=False, homogeneous=True)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.labels["text"])

        info = Gtk.Box()
        info.pack_start(image, False, True, 8)
        info.pack_end(scroll, True, True, 8)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main.pack_start(info, True, True, 8)
        main.pack_end(self.labels["actions"], False, False, 0)

        self.show_restart_buttons()

        self.content.add(main)

    def update_text(self, text):
        self.labels["text"].set_label(f"{text}")
        self.show_restart_buttons()

    def clear_action_bar(self):
        for child in self.labels["actions"].get_children():
            self.labels["actions"].remove(child)

    def show_restart_buttons(self):

        self.clear_action_bar()
        if self.ks_printer_cfg is not None and self._screen._ws.connected:
            power_devices = self.ks_printer_cfg.get("power_devices", "")
            if power_devices and self._printer.get_power_devices():
                logging.info(f"Associated power devices: {power_devices}")
                self.add_power_button(power_devices)

        if self._screen.initialized:
            self.labels["actions"].add(self.labels["restart"])
            self.labels["actions"].add(self.labels["firmware_restart"])
        else:
            self.labels["actions"].add(self.labels["restart_system"])
            self.labels["actions"].add(self.labels["shutdown"])
        self.labels["actions"].add(self.labels["menu"])
        if (
            self._screen._ws
            and not self._screen._ws.connecting
            or self._screen.reinit_count > self._screen.max_retries
        ):
            self.labels["actions"].add(self.labels["retry"])
        self.labels["actions"].show_all()

    def add_power_button(self, powerdevs):
        self.labels["power"] = self._gtk.Button(
            "shutdown", _("Power On Printer"), "color3"
        )
        self.labels["power"].connect(
            "clicked", self._screen.power_devices, powerdevs, True
        )
        self.check_power_status()
        self.labels["actions"].add(self.labels["power"])

    def activate(self):
        self.check_power_status()

    def check_power_status(self):
        if "power" in self.labels:
            devices = self._printer.get_power_devices()
            if devices is not None:
                for device in devices:
                    if self._printer.get_power_device_status(device) == "off":
                        self.labels["power"].set_sensitive(True)
                        break
                    elif self._printer.get_power_device_status(device) == "on":
                        self.labels["power"].set_sensitive(False)

    def firmware_restart(self, widget):
        self._screen._ws.klippy.restart_firmware()

    def restart_klipper(self, widget):
        self._screen._ws.klippy.restart()

    def retry(self, widget):
        logging.debug("User retrying connection")
        self._screen.connect_printer(self._screen.connecting_to_printer)
        self.show_restart_buttons()

    def reboot_poweroff(self, widget, method):
        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        if method == "reboot":
            label.set_label(_("Are you sure you wish to reboot the system?"))
            title = _("Restart")
        else:
            label.set_label(_("Are you sure you wish to shutdown the system?"))
            title = _("Shutdown")
        buttons = [
            {
                "name": _("Host"),
                "response": Gtk.ResponseType.OK,
                "style": "dialog-info",
            },
            {
                "name": _("Cancel"),
                "response": Gtk.ResponseType.CANCEL,
                "style": "dialog-error",
            },
        ]
        if self._screen._ws.connected:
            buttons.insert(
                1,
                {
                    "name": _("Printer"),
                    "response": Gtk.ResponseType.APPLY,
                    "style": "dialog-warning",
                },
            )
        self._gtk.Dialog(title, buttons, label, self.reboot_poweroff_confirm, method)

    def reboot_poweroff_confirm(self, dialog, response_id, method):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            if method == "reboot":
                os.system("systemctl reboot -i")
            else:
                os.system("systemctl poweroff -i")
        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            else:
                self._screen._ws.send_method("machine.shutdown")
