import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from KlippyGcodes import KlippyGcodes

class ScreenPanel:
    def __init__(self, screen):
        self._screen = screen
        self.lang = self._screen.lang
        self._printer = screen.printer
        self.labels = {}


    def initialize(self, panel_name):
        # Create gtk items here
        return

    def emergency_stop(self, widget):
        self._screen._ws.klippy.emergency_stop()

    def get(self):
        # Return gtk item
        return self.panel

    def home(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

    def menu_item_clicked(self, widget, panel, item):
        print("### Creating panel "+ item['panel'])
        if "items" in item:
            self._screen.show_panel(self._screen._cur_panels[-1] + '_' + item['name'], item['panel'], 1, False, items=item['items'])
            return
        self._screen.show_panel(self._screen._cur_panels[-1] + '_' + item['name'], item['panel'], 1, False)

    def update_image_text(self, label, text):
        if label in self.labels and 'l' in self.labels[label]:
            self.labels[label]['l'].set_text(text)

    def update_temp(self, dev, temp, target):
        if dev in self.labels:
            self.labels[dev].set_label(KlippyGtk.formatTemperatureString(temp, target))
