import re
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from datetime import datetime
from ks_includes.screen_panel import ScreenPanel


COLORS = {
    "command": "#bad8ff",
    "error": "#ff6975",
    "response": "#b8b8b8",
    "time": "grey",
    "warning": "#c9c9c9"
}


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Console")
        super().__init__(screen, title)
        self.autoscroll = True

        o1_button = self._gtk.Button("arrow-down", _("Auto-scroll") + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        o1_button.get_style_context().add_class("button_active")
        o1_button.get_style_context().add_class("buttons_slim")
        o1_button.connect("clicked", self.set_autoscroll)

        o2_button = self._gtk.Button("refresh", _('Clear') + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        o2_button.get_style_context().add_class("buttons_slim")
        o2_button.connect("clicked", self.clear)

        options = Gtk.Grid(vexpand=False)
        options.attach(o1_button, 0, 0, 1, 1)
        options.attach(o2_button, 1, 0, 1, 1)

        sw = Gtk.ScrolledWindow(hexpand=True, vexpand=True)

        tb = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=tb, editable=False, cursor_visible=False)
        tv.connect("size-allocate", self._autoscroll)
        tv.connect("focus-in-event", self._screen.remove_keyboard)

        sw.add(tv)

        ebox = Gtk.Box(hexpand=True, vexpand=False)

        entry = Gtk.Entry(hexpand=True, vexpand=False)
        entry.connect("button-press-event", self._screen.show_keyboard)
        entry.connect("focus-in-event", self._screen.show_keyboard)
        entry.connect("activate", self._send_command)
        entry.grab_focus_without_selecting()

        enter = self._gtk.Button("resume", " " + _('Send') + " ", None, .66, Gtk.PositionType.RIGHT, 1)
        enter.get_style_context().add_class("buttons_slim")

        enter.set_hexpand(False)
        enter.connect("clicked", self._send_command)

        ebox.add(entry)
        ebox.add(enter)

        self.labels.update({
            "entry": entry,
            "sw": sw,
            "tb": tb,
            "tv": tv
        })

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.pack_start(options, False, False, 5)
        content_box.add(sw)
        content_box.pack_end(ebox, False, False, 0)
        self.content.add(content_box)

    def clear(self, widget=None):
        self.labels['tb'].set_text("")

    def add_gcode(self, msgtype, msgtime, message):
        if msgtype == "command":
            color = COLORS['command']
        elif message.startswith("!!"):
            color = COLORS['error']
            message = message.replace("!! ", "")
        elif message.startswith("//"):
            color = COLORS['warning']
            message = message.replace("// ", "")
        elif re.match('^(?:ok\\s+)?(B|C|T\\d*):', message):
            return
        else:
            color = COLORS['response']

        message = f'<span color="{color}"><b>{message}</b></span>'

        message = message.replace('\n', '\n         ')

        self.labels['tb'].insert_markup(
            self.labels['tb'].get_end_iter(),
            f'\n<span color="{COLORS["time"]}">{datetime.fromtimestamp(msgtime).strftime("%H:%M:%S")}</span> {message}',
            -1
        )
        # Limit the length
        if self.labels['tb'].get_line_count() > 999:
            self.labels['tb'].delete(self.labels['tb'].get_iter_at_line(0), self.labels['tb'].get_iter_at_line(1))

    def gcode_response(self, result, method, params):
        if method != "server.gcode_store":
            return

        for resp in result['result']['gcode_store']:
            self.add_gcode(resp['type'], resp['time'], resp['message'])

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            self.add_gcode("response", time.time(), data)

    def set_autoscroll(self, widget):
        self.autoscroll ^= True
        self.toggle_active_class(widget, self.autoscroll)

    @staticmethod
    def toggle_active_class(widget, cond):
        if cond:
            widget.get_style_context().add_class("button_active")
        else:
            widget.get_style_context().remove_class("button_active")

    def _autoscroll(self, *args):
        if self.autoscroll:
            adj = self.labels['sw'].get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())

    def _send_command(self, *args):
        cmd = self.labels['entry'].get_text()
        self.labels['entry'].set_text('')
        self._screen.remove_keyboard()

        self.add_gcode("command", time.time(), cmd)
        self._screen._ws.klippy.gcode_script(cmd)

    def activate(self):
        self.clear()
        self._screen._ws.send_method("server.gcode_store", {"count": 100}, self.gcode_response)
