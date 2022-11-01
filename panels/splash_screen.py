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

    def initialize(self, panel_name):

        image = self._gtk.Image("klipper", self._screen.width / 5, self._screen.height * .5)
        self.labels['text'] = Gtk.Label(_("Initializing printer..."))
        self.labels['text'].set_line_wrap(True)
        self.labels['text'].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.labels['text'].set_halign(Gtk.Align.CENTER)
        self.labels['text'].set_valign(Gtk.Align.CENTER)

        self.labels['menu'] = self._gtk.ButtonImage("settings", _("Menu"), "color4")
        self.labels['menu'].connect("clicked", self._screen._go_to_submenu, "")
        self.labels['restart'] = self._gtk.ButtonImage("refresh", _("Klipper Restart"), "color1")
        self.labels['restart'].connect("clicked", self.restart)
        self.labels['firmware_restart'] = self._gtk.ButtonImage("refresh", _("Firmware Restart"), "color2")
        self.labels['firmware_restart'].connect("clicked", self.firmware_restart)
        self.labels['restart_system'] = self._gtk.ButtonImage("refresh", _("System Restart"), "color1")
        self.labels['restart_system'].connect("clicked", self.restart_system)
        self.labels['shutdown'] = self._gtk.ButtonImage("shutdown", _('System Shutdown'), "color2")
        self.labels['shutdown'].connect("clicked", self.shutdown)

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
        self.labels['text'].set_markup(f"{text}")
        self.show_restart_buttons()

    def clear_action_bar(self):
        for child in self.labels['actions'].get_children():
            self.labels['actions'].remove(child)

    def show_restart_buttons(self):

        self.clear_action_bar()
        printer = self._screen.connected_printer
        if printer is not None and not self._screen.shutdown:
            printer_cfg = self._config.get_printer_config(printer)
            if printer_cfg is not None:
                power_devices = printer_cfg.get("power_devices", "")
                power_devices = [str(i.strip()) for i in power_devices.split(',')]
                logging.info(f"Associated power devices: {power_devices}")
                self.add_power_button(self._screen.search_power_devices(power_devices))

        if self._screen.printer is not None and self._screen.printer.state != "disconnected":
            self.labels['actions'].add(self.labels['restart'])
            self.labels['actions'].add(self.labels['firmware_restart'])
        else:
            self.labels['actions'].add(self.labels['restart_system'])
            self.labels['actions'].add(self.labels['shutdown'])
        self.labels['actions'].add(self.labels['menu'])
        self.labels['actions'].show_all()

    def add_power_button(self, powerdevs):
        if powerdevs is not None:
            self.labels['power'] = self._gtk.ButtonImage("shutdown", _("Power On Printer"), "color3")
            self.labels['power'].connect("clicked", self._screen.power_on, powerdevs)
            self.check_power_status()
            self.labels['actions'].add(self.labels['power'])

    def activate(self):
        self.check_power_status()
        self._screen.base_panel.show_macro_shortcut(False)
        self._screen.base_panel.show_heaters(False)
        self._screen.base_panel.show_estop(False)

    def check_power_status(self):
        if 'power' in self.labels:
            devices = self._screen.printer.get_power_devices()
            if devices is not None:
                for device in devices:
                    if self._screen.printer.get_power_device_status(device) == "off":
                        self.labels['power'].set_sensitive(True)
                        break
                    elif self._screen.printer.get_power_device_status(device) == "on":
                        self.labels['power'].set_sensitive(False)

    def firmware_restart(self, widget):
        self._screen._ws.klippy.restart_firmware()

    def restart(self, widget):
        self._screen._ws.klippy.restart()

    def shutdown(self, widget):

        if self._screen._ws.is_connected():
            self._screen._confirm_send_action(widget,
                                              _("Are you sure you wish to shutdown the system?"),
                                              "machine.shutdown")
        else:
            logging.info("OS Shutdown")
            os.system("systemctl poweroff")

    def restart_system(self, widget):

        if self._screen._ws.is_connected():
            self._screen._confirm_send_action(widget,
                                              _("Are you sure you wish to reboot the system?"),
                                              "machine.reboot")
        else:
            logging.info("OS Reboot")
            os.system("systemctl reboot")
