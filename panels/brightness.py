import logging
import subprocess
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Brightness")
        super().__init__(screen, title)

        brightness = 0
        min_brightness = 0
        max_brightness = 255

        backlight_devices = os.listdir("/sys/class/backlight/")
        logging.debug(f"Backlights: {backlight_devices}")

        self.brightness_command = self._screen._config.get_main_config().get('brightness_command')
        # self.brightness_command = f"echo {{value}}"

        if not self.brightness_command and not backlight_devices:
            self._screen.show_popup_message(_("Backlight not configured"), level=3)
            self.back()
            return

        if not self.brightness_command:
            device = backlight_devices[0] if backlight_devices else None
            brightness_path = f"/sys/class/backlight/{device}/brightness"
            max_brightness_path = f"/sys/class/backlight/{device}/max_brightness"
            min_brightness_path = f"/sys/class/backlight/{device}/min_brightness"
            self.brightness_command = f"echo {{value}} | sudo tee {brightness_path}"
            try:
                max_brightness = int(subprocess.check_output(f"cat {max_brightness_path}", shell=True).strip())
            except Exception as e:
                logging.warning(f"Could not read max brightness: {e}")
            try:
                min_brightness = int(subprocess.check_output(f"cat {min_brightness_path}", shell=True).strip())
            except Exception as e:
                logging.warning(f"Could not read min brightness: {e}")
            try:
                brightness = int(subprocess.check_output(f"cat {brightness_path}", shell=True).strip())
            except Exception as e:
                logging.warning(f"Could not read current brightness: {e}")

        step_increment = (max_brightness - min_brightness) / 32
        adj = Gtk.Adjustment(brightness, min_brightness, max_brightness, step_increment)

        scale = Gtk.Scale(
            adjustment=adj, digits=0, hexpand=True, vexpand=True, valign=Gtk.Align.CENTER, has_origin=True
        )
        scale.get_style_context().add_class("option_slider")
        scale.connect("button-release-event", self.change_brightness)

        box = Gtk.Box()
        box.add(scale)
        self.content.add(box)

    def change_brightness(self, widget, event):
        self.set_brightness(widget.get_value())

    def set_brightness(self, value):
        value = int(value)
        bash_command = self.brightness_command.format(value=value)
        try:
            subprocess.run(bash_command, shell=True, check=True)
            logging.info(f"Brightness set to {value}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error setting brightness: {e}")
            self._screen.show_popup_message(_("Failed to set brightness"), level=3)
