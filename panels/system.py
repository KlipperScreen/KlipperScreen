import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return SystemPanel(*args)

class SystemPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)

        restart = self._gtk.ButtonImage('reboot',"\n".join(_('Klipper Restart').split(' ')),'color1')
        restart.connect("clicked", self.restart_klippy)
        firmrestart = self._gtk.ButtonImage('restart',"\n".join(_('Firmware Restart').split(' ')),'color2')
        firmrestart.connect("clicked", self.restart_klippy, "firmware")

        ks_restart = self._gtk.ButtonImage('reboot',"\n".join(_('Restart Klipper Screen').split(' ')))
        ks_restart.connect("clicked", self.restart_ks)

        reboot = self._gtk.ButtonImage('reboot',_('System\nRestart'),'color3')
        reboot.connect("clicked", self._screen._confirm_send_action,
            _("Are you sure you wish to reboot the system?"), "machine.reboot")
        shutdown = self._gtk.ButtonImage('shutdown',_('System\nShutdown'),'color4')
        shutdown.connect("clicked", self._screen._confirm_send_action,
            _("Are you sure you wish to shutdown the system?"), "machine.shutdown")

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info.set_vexpand(True)

        self.labels['loadavg'] = Gtk.Label("temp")
        self.update_system_load()

        self.system_timeout = GLib.timeout_add(1000, self.update_system_load)

        self.labels['klipper_version'] = Gtk.Label(_("Klipper Version") +
            (": %s" % self._screen.printer.get_klipper_version()))
        self.labels['klipper_version'].set_margin_top(15)

        self.labels['ks_version'] = Gtk.Label(_("KlipperScreen Version") + (": %s" % self._screen.version))
        self.labels['ks_version'].set_margin_top(15)

        info.add(self.labels['loadavg'])
        info.add(self.labels['klipper_version'])
        info.add(self.labels['ks_version'])


        grid.attach(info, 0, 0, 5, 2)
        grid.attach(restart, 0, 2, 1, 1)
        grid.attach(firmrestart, 1, 2, 1, 1)
        grid.attach(ks_restart, 2, 2, 1, 1)
        grid.attach(reboot, 3, 2, 1, 1)
        grid.attach(shutdown, 4, 2, 1, 1)

        self.content.add(grid)

    def update_system_load(self):
        _ = self.lang.gettext
        lavg = os.getloadavg()
        self.labels['loadavg'].set_text(
            _("Load Average") + (": %.2f %.2f %.2f" % (lavg[0], lavg[1], lavg[2]))
        )

        #TODO: Shouldn't need this
        self.system_timeout = GLib.timeout_add(1000, self.update_system_load)

    def restart_klippy(self, widget, type=None):
        if type == "firmware":
            self._screen._ws.klippy.restart_firmware()
        else:
            self._screen._ws.klippy.restart()

    def restart_ks(self, widget):
        os.system("sudo systemctl restart KlipperScreen")
