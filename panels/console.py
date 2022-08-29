import gi
import time
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from datetime import datetime
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return ConsolePanel(*args)


COLORS = {
    "command": "#bad8ff",
    "error": "#ff6975",
    "response": "#b8b8b8",
    "time": "grey",
    "warning": "#c9c9c9"
}


class ConsolePanel(ScreenPanel):
    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)
        self.autoscroll = True
        self.hidetemps = True

    def initialize(self, panel_name):
        self._screen._ws.send_method("server.gcode_store", {"count": 100}, self.gcode_response)

        o1_lbl = Gtk.Label(_("Auto-scroll"))
        o1_lbl.set_halign(Gtk.Align.END)
        o1_switch = Gtk.Switch()
        o1_switch.set_property("width-request", round(self._gtk.get_font_size() * 5))
        o1_switch.set_property("height-request", round(self._gtk.get_font_size() * 2.5))
        o1_switch.set_active(self.autoscroll)
        o1_switch.connect("notify::active", self.set_autoscroll)

        o2_lbl = Gtk.Label(_("Hide temp."))
        o2_lbl.set_halign(Gtk.Align.END)
        o2_switch = Gtk.Switch()
        o2_switch.set_property("width-request", round(self._gtk.get_font_size() * 5))
        o2_switch.set_property("height-request", round(self._gtk.get_font_size() * 2.5))
        o2_switch.set_active(self.hidetemps)
        o2_switch.connect("notify::active", self.hide_temps)

        o3_button = self._gtk.ButtonImage("refresh", _('Clear') + " ", None, .66, Gtk.PositionType.RIGHT, 1)
        o3_button.connect("clicked", self.clear)

        options = Gtk.Box()
        options.set_hexpand(True)
        options.set_vexpand(False)
        options.add(o1_lbl)
        options.pack_start(o1_switch, False, False, 5)
        options.add(o2_lbl)
        options.pack_start(o2_switch, False, False, 5)
        options.add(o3_button)

        sw = Gtk.ScrolledWindow()
        sw.set_hexpand(True)
        sw.set_vexpand(True)

        tb = Gtk.TextBuffer()
        tv = Gtk.TextView()
        tv.set_buffer(tb)
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.connect("size-allocate", self._autoscroll)
        tv.connect("focus-in-event", self._screen.remove_keyboard)

        sw.add(tv)

        ebox = Gtk.Box()
        ebox.set_hexpand(True)
        ebox.set_vexpand(False)

        entry = Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_vexpand(False)
        entry.connect("button-press-event", self._show_keyboard)
        entry.connect("focus-in-event", self._screen.show_keyboard)
        entry.connect("activate", self._send_command)
        entry.grab_focus_without_selecting()

        enter = self._gtk.ButtonImage("resume", " " + _('Send') + " ", None, .66, Gtk.PositionType.RIGHT, 1)
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

    def _show_keyboard(self, widget=None, event=None):
        self._screen.show_keyboard(entry=self.labels['entry'])

    def clear(self, widget):
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
        elif self.hidetemps and re.match('^(?:ok\\s+)?(B|C|T\\d*):', message):
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

    def hide_temps(self, *args):
        self.hidetemps ^= True

    def set_autoscroll(self, *args):
        self.autoscroll ^= True

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
