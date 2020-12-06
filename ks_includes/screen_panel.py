import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.KlippyGcodes import KlippyGcodes
logger = logging.getLogger("KlipperScreen.ScreenPanel")

class ScreenPanel:
    title_spacing = 50
    control = {}

    def __init__(self, screen, title, back=True):
        self._screen = screen
        self._config = screen._config
        self.lang = self._screen.lang
        self._printer = screen.printer
        self.labels = {}
        self._gtk = screen.gtk

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)

        button_scale = self._gtk.get_header_image_scale()
        logger.debug("Button scale: %s" % button_scale)
        if back == True:
            self.control['back'] = self._gtk.ButtonImage('back', None, None, button_scale[0], button_scale[1])
            self.control['back'].connect("clicked", self._screen._menu_go_back)
            self.layout.put(self.control['back'], 0, 0)

            self.control['home'] = self._gtk.ButtonImage('home', None, None, button_scale[0], button_scale[1])
            self.control['home'].connect("clicked", self.menu_return, True)
            self.layout.put(self.control['home'], self._screen.width - round(
                self._gtk.get_image_width() * button_scale[0] * 1.45), 0)

        self.control['estop'] = self._gtk.ButtonImage('emergency', None, None, button_scale[0], button_scale[1])
        self.control['estop'].connect("clicked", self.emergency_stop)
        self.layout.put(self.control['estop'], int(self._screen.width/4*3 - button_scale[0]/2), 0)

        self.title = Gtk.Label()
        self.title.set_size_request(self._screen.width, self.title_spacing)
        self.title.set_hexpand(True)
        self.title.set_halign(Gtk.Align.CENTER)
        self.title.set_valign(Gtk.Align.CENTER)
        self.set_title(title)
        self.layout.put(self.title, 0, 0)

        self.content = Gtk.Box(spacing=0)
        self.content.set_size_request(self._screen.width, self._screen.height - self.title_spacing)
        self.layout.put(self.content, 0, self.title_spacing)


    def initialize(self, panel_name):
        # Create gtk items here
        return

    def emergency_stop(self, widget):
        self._screen._ws.klippy.emergency_stop()

    def get(self):
        return self.layout

    def home(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

    def menu_item_clicked(self, widget, panel, item):
        print("### Creating panel "+ item['panel'])
        if "items" in item:
            self._screen.show_panel(self._screen._cur_panels[-1] + '_' + item['name'], item['panel'], item['name'],
                1, False, items=item['items'])
            return
        self._screen.show_panel(self._screen._cur_panels[-1] + '_' + item['name'], item['panel'], item['name'],
            1, False)

    def menu_return(self, widget, home=False):
        if home == False:
            self._screen._menu_go_back()
            return
        self._screen._menu_go_home()

    def set_title(self, title):
        self.title.set_label(title)

    def update_image_text(self, label, text):
        if label in self.labels and 'l' in self.labels[label]:
            self.labels[label]['l'].set_text(text)

    def update_temp(self, dev, temp, target):
        if dev in self.labels:
            self.labels[dev].set_label(self._gtk.formatTemperatureString(temp, target))
