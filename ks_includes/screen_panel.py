import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

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
        self.devices = {}
        self.active_heaters = []

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.get_style_context().add_class("content")
        self.content.set_hexpand(True)
        self.content.set_vexpand(True)

    def initialize(self, panel_name):
        # Create gtk items here
        return

    def emergency_stop(self, widget):

        if self._config.get_main_config().getboolean('confirm_estop'):
            self._screen._confirm_send_action(widget, _("Are you sure you want to run Emergency Stop?"),
                                              "printer.emergency_stop")
        else:
            self._screen._ws.klippy.emergency_stop()

    def format_target(self, temp):
        if temp <= 0:
            return ""
        else:
            return "(%s)" % str(int(temp))

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

    def get_file_image(self, filename, width=1, height=1, small=False):
        if not self._files.has_thumbnail(filename):
            return None

        loc = self._files.get_thumbnail_location(filename, small)
        if loc is None:
            return None
        if loc[0] == "file":
            return self._gtk.PixbufFromFile(loc[1], width, height)
        if loc[0] == "http":
            return self._gtk.PixbufFromHttp(loc[1], width, height)
        return None

    def get_title(self):
        return self.title

    def home(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME)

    def homexy(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME_XY)

    def z_tilt(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.Z_TILT)

    def quad_gantry_level(self, widget):
        self._screen._ws.klippy.gcode_script(KlippyGcodes.QUAD_GANTRY_LEVEL)

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
        if dev in self.labels and temp is not None:
            if name is None:
                self.labels[dev].set_label(self._gtk.formatTemperatureString(temp, target))
            else:
                self.labels[dev].set_label("%s\n%s" % (name, self._gtk.formatTemperatureString(temp, target)))

    def load_menu(self, widget, name):
        if ("%s_menu" % name) not in self.labels:
            return

        for child in self.content.get_children():
            self.content.remove(child)

        self.menu.append('%s_menu' % name)
        self.content.add(self.labels[self.menu[-1]])
        self.content.show_all()

    def unload_menu(self, widget=None):
        logging.debug("self.menu: %s" % self.menu)
        if len(self.menu) <= 1 or self.menu[-2] not in self.labels:
            return

        self.menu.pop()
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels[self.menu[-1]])
        self.content.show_all()

    def on_dropdown_change(self, combo, section, option, callback=None):
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            value = model[tree_iter][1]
            logging.debug("[%s] %s changed to %s" % (section, option, value))
            self._config.set(section, option, value)
            self._config.save_user_config_options()
            if callback is not None:
                callback(value)

    def scale_moved(self, widget, event, section, option):
        logging.debug("[%s] %s changed to %s" % (section, option, widget.get_value()))
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, option, str(int(widget.get_value())))
        self._config.save_user_config_options()

    def switch_config_option(self, switch, gparam, section, option, callback=None):
        logging.debug("[%s] %s toggled %s" % (section, option, switch.get_active()))
        if section not in self._config.get_config().sections():
            self._config.get_config().add_section(section)
        self._config.set(section, option, "True" if switch.get_active() else "False")
        self._config.save_user_config_options()
        if callback is not None:
            callback(switch.get_active())
