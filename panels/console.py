import gi
import logging
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from datetime import datetime
from ks_includes.KlippyGcodes import KlippyGcodes
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
    def initialize(self, panel_name):
        _ = self.lang.gettext

        gcodes = self._screen._ws.send_method("server.gcode_store", {"count": 100}, self.gcode_response)

        vbox = Gtk.VBox()
        vbox.set_hexpand(True)
        vbox.set_vexpand(True)

        sw = Gtk.ScrolledWindow()
        sw.set_hexpand(True)
        sw.set_vexpand(True)

        tb = Gtk.TextBuffer()
        tv = Gtk.TextView()
        tv.set_buffer(tb)
        tv.set_sensitive(False)
        tv.connect("size-allocate", self._autoscroll)

        sw.add(tv)

        ebox = Gtk.Box()
        ebox.set_hexpand(True)
        ebox.set_vexpand(False)

        entry = Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_vexpand(False)
        entry.connect("focus-in-event", self._show_keyboard)

        enter = self._gtk.Button("Send")
        enter.set_hexpand(False)
        enter.connect("clicked", self._send_command)

        ebox.add(entry)  # , True, 0, 0)
        ebox.add(enter)  # , True, 0, 0)

        self.labels.update({
            "entry": entry,
            "sw": sw,
            "tb": tb,
            "tv": tv
        })

        vbox.add(sw)
        vbox.pack_end(ebox, False, 0, 0)
        self.content.add(vbox)
        self._screen.add_subscription(panel_name)

    def add_gcode(self, type, time, message):
        if type == "command":
            color = COLORS['command']
            message = '$ %s' % message
        elif message.startswith("!!"):
            color = COLORS['error']
        elif message.startswith("//"):
            color = COLORS['warning']
        else:
            color = COLORS['response']

        message = '<span color="%s">%s</span>' % (color, message)

        message = message.replace('\n', '\n         ')

        self.labels['tb'].insert_markup(
            self.labels['tb'].get_end_iter(),
            '\n<span color="%s">%s</span> %s' % (COLORS['time'], datetime.fromtimestamp(time).strftime("%H:%M:%S"),
                                                 message), -1
        )

    def gcode_response(self, result, method, params):
        if method != "server.gcode_store":
            return

        for resp in result['result']['gcode_store']:
            self.add_gcode(resp['type'], resp['time'], resp['message'])

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            self.add_gcode("response", time.time(), data)

    def _autoscroll(self, *args):
        adj = self.labels['sw'].get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def _show_keyboard(self, *args):
        self._screen.show_keyboard()

    def _send_command(self, *args):
        cmd = self.labels['entry'].get_text()
        self.labels['entry'].set_text('')

        self.add_gcode("command", time.time(), cmd)
        self._screen._ws.klippy.gcode_script(cmd)
