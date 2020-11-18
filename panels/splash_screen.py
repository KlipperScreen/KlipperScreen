import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from panels.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.SplashScreenPanel")

class SplashScreenPanel(ScreenPanel):
    box = None

    def initialize(self, panel_name):
        _ = self.lang.gettext

        image = Gtk.Image()
        #TODO: update file reference
        image.set_from_file(os.getcwd() + "/styles/z-bolt/images/klipper.png")

        self.labels['text'] = Gtk.Label(_("Initializing printer..."))
        self.labels['text'].get_style_context().add_class("text")


        self.labels['actions'] = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.labels['actions'].set_hexpand(True)
        self.labels['actions'].set_vexpand(False)
        self.labels['actions'].set_halign(Gtk.Align.END)
        self.labels['actions'].set_margin_end(20)


        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        main.pack_start(image, True, True, 10)
        main.pack_end(self.labels['actions'], False, False, 10)
        main.pack_end(self.labels['text'], True, True, 10)


        box = Gtk.VBox()
        box.add(main)

        self.panel = box

    def update_text(self, text):
        self.labels['text'].set_text(text)
        self.clear_action_bar()

    def clear_action_bar(self):
        for child in self.labels['actions'].get_children():
            self.labels['actions'].remove(child)

    def show_restart_buttons(self):
        _ = self.lang.gettext

        if "firmware_restart" not in self.labels:
            self.labels['restart'] = KlippyGtk.ButtonImage("reboot",_("Restart"),"color1")
            self.labels['restart'].connect("clicked", self.restart)
            self.labels['firmware_restart'] = KlippyGtk.ButtonImage("restart",_("Firmware Restart"),"color2")
            self.labels['firmware_restart'].connect("clicked", self.firmware_restart)

        self.clear_action_bar()

        self.labels['actions'].add(self.labels['restart'])
        self.labels['actions'].add(self.labels['firmware_restart'])

    def firmware_restart(self, widget):
        self._screen._ws.klippy.restart_firmware()

    def restart(self, widget):
        self._screen._ws.klippy.restart()
