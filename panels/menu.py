import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from jinja2 import Environment, Template

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return MenuPanel(*args)


class MenuPanel(ScreenPanel):
    i = 0
    j2_data = None

    def initialize(self, panel_name, display_name, items):

        self.items = items
        self.create_menu_items()

        self.grid = self._gtk.HomogeneousGrid()

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.grid)

        self.content.add(scroll)

    def activate(self):
        self.j2_data = self._printer.get_printer_status_data()
        self.j2_data.update({
            'moonraker_connected': self._screen._ws.is_connected()
        })
        if self._screen.vertical_mode:
            self.arrangeMenuItems(self.items, 3)
        else:
            self.arrangeMenuItems(self.items, 4)

    def arrangeMenuItems(self, items, columns, expand_last=False):
        for child in self.grid.get_children():
            self.grid.remove(child)

        length = len(items)
        i = 0
        for item in items:
            key = list(item)[0]
            logging.debug(f"Evaluating item: {key}")
            if not self.evaluate_enable(item[key]['enable']):
                continue

            if columns == 4:
                if length <= 4:
                    # Arrange 2 x 2
                    columns = 2
                elif 4 < length <= 6:
                    # Arrange 3 x 2
                    columns = 3

            col = i % columns
            row = int(i / columns)

            width = height = 1
            if expand_last is True and i + 1 == length and length % 2 == 1:
                width = 2

            self.grid.attach(self.labels[key], col, row, width, height)
            i += 1

        return self.grid

    def create_menu_items(self):
        for i in range(len(self.items)):
            key = list(self.items[i])[0]
            item = self.items[i][key]

            env = Environment(extensions=["jinja2.ext.i18n"], autoescape=True)
            env.install_gettext_translations(self._config.get_lang())
            j2_temp = env.from_string(item['name'])
            parsed_name = j2_temp.render()

            b = self._gtk.ButtonImage(item['icon'], parsed_name, f"color{(i % 4) + 1}")
            if item['panel'] is not False:
                b.connect("clicked", self.menu_item_clicked, item['panel'], item)
            elif item['method'] is not False:
                params = item['params'] if item['params'] is not False else {}
                if item['confirm'] is not False:
                    b.connect("clicked", self._screen._confirm_send_action, item['confirm'], item['method'], params)
                else:
                    b.connect("clicked", self._screen._send_action, item['method'], params)
            else:
                b.connect("clicked", self._screen._go_to_submenu, key)
            self.labels[key] = b

    def evaluate_enable(self, enable):
        if enable is True:
            return True
        if enable is False:
            return False

        if enable == "{{ moonraker_connected }}":
            logging.info("moonraker is_connected %s", self._screen._ws.is_connected())
            return self._screen._ws.is_connected()

        self.j2_data = self._printer.get_printer_status_data()
        try:
            logging.debug(f"Template: '{enable}'")
            j2_temp = Template(enable, autoescape=True)
            result = j2_temp.render(self.j2_data)
            return result == 'True'
        except Exception as e:
            logging.debug(f"Error evaluating enable statement: {enable}\n{e}")
            return False
