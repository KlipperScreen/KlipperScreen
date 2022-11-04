import logging
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


class Keyboard(Gtk.Box):
    langs = ["de", "en", "es"]

    def __init__(self, screen, close_cb, entry=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.close_cb = close_cb
        self.keyboard = Gtk.Grid()
        self.keyboard.set_direction(Gtk.TextDirection.LTR)
        self.timeout = self.clear_timeout = None
        self.entry = entry

        language = self.detect_language(screen._config.get_main_config().get("language", None))
        logging.info(f"Keyboard {language}")

        if language == "de":
            self.keys = [
                [
                    ["q", "w", "e", "r", "t", "z", "u", "i", "o", "p", "ü", "⌫"],
                    ["a", "s", "d", "f", "g", "h", "j", "k", "l", "ö", "ä"],
                    ["ABC", "y", "x", "c", "v", "b", "n", "m", ",", ".", "?123"],
                ],
                [
                    ["Q", "W", "E", "R", "T", "Z", "U", "I", "O", "P", "Ü", "⌫"],
                    ["A", "S", "D", "F", "G", "H", "J", "K", "L", "Ö", "Ä"],
                    ["?123", "Y", "X", "C", "V", "B", "N", "M", ",", ".", "abc"],
                ],
                [
                    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "ß", "⌫"],
                    ["=", "-", "+", "*", "/", "\\", ":", ";", "'", "\"", "ẞ"],
                    ["abc", "(", ")", "#", "$", "!", "?", "@", "_", ",", "ABC"],
                ]
            ]
        else:
            self.keys = [
                [
                    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "⌫"],
                    ["a", "s", "d", "f", "g", "h", "j", "k", "l", "'"],
                    ["ABC", "z", "x", "c", "v", "b", "n", "m", ",", ".", "?123"],
                ],
                [
                    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "⌫"],
                    ["A", "S", "D", "F", "G", "H", "J", "K", "L", "'"],
                    ["?123", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "abc"],
                ],
                [
                    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "⌫"],
                    ["=", "-", "+", "*", "/", "\\", ":", ";", "'", "\""],
                    ["abc", "(", ")", "#", "$", "!", "?", "@", "_", ",", "ABC"],
                ]
            ]

            if language == "es":
                self.keys[0][1].remove("'")
                self.keys[0][1].append("ñ")
                self.keys[1][1].remove("'")
                self.keys[1][1].append("Ñ")

        for pallet in self.keys:
            pallet.append(["✕", " ", "✔"])

        self.buttons = self.keys.copy()
        for p, pallet in enumerate(self.keys):
            for r, row in enumerate(pallet):
                for k, key in enumerate(row):
                    if key == "⌫":
                        self.buttons[p][r][k] = screen.gtk.ButtonImage("backspace", scale=.6)
                    elif key == "✕":
                        self.buttons[p][r][k] = screen.gtk.ButtonImage("cancel", scale=.6)
                    elif key == "✔":
                        self.buttons[p][r][k] = screen.gtk.ButtonImage("complete", scale=.6)
                    else:
                        self.buttons[p][r][k] = screen.gtk.Button(key)
                    self.buttons[p][r][k].set_hexpand(True)
                    self.buttons[p][r][k].set_vexpand(True)
                    self.buttons[p][r][k].connect('button-press-event', self.repeat, key)
                    self.buttons[p][r][k].connect('button-release-event', self.release)
                    self.buttons[p][r][k].get_style_context().add_class("keyboard_pad")

        self.pallet_nr = 0
        self.set_pallet(self.pallet_nr)
        self.add(self.keyboard)

    def detect_language(self, language):
        if language is None or language == "system_lang":
            for language in self.langs:
                if os.getenv('LANG').lower().startswith(language):
                    return language
        for _ in self.langs:
            if language.startswith(_):
                return _
        return "en"

    def set_pallet(self, p):
        for _ in range(len(self.keys[self.pallet_nr]) + 1):
            self.keyboard.remove_row(0)
        self.pallet_nr = p
        for r, row in enumerate(self.keys[p][:-1]):
            for k, key in enumerate(row):
                x = k * 2 + 1 if r == 1 else k * 2
                self.keyboard.attach(self.buttons[p][r][k], x, r, 2, 1)
        self.keyboard.attach(self.buttons[p][3][0], 0, 4, 3, 1)  # ✕
        self.keyboard.attach(self.buttons[p][3][1], 3, 4, 16, 1)  # Space
        self.keyboard.attach(self.buttons[p][3][2], 19, 4, 3, 1)  # ✔
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
