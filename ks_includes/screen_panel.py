import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from jinja2 import Environment, Template

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.KlippyGcodes import KlippyGcodes

class ScreenPanel:
    title_spacing = 50
    control = {}

    def __init__(self, screen, title, back=True, action_bar=True, printer_name=True):
        self._screen = screen
        self._config = screen._config
        self._files = screen.files
        self.lang = self._screen.lang
        self._printer = screen.printer
        self.labels = {}
        self._gtk = screen.gtk

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)

        action_bar_width = self._gtk.get_action_bar_width() if action_bar == True else 0

        if action_bar == True:
            self.control_grid = self._gtk.HomogeneousGrid()
            self.control_grid.set_size_request(action_bar_width - 2, self._screen.height)
            self.control_grid.get_style_context().add_class('action_bar')

            button_scale = self._gtk.get_header_image_scale()
            logging.debug("Button scale: %s" % button_scale)

            if back == True:
                self.control['back'] = self._gtk.ButtonImage('back', None, None, button_scale[0], button_scale[1])
                self.control['back'].connect("clicked", self._screen._menu_go_back)
                self.control_grid.attach(self.control['back'], 0, 0, 1, 1)

                self.control['home'] = self._gtk.ButtonImage('main', None, None, button_scale[0], button_scale[1])
                self.control['home'].connect("clicked", self.menu_return, True)
                self.control_grid.attach(self.control['home'], 0, 1, 1, 1)
            else:
                for i in range(2):
                    self.control['space%s' % i] = Gtk.Label("")
                    self.control_grid.attach(self.control['space%s' % i], 0, i, 1, 1)

            if len(self._config.get_printers()) > 1:
                self.control['printer_select'] = self._gtk.ButtonImage(
                    'shuffle', None, None, button_scale[0], button_scale[1])
                self.control['printer_select'].connect("clicked", self._screen.show_printer_select)
            else:
                self.control['printer_select'] = Gtk.Label("")
            self.control_grid.attach(self.control['printer_select'], 0, 2, 1, 1)

            self.control['estop'] = self._gtk.ButtonImage('emergency', None, None, button_scale[0], button_scale[1])
            self.control['estop'].connect("clicked", self.emergency_stop)
            self.control_grid.attach(self.control['estop'], 0, 3, 1, 1)
            #self.layout.put(self.control['estop'], int(self._screen.width/4*3 - button_scale[0]/2), 0)

        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except:
            logging.debug("Error parsing jinja for title: %s" % title)

        self.title = Gtk.Label()
        self.title.set_size_request(self._screen.width - action_bar_width, self.title_spacing)
        self.title.set_hexpand(True)
        self.title.set_halign(Gtk.Align.CENTER)
        self.title.set_valign(Gtk.Align.CENTER)
        if printer_name == True:
            self.set_title("%s | %s" % (self._screen.connected_printer, title))
        else:
            self.set_title(title)

        self.content = Gtk.Box(spacing=0)
        self.content.set_size_request(self._screen.width - action_bar_width, self._screen.height - self.title_spacing)

        if action_bar == True:
            self.layout.put(self.control_grid, 0, 0)
        self.layout.put(self.title, action_bar_width, 0)
        self.layout.put(self.content, action_bar_width, self.title_spacing)


    def initialize(self, panel_name):
        # Create gtk items here
        return

    def emergency_stop(self, widget):
        self._screen._ws.klippy.emergency_stop()

    def get(self):
        return self.layout

    def get_file_image(self, filename, width=1.6, height=1.6):
        if not self._files.has_thumbnail(filename):
            return None

        loc = self._files.get_thumbnail_location(filename)
        if loc == None:
            return None
        if loc[0] == "file":
            return self._gtk.PixbufFromFile(loc[1], None, width, height)
        if loc[0] == "http":
            return self._gtk.PixbufFromHttp(loc[1], None, width, height)
        return None

    def home(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

    def menu_item_clicked(self, widget, panel, item):
        print("### Creating panel "+ item['panel'] + " : %s %s" % (panel, item))
        if "items" in item:
            self._screen.show_panel(self._screen._cur_panels[-1] + '_' + panel, item['panel'], item['name'],
                1, False, items=item['items'])
            return
        self._screen.show_panel(self._screen._cur_panels[-1] + '_' + panel, item['panel'], item['name'],
            1, False)

    def menu_return(self, widget, home=False):
        if home == False:
            self._screen._menu_go_back()
            return
        self._screen._menu_go_home()

    def set_title(self, title):
        self.title.set_label(title)

    def show_all(self):
        self._screen.show_all()

    def update_image_text(self, label, text):
        if label in self.labels and 'l' in self.labels[label]:
            self.labels[label]['l'].set_text(text)

    def update_temp(self, dev, temp, target, name=None):
        if dev in self.labels:
            if name == None:
                self.labels[dev].set_label(self._gtk.formatTemperatureString(temp, target))
            else:
                self.labels[dev].set_label("%s\n%s" % (name, self._gtk.formatTemperatureString(temp, target)))
