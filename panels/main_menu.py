import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk, Pango
from panels.menu import Panel as MenuPanel
from ks_includes.widgets.heatergraph import HeaterGraph
from ks_includes.widgets.keypad import Keypad
from ks_includes.KlippyGtk import find_widget
import os
import pathlib


class Panel(MenuPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title, items)
        iconPath = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", "crologo.svg")
        self.devices = {}
        self.graph_update = None
        self.active_heater = None
        self.h = self.f = 0
        self.main_menu = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, hexpand=True, vexpand=True)
        scroll = self._gtk.ScrolledWindow()
        self.numpad_visible = False
        stats = self._printer.get_printer_status_data()["printer"]
        
        logging.info("### Making MainMenu")
        
        # Create a horizontal box for the image and title
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

        # Prevent the hbox from expanding vertically
        hbox.set_hexpand(False)
        hbox.set_vexpand(False)
        hbox.set_halign(Gtk.Align.CENTER)
        hbox.set_valign(Gtk.Align.START)  # Align at the top

        self.content.add(hbox)
        
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        buttons.set_margin_top(20)
        buttons.set_margin_bottom(20)
        buttons.set_margin_start(20)
        buttons.set_margin_end(20)

        # Create three rounded buttons
        button1 = self.create_rounded_button(None, "Prepare", self.button1_clicked)
        button2 = self.create_rounded_button(None, "Preheat", self.button2_clicked)
        button3 = self.create_rounded_button(None, "Print", self.button3_clicked)

        # Add buttons to the horizontal box
        buttons.pack_start(button1, True, True, 0)
        buttons.pack_start(button2, True, True, 0)
        buttons.pack_start(button3, True, True, 0)

        # Add the hbox to the window
        self.content.add(buttons)
            

    def create_rounded_button(self, icon_path, label_text, callback):
        # Create a button
        button = Gtk.Button()

        # Apply a CSS class to style the button
        button.get_style_context().add_class("rounded-button")

        # Create a vertical box to stack the icon and label
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        # Add an icon
        if icon_path:
            image = Gtk.Image.new_from_file(icon_path)
            vbox.pack_start(image, True, True, 0)

        # Add a label
        label = Gtk.Label(label=label_text)
        vbox.pack_start(label, False, False, 0)

        # Add the vbox to the button
        button.add(vbox)
        
        button.connect("clicked", callback)

        return button
        
    def button1_clicked(self, button):
        print("Button 1 clicked")
        
    def button2_clicked(self, button):
        print("Button 2 clicked")
        
    def button3_clicked(self, button):
        print("Button 3 clicked")