import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        # Main centered layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        main_box.set_halign(Gtk.Align.CENTER)
        main_box.set_valign(Gtk.Align.CENTER)
        self.content.add(main_box)

        # Queue Start button
        queue_btn = Gtk.Button()
        queue_btn.get_style_context().add_class("queue-button")
        queue_lbl = Gtk.Label(label="Queue Start")
        queue_btn.add(queue_lbl)
        queue_btn.connect("clicked", self._queue_start)
        main_box.pack_start(queue_btn, False, False, 0)

        # Manual Print button
        manual_btn = Gtk.Button()
        manual_btn.get_style_context().add_class("queue-button")
        manual_lbl = Gtk.Label(label="Manual Print")
        manual_btn.add(manual_lbl)
        manual_btn.connect("clicked", self._manual_print)
        main_box.pack_start(manual_btn, False, False, 0)

    def _queue_start(self, widget):
        """Send START_QUEUE G-code macro to begin sequential printing."""
        self._screen._send_action(widget, "printer.gcode.script", {"script": "START_QUEUE"})

    def _manual_print(self, widget):
        """Open the file browser for manual print selection."""
        self._screen.show_panel("gcodes")
