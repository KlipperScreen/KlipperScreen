import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from panels.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.MenuPanel")

class MenuPanel(ScreenPanel):
    def initialize(self, panel_name, items):
        print("### Making a new menu")

        grid = self.arrangeMenuItems(items, 4)

        b = KlippyGtk.ButtonImage('back', 'Back')
        b.connect("clicked", self._screen._menu_go_back)
        grid.attach(b, 3, 1, 1, 1)

        self.panel = grid

    def arrangeMenuItems (self, items, columns, expandLast=False):
        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)

        l = len(items)
        i = 0
        for i in range(l):
            col = i % columns
            row = int(i/columns)
            width = 1
            if expandLast == True and i+1 == l and l%2 == 1:
                width = 2
            b = KlippyGtk.ButtonImage(
                items[i]['icon'], items[i]['name'], "color"+str((i%4)+1)
            )

            if "panel" in items[i]:
                b.connect("clicked", self.menu_item_clicked, items[i]['panel'], items[i])
            elif "items" in items[i]:
                b.connect("clicked", self._screen._go_to_submenu, items[i]['name'])
            elif "method" in items[i]:
                params = items[i]['params'] if "params" in items[i] else {}
                b.connect("clicked", self._screen._send_action, items[i]['method'], params)

            grid.attach(b, col, row, width, 1)

            i += 1

        return grid
