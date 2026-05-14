import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class Keypad(Gtk.Box):
    def __init__(self, screen, ok_cb, cancel_cb, entry_max=5, error_msg=_("Invalid Number")):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.screen = screen
        self._gtk = screen.gtk
        self.ok_cb = ok_cb
        self.error_msg = error_msg
        self.has_extra_button = False

        # Header: Entry + Close
        self.entry = Gtk.Entry(hexpand=True, xalign=0.5, max_length=entry_max)
        self.entry.connect("activate", self._on_keypad_clicked, "E")

        close_btn = self._gtk.Button('cancel', scale=.66)
        close_btn.set_hexpand(False)
        close_btn.set_vexpand(False)
        close_btn.connect("clicked", cancel_cb)

        self.top_box = Gtk.Box(spacing=5)
        self.top_box.add(self.entry)
        self.top_box.add(close_btn)

        # Grid construction
        numpad = self._build_numpad()

        # Bottom Actions
        self.action_box = Gtk.Box(spacing=5)

        self.ok_btn = self._gtk.Button("complete", style="color1", scale=1.1)
        self.ok_btn.set_vexpand(False)
        self.ok_btn.set_size_request(-1, self._gtk.font_size * (4 if self.screen.vertical_mode else 5))
        self.ok_btn.connect('clicked', self._on_keypad_clicked, "E")

        self.action_box.pack_end(self.ok_btn, True, True, 0)

        # Main Layout
        self.add(self.top_box)
        self.add(numpad)
        self.add(self.action_box)

    def _build_numpad(self):
        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        grid.get_style_context().add_class('numpad')

        keys = [
            ('1', 'numpad_tleft'), ('2', 'numpad_top'), ('3', 'numpad_tright'),
            ('4', 'numpad_left'), ('5', 'numpad_button'), ('6', 'numpad_right'),
            ('7', 'numpad_left'), ('8', 'numpad_button'), ('9', 'numpad_right'),
            ('B', 'numpad_bleft'), ('0', 'numpad_bottom'), ('.', 'numpad_bright')
        ]

        for i, (label, css_class) in enumerate(keys):
            if label == "B":
                btn = self._gtk.Button("backspace", scale=.66, style="numpad_key")
            else:
                btn = self._gtk.Button(label=label, style="numpad_key")

            btn.connect('clicked', self._on_keypad_clicked, label)
            btn.get_style_context().add_class(css_class)
            grid.attach(btn, i % 3, i // 3, 1, 1)
        return grid

    def add_extra_button(self, callback, icon=None, label=""):
        if self.has_extra_button:
            return
        self.has_extra_button = True
        btn = self._gtk.Button(icon, label, "color2", self._gtk.bsidescale, Gtk.PositionType.LEFT, 1)
        btn.connect("clicked", lambda w: self._handle_extra_action(callback))
        self.action_box.pack_start(btn, True, True, 0)
        btn.set_vexpand(False)
        self.action_box.show_all()
        return btn

    def _handle_extra_action(self, callback):
        value = self.get_value() or 0
        if isinstance(value, (int, float)):
            callback(value)

    def _on_keypad_clicked(self, widget, digit):
        if digit == 'B':
            self.entry.do_backspace(self.entry)
        elif digit == 'E':
            val = self.get_value()
            if val is not None:
                self.ok_cb(val)
                self.clear()
            else:
                self.screen.show_popup_message(self.error_msg)
        else:
            self.entry.do_insert_at_cursor(self.entry, digit)

    def get_value(self):
        try:
            return float(self.entry.get_text())
        except ValueError:
            return None

    def clear(self):
        self.entry.set_text("")
