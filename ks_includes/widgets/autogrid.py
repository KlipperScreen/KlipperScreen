import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class AutoGrid(Gtk.Grid):
    """
    A subclass of Gtk.Grid that auto-arranges its children on init

    Args:
        items (list): All the widgets to be arranged.
        max_columns (int: 4): The maximum number of columns, up to 4.
        expand_last (bool: False): expand the last widget to double width.
        vertical (bool: False): optimize for vertical orientation.

    Example:
        grid = Autogrid([Gtk.Button(), Gtk.Button()])
    """

    def __init__(self, items=None, max_columns=None, expand_last=False, vertical=False):
        super().__init__(row_homogeneous=True, column_homogeneous=True)
        if not max_columns:
            max_columns = 3 if vertical else 4
        self.expand_last = expand_last
        if not items:
            return
        length = len(items)
        if vertical and length < 4:
            # Arrange 1 x 4
            columns = 1
        elif length in {4, 2}:
            # Arrange 2 x 2
            columns = min(2, max_columns)
        elif length in {3, 5, 6}:
            # Arrange 3 x 2
            columns = min(3, max_columns)
        else:
            # Arrange 4 x n
            columns = min(4, max_columns)

        for i, widget in enumerate(items):
            col = i % columns
            row = int(i / columns)
            if self.expand_last and (i + 1) == length and length % 2 == 1:
                self.attach(widget, col, row, 2, 1)
            else:
                self.attach(widget, col, row, 1, 1)

    def clear(self):
        for i in self.get_children():
            self.remove(i)
