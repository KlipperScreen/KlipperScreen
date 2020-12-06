import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.NetworkPanel")

def create_panel(*args):
    return NetworkPanel(*args)

class NetworkPanel(ScreenPanel):
    def initialize(self, menu):
        _ = self.lang.gettext
        grid = self._gtk.HomogeneousGrid()
        grid.set_hexpand(True)

        # Get Hostname
        stream = os.popen('hostname -A')
        hostname = stream.read()
        # Get IP Address
        stream = os.popen('hostname -I')
        ip = stream.read()



        self.labels['networkinfo'] = Gtk.Label(
            _("Network Info") + "\n\n%s%s" % (hostname, ip)
        )
        self.labels['networkinfo'].get_style_context().add_class('temperature_entry')
        grid.attach(self.labels['networkinfo'], 1, 0, 1, 1)

        self.content.add(grid)
