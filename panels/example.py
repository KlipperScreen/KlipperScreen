import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return ExamplePanel(*args)


class ExamplePanel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)

        # Create gtk items here

        self.content.add(Gtk.Box())
