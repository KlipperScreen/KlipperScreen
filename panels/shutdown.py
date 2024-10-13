import logging
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Shutdown")
        super().__init__(screen, title)

        estop = self._gtk.Button("emergency", _("Emergency Stop"), "color2")
        estop.connect("clicked", self.emergency_stop)

        poweroff = self._gtk.Button("shutdown", _("Shutdown"), "color1")
        poweroff.connect("clicked", self.reboot_poweroff, "shutdown")

        restart = self._gtk.Button("refresh", _("Restart"), "color3")
        restart.connect("clicked", self.reboot_poweroff, "reboot")

        restart_ks = self._gtk.Button("refresh", _("Restart") + " KlipperScreen", "color3")
        restart_ks.connect("clicked", self._screen.restart_ks)

        self.main = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        if self._printer and self._printer.state not in {'disconnected', 'startup', 'shutdown', 'error'}:
            self.main.attach(estop, 0, 0, 1, 1)
        self.main.attach(restart_ks, 1, 0, 1, 1)
        self.main.attach(poweroff, 0, 1, 1, 1)
        self.main.attach(restart, 1, 1, 1, 1)
        self.content.add(self.main)

    def reboot_poweroff(self, widget, method):
        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        if method == "reboot":
            label.set_label(_("Are you sure you wish to reboot the system?"))
            title = _("Restart")
        else:
            label.set_label(_("Are you sure you wish to shutdown the system?"))
            title = _("Shutdown")
        buttons = []
        if (
            self._screen.apiclient is None
            or "127.0.0.1" in self._screen.apiclient.endpoint
            or "localhost" in self._screen.apiclient.endpoint
        ):
            buttons.append({"name": _("Accept"), "response": Gtk.ResponseType.ACCEPT, "style": 'dialog-primary'})
        else:
            logging.info(self._screen.apiclient.endpoint)
            buttons.extend([
                {"name": _("Host"), "response": Gtk.ResponseType.OK, "style": 'dialog-info'},
                {"name": _("Printer"), "response": Gtk.ResponseType.APPLY, "style": 'dialog-warning'},
                {"name": _("Both"), "response": Gtk.ResponseType.ACCEPT, "style": 'dialog-primary'},
            ])
        buttons.append({"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'})
        self._gtk.Dialog(title, buttons, label, self.reboot_poweroff_confirm, method)

    def reboot_poweroff_confirm(self, dialog, response_id, method):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.ACCEPT:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
                os.system("systemctl reboot -i")
            else:
                self._screen._ws.send_method("machine.shutdown")
                os.system("systemctl poweroff -i")
        elif response_id == Gtk.ResponseType.OK:
            if method == "reboot":
                os.system("systemctl reboot -i")
            else:
                os.system("systemctl poweroff -i")
        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            else:
                self._screen._ws.send_method("machine.shutdown")
