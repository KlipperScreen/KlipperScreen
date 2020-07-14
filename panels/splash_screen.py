import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk

class SplashScreenPanel:
    _screen = None
    labels = {}
    box = None

    def __init__(self, screen):
        self._screen = screen


    def initialize(self):
        image = Gtk.Image()
        #TODO: update file reference
        image.set_from_file("/opt/printer/OctoScreen/styles/z-bolt/images/logo.png")

        label = Gtk.Label()
        label.set_text("Initializing printer...")
        #label = Gtk.Button(label="Initializing printer...")
        #label.connect("clicked", self.printer_initialize)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        main.pack_start(image, True, True, 10)
        main.pack_end(label, True, True, 10)

        box = Gtk.VBox()
        box.add(main)

        self.box = box

    def get(self):
        return self.box
