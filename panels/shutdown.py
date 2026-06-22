import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.functions import run_systemctl
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Shutdown")
        super().__init__(screen, title)

        estop = self._gtk.Button("emergency", _("Emergency Stop"), "color2")
        estop.connect("clicked", self.emergency_stop)

        power_panel = {
            "panel": "power",
        }
        power_shortcut = self._gtk.Button("shutdown", _("Power"), "color2")
        power_shortcut.connect("clicked", self.menu_item_clicked, power_panel)

        poweroff = self._gtk.Button("shutdown", _("Shutdown"), "color1")
        poweroff.connect("clicked", self.reboot_poweroff, "shutdown")

        restart = self._gtk.Button("refresh", _("Restart"), "color3")
        restart.connect("clicked", self.reboot_poweroff, "reboot")

        restart_ks = self._gtk.Button("refresh", _("Restart") + " KlipperScreen", "color3")
        restart_ks.connect("clicked", self._screen.restart_ks)

        lock_screen = self._gtk.Button("lock", _("Lock"), "color3")
        lock_screen.connect("clicked", self._screen.lock_screen.lock)

        self.main = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        show_estop = self._printer and self._printer.state not in {
            "disconnected",
            "startup",
            "shutdown",
            "error",
        }
        show_power_shortcut = False
        if self.ks_printer_cfg is not None and self._screen.state.connected:
            power_devices = self.ks_printer_cfg.get("power_devices", "")
            if power_devices and self._printer.get_power_devices():
                show_power_shortcut = True

        if show_estop and show_power_shortcut:
            self.main.attach(estop, 0, 0, 1, 1)
            self.main.attach(power_shortcut, 0, 1, 1, 1)
        elif show_estop:
            self.main.attach(estop, 0, 0, 1, 2)
        elif show_power_shortcut:
            self.main.attach(power_shortcut, 0, 0, 1, 2)
        self.main.attach(restart_ks, 1, 0, 1, 1)
        self.main.attach(lock_screen, 2, 0, 1, 1)
        self.main.attach(poweroff, 1, 1, 1, 1)
        self.main.attach(restart, 2, 1, 1, 1)
        self.content.add(self.main)

    def reboot_poweroff(self, widget, method):
        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        if method == "reboot":
            label.set_label(_("Are you sure you wish to reboot the system?"))
            title = _("Restart")
        else:
            label.set_label(_("Are you sure you wish to shutdown the system?"))
            title = _("Shutdown")
        buttons = []
        if self._screen.state.printer_is_local:
            buttons.append(
                {
                    "name": _("Accept"),
                    "response": Gtk.ResponseType.ACCEPT,
                    "style": "dialog-primary",
                }
            )
        else:
            logging.info(self._screen.restApi.endpoint)
            buttons.extend(
                [
                    {"name": _("Host"), "response": Gtk.ResponseType.OK, "style": "dialog-info"},
                    {
                        "name": _("Printer"),
                        "response": Gtk.ResponseType.APPLY,
                        "style": "dialog-warning",
                    },
                    {
                        "name": _("Both"),
                        "response": Gtk.ResponseType.ACCEPT,
                        "style": "dialog-primary",
                    },
                ]
            )
        buttons.append(
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": "dialog-error"}
        )
        self._gtk.Dialog(title, buttons, label, self.reboot_poweroff_confirm, method)

    def reboot_poweroff_confirm(self, dialog, response_id, method):
        self._gtk.remove_dialog(dialog)

        if response_id == Gtk.ResponseType.ACCEPT:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
                ret, err = run_systemctl("reboot")
                if ret != 0:
                    self._screen.show_popup_message(
                        f"Failed to reboot host: {err if err else f'exit code {ret}'}"
                    )
            else:
                self.turn_off_power_devices()
                self._screen._ws.send_method("machine.shutdown")
                ret, err = run_systemctl("poweroff")
                if ret != 0:
                    self._screen.show_popup_message(
                        f"Failed to power off host: {err if err else f'exit code {ret}'}"
                    )
        elif response_id == Gtk.ResponseType.OK:
            if method == "reboot":
                ret, err = run_systemctl("reboot")
                if ret != 0:
                    self._screen.show_popup_message(
                        f"Failed to reboot host: {err if err else f'exit code {ret}'}"
                    )
            else:
                ret, err = run_systemctl("poweroff")
                if ret != 0:
                    self._screen.show_popup_message(
                        f"Failed to power off host: {err if err else f'exit code {ret}'}"
                    )
        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            else:
                self.turn_off_power_devices()
                self._screen._ws.send_method("machine.shutdown")

    def turn_off_power_devices(self):
        if self.ks_printer_cfg is not None and self._screen.state.connected:
            power_devices = self.ks_printer_cfg.get("power_devices", "")
            if power_devices and self._printer.get_power_devices():
                logging.info(f"Turning off associated power devices: {power_devices}")
                self._screen.power_devices(widget=None, devices=power_devices, on=False)
