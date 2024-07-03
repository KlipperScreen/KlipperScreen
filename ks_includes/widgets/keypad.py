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

        self.labels['entry'] = Gtk.Entry(hexpand=True, xalign=0.5, max_length=5)
        self.labels['entry'].connect("activate", self.keypad_clicked, "E")
        self.labels['entry'].connect('changed', self.on_changed)

        close = self._gtk.Button('cancel', scale=.66)
        close.set_hexpand(False)
        close.set_vexpand(False)
        close.connect("clicked", close_function)

        self.top_box = Gtk.Box(spacing=5)
        self.top_box.add(self.labels["entry"])
        self.top_box.add(close)

        numpad = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
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
            ['.', 'numpad_bright']
        ]
        for i in range(len(keys)):
            k_id = f'button_{str(keys[i][0])}'
            if keys[i][0] == "B":
                self.labels[k_id] = self._gtk.Button("backspace", scale=.66, style="numpad_key")
            else:
                self.labels[k_id] = self._gtk.Button(label=keys[i][0], style="numpad_key")
            self.labels[k_id].connect('clicked', self.keypad_clicked, keys[i][0])
            self.labels[k_id].get_style_context().add_class(keys[i][1])
            numpad.attach(self.labels[k_id], i % 3, i // 3, 1, 1)

        self.labels["keypad"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        ok = self._gtk.Button('complete', style="color1", scale=1.1)
        if self.screen.vertical_mode:
            ok.set_size_request(-1, self._gtk.font_size * 4)
        else:
            ok.set_size_request(-1, self._gtk.font_size * 5)
        ok.connect('clicked', self.keypad_clicked, "E")
        ok.set_vexpand(False)

        self.pid = self._gtk.Button(
            'heat-up', _('Calibrate') + ' PID', "color2", self._gtk.bsidescale, Gtk.PositionType.LEFT, 1
        )
        self.pid.set_vexpand(False)
        self.pid.connect("clicked", self.keypad_clicked, "PID")
        self.pid.set_sensitive(False)
        self.pid.set_no_show_all(True)

        self.add(self.top_box)
        self.add(numpad)
        self.bottom = Gtk.Box()
        self.bottom.add(self.pid)
        self.bottom.add(ok)
        self.add(self.bottom)

        self.labels["keypad"] = numpad

    def show_pid(self, can_pid):
        self.pid.set_visible(can_pid)

    def clear(self):
        self.labels['entry'].set_text("")

    def keypad_clicked(self, widget, digit):
        if digit == 'B':
            self.labels['entry'].do_backspace(self.labels['entry'])
        elif digit in ('E', 'PID'):
            temp = self.validate_temp(self.labels['entry'].get_text())
            self.clear()
            if temp is None:
                self.screen.show_popup_message(_("Invalid temperature"))
                return
            if digit == 'PID':
                self.pid_calibrate(temp)
            elif digit == 'E':
                self.change_temp(temp)
        else:
            self.labels['entry'].do_insert_at_cursor(self.labels['entry'], digit)

    def on_changed(self, *args):
        new_temp = self.validate_temp(self.labels['entry'].get_text())
        self.pid.set_sensitive(new_temp is not None and new_temp > 9)

    @staticmethod
    def validate_temp(temp):
        try:
            return float(temp)
        except ValueError:
            return None
