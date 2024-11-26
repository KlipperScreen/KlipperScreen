import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


class Keyboard(Gtk.Box):
    langs = ["de", "en", "fr", "es"]

    def __init__(self, screen, close_cb, entry=None, box=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.shift = []
        self.shift_active = False
        self.close_cb = close_cb
        self.keyboard = Gtk.Grid()
        self.keyboard.set_direction(Gtk.TextDirection.LTR)
        self.timeout = self.clear_timeout = None
        self.entry = entry
        self.purpose = self.entry.get_input_purpose()
        self.box = box or None

        language = self.detect_language(screen._config.get_main_config().get("language", None))

        if self.purpose == Gtk.InputPurpose.DIGITS:
            self.keys = [
                [
                    ["7", "8", "9"],
                    ["4", "5", "6"],
                    ["1", "2", "3"],
                    ["↓", "0", "⌫"]
                ]
            ]
        elif self.purpose == Gtk.InputPurpose.NUMBER:
            self.keys = [
                [
                    ["7", "8", "9", "⌫"],
                    ["4", "5", "6", "+"],
                    ["1", "2", "3", "-"],
                    ["↓", "0", ".", "↓"]
                ]
            ]
        elif language == "de":
            self.keys = [
                [
                    ["q", "w", "e", "r", "t", "z", "u", "i", "o", "p", "ü"],
                    ["a", "s", "d", "f", "g", "h", "j", "k", "l", "ö", "ä"],
                    ["↑", "y", "x", "c", "v", "b", "n", "m", "ẞ", "#+=", "⌫"],
                    ["123", " ", "↓"],
                ],
                [
                    ["Q", "W", "E", "R", "T", "Z", "U", "I", "O", "P", "Ü"],
                    ["A", "S", "D", "F", "G", "H", "J", "K", "L", "Ö", "Ä"],
                    ["↑", "Y", "X", "C", "V", "B", "N", "M", "ß", "#+=", "⌫"],
                    ["123", " ", "↓"],
                ],
                [
                    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
                    ["@", "#", "$", "_", "&", "-", "+", "(", ")", "/"],
                    ["↑", "*", '"', "'", ":", ";", "!", "?", "#+=", "⌫"],
                    ["abc", " ", "↓"],
                ],
                [
                    ["[", "]", "{", "}", "#", "%", "^", "*", "+", "="],
                    ["_", "\\", "|", "~", "<", ">", "€", "£", "¥", "•"],
                    ["↑", ".", ",", "?", "!", "'", "º", "¨", "123", "⌫"],
                    ["ABC", " ", "↓"],
                ]
            ]
        elif language == "fr":
            self.keys = [
                [
                    ["a", "z", "e", "r", "t", "y", "u", "i", "o", "p"],
                    ["q", "s", "d", "f", "g", "h", "j", "k", "l", "m"],
                    ["↑", "w", "x", "c", "v", "b", "n", "ç", "#+=", "⌫"],
                    ["123", " ", "↓"],
                ],
                [
                    ["A", "Z", "E", "R", "T", "Y", "U", "I", "O", "P"],
                    ["Q", "S", "D", "F", "G", "H", "J", "K", "L", "M"],
                    ["↑", "W", "X", "C", "V", "B", "N", "Ç", "#+=", "⌫"],
                    ["123", " ", "↓"],
                ],
                [
                    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
                    ["@", "#", "$", "_", "&", "-", "+", "(", ")", "/"],
                    ["↑", "*", '"', "'", ":", ";", "!", "?", "ABC", "⌫"],
                    ["abc", " ", "↓"],
                ],
                [
                    ["[", "]", "{", "}", "#", "%", "^", "*", "+", "="],
                    ["_", "\\", "|", "~", "<", ">", "€", "£", "¥", "•"],
                    ["↑", ".", ",", "?", "!", "'", "º", "Æ", "æ", "⌫"],
                    ["ABC", " ", "↓"],
                ]
            ]
        else:
            self.keys = [
                [
                    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
                    ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
                    ["↑", "z", "x", "c", "v", "b", "n", "m", "#+=", "⌫"],
                    ["123", " ", "↓"],
                ],
                [
                    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
                    ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
                    ["↑", "Z", "X", "C", "V", "B", "N", "M", "#+=", "⌫"],
                    ["123", " ", "↓"],
                ],
                [
                    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
                    ["@", "#", "$", "_", "&", "-", "+", "(", ")", "/"],
                    ["↑", "*", '"', "'", ":", ";", "!", "?", "Ç", "⌫"],
                    ["abc", " ", "↓"],
                ],
                [
                    ["[", "]", "{", "}", "#", "%", "^", "*", "+", "="],
                    ["_", "\\", "|", "~", "<", ">", "€", "£", "¥", "•"],
                    ["↑", ".", ",", "?", "!", "'", "º", "ç", "abc", "⌫"],
                    ["ABC", " ", "↓"],
                ]
            ]

            if language == "es":
                self.keys[0][1].append("ñ")
                self.keys[1][1].append("Ñ")

        self.buttons = self.keys.copy()
        for p, pallet in enumerate(self.keys):
            for r, row in enumerate(pallet):
                for k, key in enumerate(row):
                    if key == "⌫":
                        self.buttons[p][r][k] = screen.gtk.Button("backspace", scale=.6)
                    elif key == "↑":
                        self.buttons[p][r][k] = screen.gtk.Button("arrow-up", scale=.6)
                        self.shift.append(self.buttons[p][r][k])
                    elif key == "↓":
                        self.buttons[p][r][k] = screen.gtk.Button("arrow-down", scale=.6)
                    else:
                        self.buttons[p][r][k] = screen.gtk.Button(label=key, lines=1)
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
        columns = 0

        if self.purpose in (Gtk.InputPurpose.DIGITS, Gtk.InputPurpose.NUMBER):
            for r, row in enumerate(self.keys[p]):
                for k, key in enumerate(row):
                    x = k * 2
                    self.keyboard.attach(self.buttons[p][r][k], x, r, 2, 1)
                    if x > columns:
                        columns = x
            self.show_all()
            return

        for r, row in enumerate(self.keys[p][:-1]):
            for k, key in enumerate(row):
                x = k * 2 + 1 if r == 1 else k * 2
                self.keyboard.attach(self.buttons[p][r][k], x, r, 2, 1)
                if x > columns:
                    columns = x
        self.keyboard.attach(self.buttons[p][3][0], 0, 4, 3, 1)  # 123
        self.keyboard.attach(self.buttons[p][3][1], 3, 4, -4 + columns, 1)  # Space
        self.keyboard.attach(self.buttons[p][3][2], -1 + columns, 4, 3, 1)  # ↓
        self.show_all()

    def repeat(self, widget, event, key):
        # Button-press
        widget.get_style_context().add_class("active")
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
        if widget not in self.shift:
            widget.get_style_context().remove_class("active")

    def clear(self, widget=None):
        self.entry.set_text("")
        if self.clear_timeout is not None:
            GLib.source_remove(self.clear_timeout)
            self.clear_timeout = None

    def update_entry(self, widget, key):
        if key == "⌫":
            Gtk.Entry.do_backspace(self.entry)
        elif key == "↓":
            self.close_cb(entry=self.entry, box=self.box)
            return
        elif key == "↑":
            self.toggle_shift()
            if self.pallet_nr == 0:
                self.set_pallet(1)
            elif self.pallet_nr == 1:
                self.set_pallet(0)
            elif self.pallet_nr == 2:
                self.set_pallet(3)
            elif self.pallet_nr == 3:
                self.set_pallet(2)
            return
        elif key == "abc":
            if self.shift_active:
                self.toggle_shift()
            widget.get_style_context().remove_class("active")
            self.set_pallet(0)
        elif key == "ABC":
            if not self.shift_active:
                self.toggle_shift()
            widget.get_style_context().remove_class("active")
            self.set_pallet(1)
        elif key == "123":
            if self.shift_active:
                self.toggle_shift()
            widget.get_style_context().remove_class("active")
            self.set_pallet(2)
        elif key == "#+=":
            if not self.shift_active:
                self.toggle_shift()
            widget.get_style_context().remove_class("active")
            self.set_pallet(3)
        else:
            Gtk.Entry.do_insert_at_cursor(self.entry, key)

    def toggle_shift(self):
        self.shift_active = not self.shift_active
        widget: Gtk.Widget
        for widget in self.shift:
            if self.shift_active:
                widget.get_style_context().add_class("active")
            else:
                widget.get_style_context().remove_class("active")
