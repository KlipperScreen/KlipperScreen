import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.SplashScreenPanel")

def create_panel(*args):
    return SplashScreenPanel(*args)

class SplashScreenPanel(ScreenPanel):
    box = None

    def initialize(self, panel_name):
        _ = self.lang.gettext

        image = self._gtk.Image("klipper.png", None, 4, 3)

        self.labels['text'] = Gtk.Label(_("Initializing printer..."))
        self.labels['text'].set_line_wrap(True)
        self.labels['text'].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.labels['text'].set_halign(Gtk.Align.CENTER)


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

        self.layout = box

    def update_text(self, text):
        self.labels['text'].set_text(text)
        self.clear_action_bar()

    def clear_action_bar(self):
        for child in self.labels['actions'].get_children():
            self.labels['actions'].remove(child)

    def show_restart_buttons(self):
        _ = self.lang.gettext

        if "firmware_restart" not in self.labels:
            self.labels['power'] = self._gtk.ButtonImage("reboot",_("Power On Printer"),"color3")
            self.labels['restart'] = self._gtk.ButtonImage("reboot",_("Restart"),"color1")
            self.labels['restart'].connect("clicked", self.restart)
            self.labels['firmware_restart'] = self._gtk.ButtonImage("restart",_("Firmware Restart"),"color2")
            self.labels['firmware_restart'].connect("clicked", self.firmware_restart)

        self.clear_action_bar()

        devices = [i for i in self._screen.printer.get_power_devices() if i.lower().startswith('printer')]
        logger.debug("Power devices: %s" % devices)
        if len(devices) > 0:
            logger.debug("Adding power button")
            self.labels['power'].connect("clicked", self.power_on, devices[0])
            self.labels['actions'].add(self.labels['power'])

        self.labels['actions'].add(self.labels['power'])
        self.labels['actions'].add(self.labels['restart'])
        self.labels['actions'].add(self.labels['firmware_restart'])

    def firmware_restart(self, widget):
        self._screen._ws.klippy.restart_firmware()

    def power_on(self, widget, device):
        self._screen._ws.klippy.power_device_on(device)

    def restart(self, widget):
        self._screen._ws.klippy.restart()
