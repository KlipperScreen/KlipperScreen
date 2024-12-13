import gi
import os
import pathlib

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel
from screen import (
    KlipperScreen,
    KlippyGtk
)


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        self._screen: KlipperScreen
        self._gtk: KlippyGtk

        title = title or _("Nozzle")
        super().__init__(screen, title)

        # HACK: to make it centered
        self.labels['text'] = Gtk.Label(f"\n")
        self.content.add(self.labels['text'])
        
        self.above = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        self.below = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)

        self.create_nozzle_image_button("nozzle-ST025", self.above, "Standard 0.25mm")
        self.create_nozzle_image_button("nozzle-ST04", self.above, "Standard 0.4mm")
        self.create_nozzle_image_button("nozzle-ST08", self.above, "Standard 0.8mm")
        self.create_nozzle_image_button("nozzle-METAL04", self.below, "Metal 0.4mm")
        self.create_nozzle_image_button("nozzle-FIBER06", self.below, "Fiber 0.6mm")

        self.content.add(self.above)
        self.content.add(self.below)

    def image_from_directory(self, image_name, directory):
        # Get it from specific directory instead of theme_dir
        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, directory)
        width = self._gtk.content_width * 4
        height = self._gtk.content_height * .4
        filename = os.path.join(styles_dir, image_name)
        file = f"{filename}.png"
        pixbuf = self._gtk.PixbufFromFile(file, int(width), int(height)) if os.path.exists(file) else None
        return Gtk.Image.new_from_pixbuf(pixbuf) if pixbuf is not None else Gtk.Image()

    def create_nozzle_image_button(self, image_name, box, nozzle):
        image = self.image_from_directory(image_name, os.path.join("syncraft", "images"))
        event_box = Gtk.EventBox()
        event_box.add(image)
        event_box.connect("button-press-event", self.on_image_clicked, nozzle)
        box.pack_start(event_box, True, True, 8)

    def on_image_clicked(self, widget, event, nozzle):
        self.nozzlegcodescript(nozzle)
        self._screen._menu_go_back()

    def nozzlegcodescript(self, nozzle):
        self._screen._ws.klippy.gcode_script(
            f"NOZZLE_SET NZ='{nozzle}' EXTRUDER='{self._config.extruder}'"
        )