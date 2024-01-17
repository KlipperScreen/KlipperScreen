import logging
import subprocess
import glob
import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):

        super().__init__(screen, title)
        self.menu = ['screen_brightness']

        self.buttons = {
            'LOW': self._gtk.Button("brightness", f"   {_('Low')}", None, 0.9, Gtk.PositionType.LEFT, 3),
            'NORMAL': self._gtk.Button("brightness", f"   {_('Medium')}", None, 0.9, Gtk.PositionType.LEFT, 3),
            'HIGH': self._gtk.Button("brightness", f"   {_('High')}", None, 0.9, Gtk.PositionType.LEFT, 3),
        }
        self.buttons['LOW'].connect("clicked", self.change_brightness, 25)
        self.buttons['LOW'].set_property("opacity", 0.3)

        self.buttons['NORMAL'].connect("clicked", self.change_brightness, 100)
        self.buttons['NORMAL'].set_property("opacity", 0.7)

        self.buttons['HIGH'].connect("clicked", self.change_brightness, 255)
        self.buttons['HIGH'].set_property("opacity", 1.0)

        grid = Gtk.Grid()

        grid.attach(self.buttons['HIGH'], 1, 0, 1, 1)
        grid.attach(self.buttons['LOW'], 1, 2, 1, 1)
        grid.attach(self.buttons['NORMAL'], 1, 1, 1, 1)

        self.labels['screen_brightness'] = Gtk.Grid()
        self.labels['screen_brightness'].attach(grid, 0, 0, 3, 3)
        self.content.add(self.labels['screen_brightness'])

    def change_brightness(self, button, value):
        brightness_files = glob.glob('/sys/class/backlight/*/brightness')
        if not brightness_files:
            self._screen.show_popup_message(_("Error"), level=3)
            return
        
        brightness_file_path = brightness_files[0]
        with open(brightness_file_path, 'r') as brightness_file:
            brightness_value = brightness_file.read().strip()
            self.set_brightness(value=value)

    def set_brightness (self, value):
        bash_command = f"echo {value} | sudo tee /sys/class/backlight/*/brightness"
        try:
            subprocess.run(bash_command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")