import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


class ScreenSaver:
    def __init__(self, screen):
        self.screen = screen
        self.printer = screen.printer
        self.config = screen._config
        self.screensaver_timeout = None
        self.blackbox = None

    def is_showing(self):
        return self.blackbox is not None

    def reset_timeout(self, *args):
        if self.screensaver_timeout is not None:
            GLib.source_remove(self.screensaver_timeout)
            self.screensaver_timeout = None
        if self.screen.use_dpms:
            return
        if self.printer and self.printer.state in ("printing", "paused"):
            use_screensaver = self.config.get_main_config().get('screen_blanking_printing') != "off"
        else:
            use_screensaver = self.config.get_main_config().get('screen_blanking') != "off"
        if use_screensaver:
            self.screensaver_timeout = GLib.timeout_add_seconds(
                self.screen.blanking_time, self.show)

    def show(self):
        if self.blackbox is not None:
            logging.debug("Screensaver active")
            return
        logging.debug("Showing Screensaver")
        if self.screensaver_timeout is not None:
            GLib.source_remove(self.screensaver_timeout)
            self.screensaver_timeout = None
        if self.screen.blanking_time == 0:
            return False
        self.screen.remove_keyboard()
        self.screen.close_popup_message()
        for dialog in self.screen.dialogs:
            logging.debug("Hiding dialog")
            dialog.hide()

        close = Gtk.Button()
        close.connect("clicked", self.close)

        box = Gtk.Box(
            halign=Gtk.Align.CENTER, width_request=self.screen.width, height_request=self.screen.height)
        box.pack_start(close, True, True, 0)
        box.get_style_context().add_class("screensaver")
        self.blackbox = box
        for child in self.screen.overlay.get_children():
            child.hide()
        self.screen.overlay.add(self.blackbox)

        # Avoid leaving a cursor-handle
        close.grab_focus()
        self.screen.gtk.set_cursor(False, window=self.screen.get_window())

        self.blackbox.show_all()
        self.screen.power_devices(None, self.config.get_main_config().get("screen_off_devices", ""), on=False)
        return False

    def close(self, widget=None):
        if self.blackbox is None:
            return False
        logging.debug("Closing Screensaver")
        self.screen.overlay.remove(self.blackbox)
        self.blackbox = None
        for child in self.screen.overlay.get_children():
            child.show()
        if self.screen.use_dpms:
            self.screen.wake_screen()
        else:
            self.reset_timeout()
        for dialog in self.screen.dialogs:
            logging.info(f"Restoring Dialog {dialog}")
            dialog.show()
        self.screen.gtk.set_cursor(self.screen.show_cursor, window=self.screen.get_window())
        self.screen.power_devices(None, self.config.get_main_config().get("screen_on_devices", ""), on=True)
        self.screen.lock_screen.relock()
