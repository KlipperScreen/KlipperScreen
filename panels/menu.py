import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk

class MenuPanel:
    _screen = None
    labels = {}

    def __init__(self, screen):
        self._screen = screen


    def initialize(self, items):
        print "### Making a new menu"

        grid = self.arrangeMenuItems(items, 4)

        b = KlippyGtk.ButtonImage('back', 'Back')
        b.connect("clicked", self._screen._menu_go_back)
        grid.attach(b, 3, 1, 1, 1)

        self.grid = grid

    def get(self):
        return self.grid

    def arrangeMenuItems (self, items, columns, expandLast=False):
        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)

        l = len(items)
        i = 0
        for i in range(l):
            col = i % columns
            row = round(i/columns, 0)
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
        print b.get_style_context()
        print b.get_default_style()

        return grid

    def menu_item_clicked(self, widget, panel, item):
        print "### Creating panel "+ item['panel']
        if "items" in item:
            self._screen.show_panel("_".join(self._screen._cur_panels) + '_' + item['name'], item['panel'], 1, False, items=item['items'])
            return
        self._screen.show_panel("_".join(self._screen._cur_panels) + '_' + item['name'], item['panel'], 1, False)
        return
