import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return ScreenSaverPanel(*args)

class ScreenSaverPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext

        box = Gtk.Box()
        box.set_hexpand(True)
        box.set_vexpand(True)
        box.set_halign(Gtk.Align.CENTER)

        l = Gtk.Label(_("Screen will show in less than one second"))
        box.add(l)


        self.layout = box
