import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class PrintListItem(Gtk.FlowBoxChild):
    def __init__(self):
        super().__init__()
        self.date = None
        self.size = None
        self.dir = 0
        self.path = None

    def set_date(self, date):
        self.date = date

    def set_size(self, size):
        self.size = size

    def set_as_dir(self, is_dir: bool):
        self.dir = -1 if is_dir else 0

    def set_path(self, path):
        self.path = path

    def get_date(self):
        return self.date

    def get_size(self):
        return self.size

    def get_is_dir(self):
        return self.dir

    def get_path(self):
        return self.path
