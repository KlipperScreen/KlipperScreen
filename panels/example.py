import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return ExamplePanel(*args)


class ExamplePanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext
        # Create gtk items here

        self.content.add(Gtk.Box())
