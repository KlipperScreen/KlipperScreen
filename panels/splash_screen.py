import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, Pango

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return SplashScreenPanel(*args)

class SplashScreenPanel(ScreenPanel):
    box = None

    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)

    def initialize(self, panel_name):
        _ = self.lang.gettext

        image = self._gtk.Image("klipper.svg", None, 3.2, 3.2)

        self.labels['text'] = Gtk.Label(_("Initializing printer..."))
        self.labels['text'].set_line_wrap(True)
        self.labels['text'].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.labels['text'].set_halign(Gtk.Align.CENTER)
        self.labels['text'].set_valign(Gtk.Align.CENTER)


        self.labels['actions'] = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.labels['actions'].set_hexpand(True)
        self.labels['actions'].set_vexpand(False)
        self.labels['actions'].set_halign(Gtk.Align.CENTER)
        self.labels['actions'].set_homogeneous(True)
        self.labels['actions'].set_size_request(self._screen.base_panel.content.get_allocation().width, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        scroll.add(self.labels['text'])

        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        info.pack_start(image, False, True, 8)
        info.pack_end(scroll, True, True, 8)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.pack_start(info, True, True, 8)
        main.pack_end(self.labels['actions'], False, False, 0)

        self.show_restart_buttons()

        self.content.add(main)

    def update_text(self, text):
        self.labels['text'].set_markup("%s" % text)

    def clear_action_bar(self):
        for child in self.labels['actions'].get_children():
            self.labels['actions'].remove(child)

    def show_restart_buttons(self):
        _ = self.lang.gettext

        if "firmware_restart" not in self.labels:
            self.labels['menu'] = self._gtk.ButtonImage("settings", _("Menu"), "color4")
            self.labels['menu'].connect("clicked", self._screen._go_to_submenu, "")
            self.labels['restart'] = self._gtk.ButtonImage("refresh", _("Restart") + "\n" + "Klipper", "color1")
            self.labels['restart'].connect("clicked", self.restart)
            self.labels['firmware_restart'] = self._gtk.ButtonImage("refresh", _("Firmware\nRestart"), "color2")
            self.labels['firmware_restart'].connect("clicked", self.firmware_restart)
            self.labels['power'] = self._gtk.ButtonImage("shutdown", _("Power On Printer"), "color3")
            self.labels['restart_system'] = self._gtk.ButtonImage("refresh", _("Restart\nSystem"), "color1")
            self.labels['restart_system'].connect("clicked", self.restart_system)
            self.labels['shutdown'] = self._gtk.ButtonImage("shutdown", _('System\nShutdown'), "color2")
            self.labels['shutdown'].connect("clicked", self.shutdown)

        self.clear_action_bar()

        if self._screen.printer is not None and self._screen.printer.state != "disconnected":
            self.search_power_devices()
            self.labels['actions'].add(self.labels['restart'])
            self.labels['actions'].add(self.labels['firmware_restart'])
            self.labels['actions'].add(self.labels['menu'])
        else:
            self.labels['actions'].add(self.labels['restart_system'])
            self.labels['actions'].add(self.labels['shutdown'])
            self.labels['actions'].add(self.labels['menu'])

        self.labels['actions'].show_all()

    def search_power_devices(self):
        power_devices = found_devices = []
        printer = self._screen.connecting_to_printer
        logging.info("Connecting to %s", printer)
        printer_cfg = self._config.get_printer_config(printer)
        if printer_cfg is not None:
            power_devices = printer_cfg.get("power_devices", "")
            power_devices = [str(i.strip()) for i in power_devices.split(',')]
            logging.info("%s associated power devices: %s", printer, power_devices)
        devices = self._screen.printer.get_power_devices()
        logging.debug("Power devices: %s", devices)
        if devices is not None:
            for device in devices:
                for power_device in power_devices:
                    if device == power_device and power_device not in found_devices:
                        found_devices.append(power_device)
        if len(found_devices) > 0:
            logging.info("Found %s, Adding power button", found_devices)
            self.labels['power'].connect("clicked", self.power_on, found_devices)
            self.labels['actions'].add(self.labels['power'])
        else:
            logging.info("%s power devices not found", printer)

    def power_on(self, widget, devices):
        _ = self.lang.gettext
        self._screen.show_popup_message(_("Sending Power ON signal to: %s") % devices, level=1)
        for device in devices:
            if self._screen.printer.get_power_device_status(device) == "off":
                logging.info("%s is OFF, Sending Power ON signal", device)
                self._screen._ws.klippy.power_device_on(device)
            elif self._screen.printer.get_power_device_status(device) == "on":
                logging.info("%s is ON", device)


    def firmware_restart(self, widget):
        self._screen._ws.klippy.restart_firmware()

    def restart(self, widget):
        self._screen._ws.klippy.restart()


    def shutdown(self, widget):
        os.system("sudo shutdown -P now")

    def restart_system(self, widget):
        os.system("sudo reboot now")
