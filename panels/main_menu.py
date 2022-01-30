import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from panels.menu import MenuPanel

def create_panel(*args):
    return MainPanel(*args)

class MainPanel(MenuPanel):
    def __init__(self, screen, title, back=False):
        super().__init__(screen, title, False)

    def initialize(self, panel_name, items, extrudercount):
        print("### Making MainMenu")

        grid = self._gtk.HomogeneousGrid()
        grid.set_hexpand(True)
        grid.set_vexpand(True)

        self.items = items
        self.create_menu_items()

        self.grid = Gtk.Grid()
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(True)

        self.labels['menu'] = self.arrangeMenuItems(items, 4, True)
        grid.attach(self.labels['menu'], 0, 0, 1, 1)

        self.grid = grid

        self.content.add(self.grid)
        self.layout.show_all()

    def activate(self):
        return
