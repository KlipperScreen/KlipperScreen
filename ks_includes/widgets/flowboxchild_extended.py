import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk


class PrintListItem(Gtk.FlowBoxChild):
    def __init__(self):
        super().__init__()
        self.date = None
        self.size = None
        self.dir = False

    def set_date(self, date):
        self.date = date

    def set_size(self, size):
        self.size = size

    def set_as_dir(self, is_dir):
        self.dir = is_dir

    def get_date(self):
        return self.date

    def get_size(self):
        return self.size

    def is_dir(self):
        return self.dir
