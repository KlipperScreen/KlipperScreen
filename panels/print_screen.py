import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from panels.menu import Panel as MenuPanel
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.heatergraph import HeaterGraph
from ks_includes.widgets.keypad import Keypad
from ks_includes.KlippyGtk import find_widget
import os
import pathlib
import requests

FRONTEND_URL = "https://queue.vtcro.org"

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")
        iconPath = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", "crologo.svg")
        
        self.overlay = Gtk.Overlay()
        self.content.add(self.overlay)
        
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_margin_top(30)
        self.overlay.add(self.main_box)

        # Header with logo and title
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(iconPath, -1, -1)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        hbox.pack_start(image, False, False, 0)

        titleLabel = Gtk.Label()
        titleLabel.set_markup("<b>VT CRO Queue</b>")
        titleLabel.set_name("large_text")
        titleLabel.set_justify(Gtk.Justification.CENTER)
        titleLabel.set_margin_top(20)
        titleLabel.set_margin_bottom(20)
        hbox.pack_start(titleLabel, False, False, 0)

        hbox.set_hexpand(False)
        hbox.set_vexpand(False)
        hbox.set_halign(Gtk.Align.CENTER)
        hbox.set_valign(Gtk.Align.START)
        self.main_box.add(hbox)

        # Buttons section
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        buttons.set_margin_top(20)
        buttons.set_margin_bottom(20)
        buttons.set_margin_start(20)
        buttons.set_margin_end(20)
        
        url = f"{FRONTEND_URL}/api/check"
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            self.status = True
        else:
            self.status = False

        buttonList = []
        # if self.status:
        button1 = self.create_rounded_button(None, "Queue Start", self.button1_clicked)
        buttonList.append(button1)
        button2 = self.create_rounded_button(None, "Manual Print", self.button2_clicked)
        button3 = self.create_rounded_button(None, "Back", self.button3_clicked)
        buttonList.append(button2)
        buttonList.append(button3)

        for button in buttonList:
            buttons.pack_start(button, True, True, 0)


        self.main_box.add(buttons)

    def create_rounded_button(self, icon_path, label_text, callback):
        button = Gtk.Button()
        button.get_style_context().add_class("rounded-button")
        if label_text == "Print":
            button.get_style_context().add_class("print-button")
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        if icon_path:
            image = Gtk.Image.new_from_file(icon_path)
            image.set_valign(Gtk.Align.CENTER)
            vbox.pack_start(image, True, True, 0)

        label = Gtk.Label(label=label_text)
        label.set_valign(Gtk.Align.CENTER)
        label.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(label, False, False, 0)

        vbox.set_valign(Gtk.Align.CENTER)
        button.add(vbox)
        button.connect("clicked", callback)
        return button


    def button1_clicked(self, button):
        self._screen._send_action(button, "printer.gcode.script", {"script": "START_QUEUE"})

    def button2_clicked(self, button):
        self._screen.show_panel("gcodes")
        
    def button3_clicked(self, button):
        self._screen._menu_go_back()
