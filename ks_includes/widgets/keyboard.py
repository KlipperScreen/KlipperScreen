import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


class Keyboard(Gtk.Box):
    def __init__(self, screen, close_cb, entry=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._gtk = screen.gtk
        self.close_cb = close_cb
        self.keyboard = Gtk.Grid()
        self.keyboard.set_direction(Gtk.TextDirection.LTR)
        self.timeout = self.clear_timeout = None
        self.entry = entry

        self.keys = [
            [["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "⌫"],
             ["a", "s", "d", "f", "g", "h", "j", "k", "l", "'"],
             ["ABC", "z", "x", "c", "v", "b", "n", "m", ",", ".", "?123"],
             ["✕", " ", "✔"]
             ],
            [["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "⌫"],
             ["A", "S", "D", "F", "G", "H", "J", "K", "L", "'"],
             ["?123", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "abc"],
             ["✕", " ", "✔"]
             ],
            [["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "⌫"],
             ["=", "-", "+", "*", "/", "\\", ":", ";", "'", "\""],
             ["abc", "(", ")", "#", "$", "!", "?", "@", "_", ",", "ABC"],
             ["✕", " ", "✔"]
             ]
        ]

        self.labels = self.keys.copy()
        for p, pallet in enumerate(self.keys):
            for r, row in enumerate(pallet):
                for k, key in enumerate(row):
                    self.labels[p][r][k] = self._gtk.Button(key)
                    self.labels[p][r][k].set_hexpand(True)
                    self.labels[p][r][k].set_vexpand(True)
                    self.labels[p][r][k].connect('button-press-event', self.repeat, key)
                    self.labels[p][r][k].connect('button-release-event', self.release)
                    self.labels[p][r][k].get_style_context().add_class("keyboard_pad")

        self.pallet_nr = 0
        self.set_pallet(self.pallet_nr)
        self.add(self.keyboard)

    def set_pallet(self, p):
        pallet = self.keys[p]
        span = 2
        for r, row in enumerate(pallet[:-1]):
            for k, key in enumerate(row):
                x = k * 2 + 1 if r == 1 else k * 2
                old = self.keyboard.get_child_at(x, r)
                if old:
                    self.keyboard.remove(old)
                self.keyboard.attach(self.labels[p][r][k], x, r, span, 1)
        if not self.keyboard.get_child_at(0, 4):
            self.keyboard.attach(self.labels[p][3][0], 0, 4, 3, 1)
            self.keyboard.attach(self.labels[p][3][1], 3, 4, 16, 1)
            self.keyboard.attach(self.labels[p][3][2], 19, 4, 3, 1)
        self.show_all()

    def repeat(self, widget, event, key):
        # Button-press
        self.update_entry(widget, key)
        if self.timeout is None and key == "⌫":
            # Hold for repeat, hold longer to clear the field
            self.clear_timeout = GLib.timeout_add_seconds(3, self.clear, widget)
            # This can be used to repeat all the keys,
            # but I don't find it useful on the console
            self.timeout = GLib.timeout_add(400, self.repeat, widget, None, key)
        return True

    def release(self, widget, event):
        # Button-release
        if self.timeout is not None:
            GLib.source_remove(self.timeout)
            self.timeout = None
        if self.clear_timeout is not None:
            GLib.source_remove(self.clear_timeout)
            self.clear_timeout = None

    def clear(self, widget=None):
        self.entry.set_text("")
        if self.clear_timeout is not None:
            GLib.source_remove(self.clear_timeout)
            self.clear_timeout = None

    def update_entry(self, widget, key):
        if key == "⌫":
            Gtk.Entry.do_backspace(self.entry)
        elif key == "✔":
            self.close_cb()
            return
        elif key == "✕":
            self.clear()
            self.close_cb()
            return
        elif key == "abc":
            self.set_pallet(0)
        elif key == "ABC":
            self.set_pallet(1)
        elif key == "?123":
            self.set_pallet(2)
        else:
            Gtk.Entry.do_insert_at_cursor(self.entry, key)
