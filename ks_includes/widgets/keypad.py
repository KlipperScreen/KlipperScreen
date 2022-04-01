import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class Keypad(Gtk.Box):
    def __init__(self, screen, change_temp, close_function):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        _ = screen.lang.gettext
        self.labels = {}
        self.change_temp = change_temp
        self.screen = screen
        self._gtk = screen.gtk

        numpad = self._gtk.HomogeneousGrid()
        numpad.set_direction(Gtk.TextDirection.LTR)

        keys = [
            ['1', 'numpad_tleft'],
            ['2', 'numpad_top'],
            ['3', 'numpad_tright'],
            ['4', 'numpad_left'],
            ['5', 'numpad_button'],
            ['6', 'numpad_right'],
            ['7', 'numpad_left'],
            ['8', 'numpad_button'],
            ['9', 'numpad_right'],
            ['B', 'numpad_bleft'],
            ['0', 'numpad_bottom'],
            ['E', 'numpad_bright']
        ]
        for i in range(len(keys)):
            id = 'button_' + str(keys[i][0])
            if keys[i][0] == "B":
                self.labels[id] = self._gtk.ButtonImage("backspace", None, None, 1)
            elif keys[i][0] == "E":
                self.labels[id] = self._gtk.ButtonImage("complete", None, None, 1)
            else:
                self.labels[id] = Gtk.Button(keys[i][0])
            self.labels[id].connect('clicked', self.update_entry, keys[i][0])
            self.labels[id].get_style_context().add_class(keys[i][1])
            numpad.attach(self.labels[id], i % 3, i/3, 1, 1)

        self.labels["keypad"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['entry'] = Gtk.Entry()
        self.labels['entry'].props.xalign = 0.5
        self.labels['entry'].connect("activate", self.update_entry, "E")

        b = self._gtk.ButtonImage('cancel', _('Close'), None, 1)
        b.connect("clicked", close_function)

        self.add(self.labels['entry'])
        self.add(numpad)
        self.add(b)

        self.labels["keypad"] = numpad

    def clear(self):
        self.labels['entry'].set_text("")

    def update_entry(self, widget, digit):
        text = self.labels['entry'].get_text()
        if digit == 'B':
            if len(text) < 1:
                return
            self.labels['entry'].set_text(text[0:-1])
        elif digit == 'E':
            try:
                temp = int(text)
            except ValueError:
                temp = 0
            self.change_temp(temp)
            self.labels['entry'].set_text("")
        else:
            if len(text) >= 3:
                return
            self.labels['entry'].set_text(text + digit)
