import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from KlippyGcodes import KlippyGcodes
from panels.screen_panel import ScreenPanel

class SystemPanel(ScreenPanel):
    def initialize(self, panel_name):
        # Create gtk items here

        grid = KlippyGtk.HomogeneousGrid()

        restart = KlippyGtk.ButtonImage('reboot','Klipper Restart','color1')
        restart.connect("clicked", self.restart_klippy)
        firmrestart = KlippyGtk.ButtonImage('restart','Firmware Restart','color2')
        restart.connect("clicked", self.restart_klippy, "firmware")
        back = KlippyGtk.ButtonImage('back', 'Back')
        back.connect("clicked", self._screen._menu_go_back)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info.set_vexpand(True)

        title = Gtk.Label("System Information")
        title.set_margin_bottom(5)
        title.set_margin_top(15)

        self.labels['loadavg'] = Gtk.Label("temp")
        self.update_system_load()

        self.system_timeout = GLib.timeout_add(1000, self.update_system_load)

        title.get_style_context().add_class('temperature_entry')
        self.labels['loadavg'].get_style_context().add_class('temperature_entry')

        info.add(title)
        info.add(self.labels['loadavg'])


        grid.attach(info, 0, 0, 4, 2)
        grid.attach(restart, 0, 2, 1, 1)
        grid.attach(firmrestart, 1, 2, 1, 1)
        grid.attach(back, 3, 2, 1, 1)

        self.panel = grid

    def update_system_load(self):
        lavg = os.getloadavg()
        self.labels['loadavg'].set_text(
            "Load Average: %.2f %.2f %.2f" % (lavg[0], lavg[1], lavg[2])
        )

        #TODO: Shouldn't need this
        self.system_timeout = GLib.timeout_add(1000, self.update_system_load)

    def restart_klippy(self, type=None):
        if type == "firmware":
            self._screen._ws.klippy.restart_firmware()
        else:
            self._screen._ws.klippy.restart()
