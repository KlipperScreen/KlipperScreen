import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from jinja2 import Environment, Template

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

class BasePanel(ScreenPanel):
    def __init__(self, screen, title, back=True, action_bar=True, printer_name=True):
        super().__init__(screen, title, back, action_bar, printer_name)
        self.current_panel = None

        self.buttons_showing = {
            'back': False if back else True
        }

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)

        action_bar_width = self._gtk.get_action_bar_width() if action_bar == True else 0

        self.control_grid = self._gtk.HomogeneousGrid()
        self.control_grid.set_size_request(action_bar_width - 2, self._screen.height)
        self.control_grid.get_style_context().add_class('action_bar')

        button_scale = self._gtk.get_header_image_scale()
        logging.debug("Button scale: %s" % button_scale)

        self.control['back'] = self._gtk.ButtonImage('back', None, None, button_scale[0], button_scale[1])
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = self._gtk.ButtonImage('main', None, None, button_scale[0], button_scale[1])
        self.control['home'].connect("clicked", self.menu_return, True)

        #if back == True:
        #    self.control_grid.attach(self.control['back'], 0, 0, 1, 1)
        #    self.control_grid.attach(self.control['home'], 0, 1, 1, 1)
        #else:
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

        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except:
            logging.debug("Error parsing jinja for title: %s" % title)

        self.titlelbl = Gtk.Label()
        self.titlelbl.set_size_request(self._screen.width - action_bar_width, self.title_spacing)
        self.titlelbl.set_hexpand(True)
        self.titlelbl.set_halign(Gtk.Align.CENTER)
        self.titlelbl.set_valign(Gtk.Align.CENTER)
        self.set_title(title)

        self.content = Gtk.Box(spacing=0)
        self.content.set_size_request(self._screen.width - action_bar_width, self._screen.height - self.title_spacing)

        if action_bar == True:
            self.layout.put(self.control_grid, 0, 0)
        self.layout.put(self.titlelbl, action_bar_width, 0)
        self.layout.put(self.content, action_bar_width, self.title_spacing)

    def initialize(self, panel_name):
        # Create gtk items here
        return

    def add_content(self, panel):
        self.current_panel = panel
        self.set_title(panel.get_title())
        self.content.add(panel.get_content())

    def back(self, widget):
        if self.current_panel == None:
            return

        if hasattr(self.current_panel, "back"):
            if not self.current_panel.back():
                self._screen._menu_go_back()
        else:
            self._screen._menu_go_back()

    def get(self):
        return self.layout

    def remove(self, widget):
        self.content.remove(widget)

    def show_back(self, show=True):
        if show == True and self.buttons_showing['back'] == False:
            self.control_grid.remove(self.control_grid.get_child_at(0,0))
            self.control_grid.attach(self.control['back'], 0, 0, 1, 1)
            self.control_grid.remove(self.control_grid.get_child_at(0,1))
            self.control_grid.attach(self.control['home'], 0, 1, 1, 1)
            self.buttons_showing['back'] = True
        elif show == False and self.buttons_showing['back'] == True:
            for i in range(0,2):
                self.control_grid.remove(self.control_grid.get_child_at(0,i))
                self.control_grid.attach(self.control['space%s' % i], 0, i, 1, 1)
            self.buttons_showing['back'] = False
        self.control_grid.show()

    def set_title(self, title):
        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except:
            logging.debug("Error parsing jinja for title: %s" % title)

        self.titlelbl.set_label("%s | %s" % (self._screen.connected_printer, title))

    def show_back_buttons(self):
        self.control_grid.attach(self.control['back'], 0, 0, 1, 1)
        self.control_grid.attach(self.control['home'], 0, 1, 1, 1)
