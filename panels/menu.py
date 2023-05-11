import logging

import gi

import json

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from jinja2 import Environment, Template

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return MenuPanel(*args)


class MenuPanel(ScreenPanel):
    i = 0
    j2_data = None

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.items = []
        self.grid = self._gtk.HomogeneousGrid()

    def initialize(self, items):
        for item in items:
            key = next(iter(item))
            if self.evaluate_enable(item[key]['enable']):
                self.items.append(item)
            else:
                logging.debug(f"X > {key}")
        self.create_menu_items()
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.grid)
        self.content.add(scroll)

    def activate(self):
        if self._screen.vertical_mode:
            self.arrangeMenuItems(self.items, 3)
        else:
            self.arrangeMenuItems(self.items, 4)

    def arrangeMenuItems(self, items, columns, expand_last=False):
        for child in self.grid.get_children():
            self.grid.remove(child)

        length = len(items)
        for i, item in enumerate(items):
            key = list(item)[0]

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
        self.j2_data = None
        return self.grid

    def create_menu_items(self):
        for i in range(len(self.items)):
            key = list(self.items[i])[0]
            item = self.items[i][key]

            env = Environment(extensions=["jinja2.ext.i18n"], autoescape=True)
            env.install_gettext_translations(self._config.get_lang())

            printer = self._printer.get_printer_status_data()

            name = env.from_string(item['name']).render(printer)
            icon = env.from_string(item['icon']).render(printer) if item['icon'] else None
            style = env.from_string(item['style']).render(printer) if item['style'] else None

            b = self._gtk.Button(icon, name, style or f"color{i % 4 + 1}")

            if item['panel'] is not None:
                panel = env.from_string(item['panel']).render(printer)
                b.connect("clicked", self.menu_item_clicked, panel, item)
            elif item['method'] is not None:
                params = {}

                if item['params'] is not False:
                    try:
                        p = env.from_string(item['params']).render(printer)
                        params = json.loads(p)
                    except Exception as e:
                        logging.exception(f"Unable to parse parameters for [{name}]:\n{e}")
                        params = {}

                if item['confirm'] is not None:
                    b.connect("clicked", self._screen._confirm_send_action, item['confirm'], item['method'], params)
                else:
                    b.connect("clicked", self._screen._send_action, item['method'], params)
            else:
                b.connect("clicked", self._screen._go_to_submenu, key)
            self.labels[key] = b

    def evaluate_enable(self, enable):
        if enable == "{{ moonraker_connected }}":
            logging.info(f"moonraker connected {self._screen._ws.connected}")
            return self._screen._ws.connected
        elif enable == "{{ camera_configured }}":
            return self.ks_printer_cfg and self.ks_printer_cfg.get("camera_url", None) is not None
        self.j2_data = self._printer.get_printer_status_data()
        try:
            j2_temp = Template(enable, autoescape=True)
            result = j2_temp.render(self.j2_data)
            return result == 'True'
        except Exception as e:
            logging.debug(f"Error evaluating enable statement: {enable}\n{e}")
            return False
