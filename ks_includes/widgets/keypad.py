import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class Keypad(Gtk.Box):
    def __init__(self, screen, change_temp, pid_calibrate, close_function):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.labels = {}
        self.change_temp = change_temp
        self.pid_calibrate = pid_calibrate
        self.screen = screen
        self._gtk = screen.gtk

        numpad = self._gtk.HomogeneousGrid()
        numpad.set_direction(Gtk.TextDirection.LTR)
        numpad.get_style_context().add_class('numpad')

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
            k_id = f'button_{str(keys[i][0])}'
            if keys[i][0] == "B":
                self.labels[k_id] = self._gtk.Button("backspace", scale=1)
            elif keys[i][0] == "E":
                self.labels[k_id] = self._gtk.Button("complete", scale=1)
            else:
                self.labels[k_id] = Gtk.Button(label=keys[i][0])
            self.labels[k_id].connect('clicked', self.update_entry, keys[i][0])
            self.labels[k_id].get_style_context().add_class(keys[i][1])
            numpad.attach(self.labels[k_id], i % 3, i / 3, 1, 1)

        self.labels["keypad"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['entry'] = Gtk.Entry()
        self.labels['entry'].props.xalign = 0.5
        self.labels['entry'].connect("activate", self.update_entry, "E")

        self.pid = self._gtk.Button('heat-up', _('Calibrate') + ' PID', None, .66, Gtk.PositionType.LEFT, 1)
        self.pid.connect("clicked", self.update_entry, "PID")
        self.pid.set_sensitive(False)
        self.pid.set_no_show_all(True)
        b = self._gtk.Button('cancel', _('Close'), None, .66, Gtk.PositionType.LEFT, 1)
        b.connect("clicked", close_function)

        self.add(self.labels['entry'])
        self.add(numpad)
        self.bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.bottom.add(self.pid)
        self.bottom.add(b)
        self.add(self.bottom)

        self.labels["keypad"] = numpad

    def show_pid(self, can_pid):
        self.pid.set_visible(can_pid)

    def clear(self):
        self.labels['entry'].set_text("")

    def update_entry(self, widget, digit):
        text = self.labels['entry'].get_text()
        temp = self.validate_temp(text)
        if digit == 'B':
            if len(text) < 1:
                return
            self.labels['entry'].set_text(text[:-1])
        elif digit == 'E':
            self.change_temp(temp)
            self.labels['entry'].set_text("")
        elif digit == 'PID':
            self.pid_calibrate(temp)
            self.labels['entry'].set_text("")
        elif len(text + digit) > 3:
            return
        else:
            self.labels['entry'].set_text(text + digit)
        self.pid.set_sensitive(self.validate_temp(self.labels['entry'].get_text()) > 9)

    @staticmethod
    def validate_temp(temp):
        try:
            return int(temp)
        except ValueError:
            return 0
