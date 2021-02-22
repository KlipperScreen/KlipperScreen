import gettext
import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from jinja2 import Environment, Template

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return MenuPanel(*args)

class MenuPanel(ScreenPanel):
    i = 0
    def initialize(self, panel_name, display_name, items):
        _ = self.lang.gettext

        self.items = items
        self.create_menu_items()

        self.grid = Gtk.Grid()
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(True)
        self.content.add(self.grid)

    def activate(self):
        self.j2_data = self._printer.get_printer_status_data()
        self.j2_data.update({
            'moonraker_connected': self._screen._ws.is_connected()
        })
        self.arrangeMenuItems(self.items, 4)

    def arrangeMenuItems (self, items, columns, expandLast=False):
        for child in self.grid.get_children():
            self.grid.remove(child)

        l = len(items)
        i = 0
        for item in items:
            key = list(item)[0]
            logging.debug("Evaluating item: %s" % key)
            if not self.evaluate_enable(item[key]['enable']):
                continue

            col = i % columns
            row = int(i/columns)
            width = 1

            if expandLast == True and i+1 == l and l%2 == 1:
                width = 2

            self.grid.attach(self.labels[key], col, row, width, 1)
            i += 1

        return self.grid

    def create_menu_items(self):
        for i in range(len(self.items)):
            key = list(self.items[i])[0]
            item = self.items[i][key]

            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(item['name'])
            parsed_name = j2_temp.render()

            b = self._gtk.ButtonImage(
                item['icon'], parsed_name, "color"+str((i%4)+1)
            )
            if item['panel'] != False:
                b.connect("clicked", self.menu_item_clicked, item['panel'], item)
            elif item['method'] != False:
                params = item['params'] if item['params'] != False else {}
                if item['confirm'] != False:
                    b.connect("clicked", self._screen._confirm_send_action, item['confirm'], item['method'], params)
                else:
                    b.connect("clicked", self._screen._send_action, item['method'], params)
            else:
                b.connect("clicked", self._screen._go_to_submenu, key)
            self.labels[key] = b

    def evaluate_enable(self, enable):
        if enable == True:
            return True
        if enable == False:
            return False

        try:
            logging.debug("Template: '%s'" % enable)
            logging.debug("Data: %s" % self.j2_data)
            j2_temp = Template(enable)
            result = j2_temp.render(self.j2_data)
            if result == 'True':
                return True
            return False
        except:
            logging.debug("Error evaluating enable statement: %s", enable)
            return False
