import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.content.get_style_context().add_class("customBG")

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")
        eagle_path = os.path.join(styles_dir, "cro_eagle.png")

        self.temp_labels = {}
        self.labels = {}

        # Main vertical layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        self.content.add(main_box)

        # Center area: eagle logo + status text
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        center_box.set_hexpand(True)
        center_box.set_vexpand(True)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)

        if os.path.exists(eagle_path):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(eagle_path, 320, 280)
            eagle_image = Gtk.Image.new_from_pixbuf(pixbuf)
            eagle_image.set_halign(Gtk.Align.CENTER)
            eagle_image.set_valign(Gtk.Align.CENTER)
            center_box.add(eagle_image)

        self.labels["text"] = Gtk.Label(
            label=_("Initializing printer..."),
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        center_box.add(self.labels["text"])

        main_box.pack_start(center_box, True, True, 0)

        # Action buttons bar
        self.labels["menu"] = self._gtk.Button("settings", _("Menu"), "color4")
        self.labels["menu"].connect("clicked", self._screen._go_to_submenu, "")
        self.labels["restart"] = self._gtk.Button(
            "refresh", _("Klipper Restart"), "color1"
        )
        self.labels["restart"].connect("clicked", self.restart_klipper)
        self.labels["firmware_restart"] = self._gtk.Button(
            "refresh", _("Firmware Restart"), "color2"
        )
        self.labels["firmware_restart"].connect("clicked", self.firmware_restart)
        self.labels["restart_system"] = self._gtk.Button(
            "refresh", _("System Restart"), "color1"
        )
        self.labels["restart_system"].connect("clicked", self.reboot_poweroff, "reboot")
        self.labels["shutdown"] = self._gtk.Button(
            "shutdown", _("System Shutdown"), "color2"
        )
        self.labels["shutdown"].connect("clicked", self.reboot_poweroff, "shutdown")
        self.labels["retry"] = self._gtk.Button("load", _("Retry"), "color3")
        self.labels["retry"].connect("clicked", self.retry)

        self.labels["actions"] = Gtk.Box(hexpand=True, vexpand=False, homogeneous=True)
        main_box.pack_start(self.labels["actions"], False, False, 0)

        # Bottom temperature bar
        temp_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        temp_bar.set_halign(Gtk.Align.CENTER)
        temp_bar.set_valign(Gtk.Align.END)
        temp_bar.set_margin_bottom(12)
        temp_bar.set_margin_start(20)
        temp_bar.set_margin_end(20)

        # Nozzle temperature card
        nozzle_card = self._create_temp_card("Nozzle", "nozzle_blue", "extruder")
        temp_bar.pack_start(nozzle_card, False, False, 0)

        # Bed temperature card
        bed_card = self._create_temp_card("Bed", "bed_orange", "heater_bed")
        temp_bar.pack_start(bed_card, False, False, 0)

        main_box.pack_end(temp_bar, False, False, 0)

        self.show_restart_buttons()

        # Start temperature update timer
        GLib.timeout_add_seconds(1, self._update_temps)

    def _create_temp_card(self, label_text, icon_type, device):
        """Create a temperature display card matching the mockup."""
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card.get_style_context().add_class("temp-card")
        card.set_size_request(280, 56)

        # Thermometer icon (colored indicator)
        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        icon_box.set_valign(Gtk.Align.CENTER)
        icon_box.set_margin_start(8)

        # Simple colored bar as thermometer indicator
        indicator = Gtk.DrawingArea()
        indicator.set_size_request(6, 32)
        if icon_type == "nozzle_blue":
            indicator.connect("draw", self._draw_indicator, 0.2, 0.6, 1.0)
        else:
            indicator.connect("draw", self._draw_indicator, 1.0, 0.5, 0.2)
        icon_box.add(indicator)
        card.pack_start(icon_box, False, False, 0)

        # Temperature info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        info_box.set_valign(Gtk.Align.CENTER)

        # Label (Nozzle / Bed)
        name_label = Gtk.Label(label=label_text)
        name_label.get_style_context().add_class("temp-label")
        name_label.set_halign(Gtk.Align.START)
        info_box.add(name_label)

        # Temperature value
        temp_label = Gtk.Label(label="--°")
        temp_label.get_style_context().add_class("temp-value")
        temp_label.set_halign(Gtk.Align.START)
        info_box.add(temp_label)

        card.pack_start(info_box, True, True, 0)

        # State label
        state_label = Gtk.Label(label="Idle")
        state_label.get_style_context().add_class("temp-state")
        state_label.set_valign(Gtk.Align.CENTER)
        state_label.set_margin_end(12)
        card.pack_end(state_label, False, False, 0)

        # Store references for updates
        self.temp_labels[device] = {
            'temp': temp_label,
            'state': state_label,
        }

        return card

    def _draw_indicator(self, widget, ctx, r, g, b):
        """Draw a colored thermometer indicator bar."""
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        # Rounded rectangle
        radius = width / 2
        ctx.set_source_rgb(r, g, b)
        ctx.arc(width / 2, radius, radius, 3.14159, 0)
        ctx.arc(width / 2, height - radius, radius, 0, 3.14159)
        ctx.close_path()
        ctx.fill()
        return True

    def _update_temps(self):
        """Update temperature displays."""
        for device, labels in self.temp_labels.items():
            temp = self._printer.get_stat(device, "temperature")
            target = self._printer.get_stat(device, "target")

            if temp is not None:
                labels['temp'].set_label(f"{temp:.0f}°")
            else:
                labels['temp'].set_label("--°")

            # Determine state
            if target and target > 0:
                state = self._printer.state
                if state in ("printing", "paused"):
                    labels['state'].set_label("Printing")
                else:
                    labels['state'].set_label("Heating")
            else:
                labels['state'].set_label("Idle")

        return True

    def update_text(self, text):
        self.labels["text"].set_label(f"{text}")
        self.show_restart_buttons()

    def clear_action_bar(self):
        for child in self.labels["actions"].get_children():
            self.labels["actions"].remove(child)

    def show_restart_buttons(self):

        self.clear_action_bar()
        if self.ks_printer_cfg is not None and self._screen._ws.connected:
            power_devices = self.ks_printer_cfg.get("power_devices", "")
            if power_devices and self._printer.get_power_devices():
                logging.info(f"Associated power devices: {power_devices}")
                self.add_power_button(power_devices)

        if self._screen.initialized:
            self.labels["actions"].add(self.labels["restart"])
            self.labels["actions"].add(self.labels["firmware_restart"])
        else:
            self.labels["actions"].add(self.labels["restart_system"])
            self.labels["actions"].add(self.labels["shutdown"])
        self.labels["actions"].add(self.labels["menu"])
        if (
            self._screen._ws
            and not self._screen._ws.connecting
            or self._screen.reinit_count > self._screen.max_retries
        ):
            self.labels["actions"].add(self.labels["retry"])
        self.labels["actions"].show_all()

    def add_power_button(self, powerdevs):
        self.labels["power"] = self._gtk.Button(
            "shutdown", _("Power On Printer"), "color3"
        )
        self.labels["power"].connect(
            "clicked", self._screen.power_devices, powerdevs, True
        )
        self.check_power_status()
        self.labels["actions"].add(self.labels["power"])

    def activate(self):
        self.check_power_status()

    def check_power_status(self):
        if "power" in self.labels:
            devices = self._printer.get_power_devices()
            if devices is not None:
                for device in devices:
                    if self._printer.get_power_device_status(device) == "off":
                        self.labels["power"].set_sensitive(True)
                        break
                    elif self._printer.get_power_device_status(device) == "on":
                        self.labels["power"].set_sensitive(False)

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        # Update temps from live data
        for device in self.temp_labels:
            if device in data:
                temp = self._printer.get_stat(device, "temperature")
                target = self._printer.get_stat(device, "target")
                if temp is not None:
                    self.temp_labels[device]['temp'].set_label(f"{temp:.0f}°")
                if target and target > 0:
                    state = self._printer.state
                    if state in ("printing", "paused"):
                        self.temp_labels[device]['state'].set_label("Printing")
                    else:
                        self.temp_labels[device]['state'].set_label("Heating")
                else:
                    self.temp_labels[device]['state'].set_label("Idle")

    def firmware_restart(self, widget):
        self._screen._ws.klippy.restart_firmware()

    def restart_klipper(self, widget):
        self._screen._ws.klippy.restart()

    def retry(self, widget):
        logging.debug("User retrying connection")
        self._screen.connect_printer(self._screen.connecting_to_printer)
        self.show_restart_buttons()

    def reboot_poweroff(self, widget, method):
        label = Gtk.Label(wrap=True, hexpand=True, vexpand=True)
        if method == "reboot":
            label.set_label(_("Are you sure you wish to reboot the system?"))
            title = _("Restart")
        else:
            label.set_label(_("Are you sure you wish to shutdown the system?"))
            title = _("Shutdown")
        buttons = [
            {
                "name": _("Host"),
                "response": Gtk.ResponseType.OK,
                "style": "dialog-info",
            },
            {
                "name": _("Cancel"),
                "response": Gtk.ResponseType.CANCEL,
                "style": "dialog-error",
            },
        ]
        if self._screen._ws.connected:
            buttons.insert(
                1,
                {
                    "name": _("Printer"),
                    "response": Gtk.ResponseType.APPLY,
                    "style": "dialog-warning",
                },
            )
        self._gtk.Dialog(title, buttons, label, self.reboot_poweroff_confirm, method)

    def reboot_poweroff_confirm(self, dialog, response_id, method):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            if method == "reboot":
                os.system("systemctl reboot -i")
            else:
                os.system("systemctl poweroff -i")
        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            else:
                self._screen._ws.send_method("machine.shutdown")
