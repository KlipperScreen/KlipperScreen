import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from jinja2 import Environment, Template

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.KlippyGcodes import KlippyGcodes

class ScreenPanel:

    def __init__(self, screen, title, back=True, action_bar=True, printer_name=True):
        self._screen = screen
        self._config = screen._config
        self._files = screen.files
        self.lang = self._screen.lang
        self._printer = screen.printer
        self.labels = {}
        self._gtk = screen.gtk
        self.control = {}
        self.title = title

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)

        action_bar_width = self._gtk.get_action_bar_width() if action_bar is True else 0
        self.content = Gtk.Box(spacing=0)

    def initialize(self, panel_name):
        # Create gtk items here
        return

    def emergency_stop(self, widget):
        self._screen._ws.klippy.emergency_stop()

    def format_target(self, temp):
        if temp <= 0:
            return ""
        else:
            return self.format_temp(temp, 0)

    def format_temp(self, temp, places=1):
        if places == 0:
            n = int(temp)
        else:
            n = round(temp, places)
        return "%s<small>°C</small>" % str(n)

    def get(self):
        return self.layout

    def get_content(self):
        return self.content

    def get_file_image(self, filename, width=1.6, height=1.6):
        if not self._files.has_thumbnail(filename):
            return None

        loc = self._files.get_thumbnail_location(filename)
        if loc is None:
            return None
        if loc[0] == "file":
            return self._gtk.PixbufFromFile(loc[1], None, width, height)
        if loc[0] == "http":
            return self._gtk.PixbufFromHttp(loc[1], None, width, height)
        return None

    def get_title(self):
        return self.title

    def home(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

    def menu_item_clicked(self, widget, panel, item):
        print("### Creating panel " + item['panel'] + " : %s %s" % (panel, item))
        if "items" in item:
            self._screen.show_panel(self._screen._cur_panels[-1] + '_' + panel, item['panel'], item['name'],
                                    1, False, items=item['items'])
            return
        self._screen.show_panel(self._screen._cur_panels[-1] + '_' + panel, item['panel'], item['name'],
                                1, False)

    def menu_return(self, widget, home=False):
        if home is False:
            self._screen._menu_go_back()
            return
        self._screen._menu_go_home()

    def set_title(self, title):
        self.title = title

    def show_all(self):
        self._screen.show_all()

    def update_image_text(self, label, text):
        if label in self.labels and 'l' in self.labels[label]:
            self.labels[label]['l'].set_text(text)

    def update_temp(self, dev, temp, target, name=None):
        if dev in self.labels:
            if name is None:
                self.labels[dev].set_label(self._gtk.formatTemperatureString(temp, target))
            else:
                self.labels[dev].set_label("%s\n%s" % (name, self._gtk.formatTemperatureString(temp, target)))
