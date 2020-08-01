import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from panels.screen_panel import ScreenPanel

class BedLevelPanel(ScreenPanel):
    def initialize(self, menu):
        # Create gtk items here
        self.panel = KlippyGtk.HomogeneousGrid()

        self.labels['tl'] = KlippyGtk.ButtonImage("bed-level-t-l")
        self.labels['tr'] = KlippyGtk.ButtonImage("bed-level-t-r")
        self.labels['bl'] = KlippyGtk.ButtonImage("bed-level-b-l")
        self.labels['br'] = KlippyGtk.ButtonImage("bed-level-b-r")

        self.panel.attach(self.labels['tl'], 1, 0, 1, 1)
        self.panel.attach(self.labels['tr'], 2, 0, 1, 1)
        self.panel.attach(self.labels['bl'], 1, 1, 1, 1)
        self.panel.attach(self.labels['br'], 2, 1, 1, 1)

        self.labels['home'] = KlippyGtk.ButtonImage("home","Home All","color2")
        self.labels['dm'] = KlippyGtk.ButtonImage("motor-off", "Disable X/Y", "color3")

        self.panel.attach(self.labels['home'], 0, 0, 1, 1)
        self.panel.attach(self.labels['dm'], 0, 1, 1, 1)

        b = KlippyGtk.ButtonImage('back', 'Back')
        b.connect("clicked", self._screen._menu_go_back)
        self.panel.attach(b, 3, 1, 1, 1)
