import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from KlippyGcodes import KlippyGcodes
from panels.screen_panel import ScreenPanel

class ExamplePanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext
        # Create gtk items here
        return
