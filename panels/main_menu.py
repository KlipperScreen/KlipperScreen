import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from panels.menu import Panel as MenuPanel
from ks_includes.widgets.heatergraph import HeaterGraph
from ks_includes.widgets.keypad import Keypad
from ks_includes.KlippyGtk import find_widget
import os
import pathlib


class Panel(MenuPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title, items)
        self.content.get_style_context().add_class("customBG")
        iconPath = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", "crologo.svg")
        settingsPath = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", "gear.svg")
        movePath = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", "move.svg")
        printPath = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", "print.svg")
        self.devices = {}
        self.graph_update = None
        self.active_heater = None
        self.h = self.f = 0
        self.temp_buttons = {}  # To store temp buttons for updating
        
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

        button1 = self.create_rounded_button(movePath, "Move", self.button1_clicked)
        button2 = self.create_rounded_button(settingsPath, "Settings", self.button2_clicked)
        button3 = self.create_rounded_button(printPath, "Andrew Da Best", self.button3_clicked)

        buttons.pack_start(button1, True, True, 0)
        buttons.pack_start(button2, True, True, 0)
        buttons.pack_start(button3, True, True, 0)

        self.main_box.add(buttons)

        # Temperature section with buttons
        self.temp_grid = Gtk.Grid()
        self.temp_grid.set_column_spacing(20)
        self.temp_grid.set_row_spacing(10)
        self.temp_grid.set_margin_top(20)
        self.temp_grid.set_margin_bottom(20)
        self.temp_grid.set_margin_start(20)
        self.temp_grid.set_margin_end(20)
        self.add_temperature_rows()
        self.main_box.add(self.temp_grid)
        
        self.numpad_placeholder = Gtk.Box()
        self.overlay.add_overlay(self.numpad_placeholder)  # Add the numpad placeholder to the overlay
        self.numpad_placeholder.set_halign(Gtk.Align.CENTER)
        self.numpad_placeholder.set_valign(Gtk.Align.CENTER)  # Center the numpa
        GLib.timeout_add_seconds(1, self.update_temperatures)

    def create_rounded_button(self, icon_path, label_text, callback):
        button = Gtk.Button()
        button.get_style_context().add_class("rounded-button")
        if label_text == "Print":
            button.get_style_context().add_class("rounded-button")
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

    def add_temperature_rows(self):
    # Create a horizontal box for the temperature rows
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        hbox.set_halign(Gtk.Align.CENTER)  # Horizontally center the temperature rows
        hbox.set_valign(Gtk.Align.END)  # Push the box into the empty space
        hbox.set_margin_top(10)  # Optional: Adjust spacing from the buttons above

        # Add the Extruder Temp row
        extruder_box = self.create_temp_box("Extruder", "extruder")
        hbox.pack_start(extruder_box, False, False, 0)

        # Add the Bed Temp row
        bed_box = self.create_temp_box("Bed", "heater_bed")
        hbox.pack_start(bed_box, False, False, 0)

        # Add the horizontal box to the content
        self.main_box.add(hbox)


    def create_temp_box(self, label_text, device):
        # Create a horizontal box for a single temperature row
        temp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        # Add the label
        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.START)
        label.set_name("temperature_text")
        temp_box.pack_start(label, False, False, 0)

        # Add the button
        button = Gtk.Button(label="-- / --")
        button.get_style_context().add_class("temperature-button")
        button.set_halign(Gtk.Align.END)
        button.connect("clicked", self.show_numpad, device)
        temp_box.pack_start(button, False, False, 0)

        # Store the button for updates
        self.temp_buttons[device] = button

        return temp_box

    def update_temperatures(self):
        for device, button in self.temp_buttons.items():
            current_temp = self._printer.get_stat(device, "temperature")
            target_temp = self._printer.get_stat(device, "target")

            current_temp = f"{current_temp:.1f}" if current_temp is not None else "--"
            target_temp = f"{target_temp:.1f}" if target_temp is not None else "--"

            button.set_label(f"{current_temp} / {target_temp}")
        return True

    def show_numpad(self, button, device):
        logging.info("Showing numpad")
        self.active_heater = device
        
        

        if "keypad" not in self.labels:
            # Create the Keypad if it doesn't already exist
            self.labels["keypad"] = Keypad(self._screen, self.change_target_temp, self.pid_calibrate, self.hide_numpad)
            self.labels["label"] = Gtk.Label(label=f"Set {device} temperature")
            self.labels["vbox"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Configure the Keypad for the selected device
        can_pid = self._printer.state not in ("printing", "paused") \
            and self._screen.printer.config[self.active_heater]['control'] == 'pid'
        self.labels["keypad"].show_pid(can_pid)
        self.labels["keypad"].clear()

        # Remove the Keypad from its current parent if necessary
        if self.labels["keypad"].get_parent() is not None:
            self.labels["keypad"].get_parent().remove(self.labels["keypad"])
            self.labels["label"].get_parent().remove(self.labels["label"])
            
        self.numpad_placeholder.get_style_context().add_class("numpad-placeholder")
        self.labels["keypad"].get_style_context().add_class("keypad")

        self.numpad_placeholder.override_background_color(
            Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 1.0)  # Solid black background
        )

        # Add the Keypad to the overlay placeholder
        self.labels["vbox"].add(self.labels["label"])
        self.labels["vbox"].add(self.labels["keypad"])
        self.numpad_placeholder.add(self.labels["vbox"])
        #self.numpad_placeholder.add(label)
        #self.numpad_placeholder.add(self.labels["keypad"])

        # Ensure the placeholder and keypad are fully visible and interactive
        self.numpad_placeholder.set_sensitive(True)
        self.numpad_placeholder.set_opacity(1.0)  # Ensure the placeholder is fully opaque
        self.numpad_placeholder.set_hexpand(True)
        self.numpad_placeholder.set_vexpand(True)
        self.numpad_placeholder.set_halign(Gtk.Align.FILL)
        self.numpad_placeholder.set_valign(Gtk.Align.FILL)
        self.numpad_placeholder.show_all()

        # Redraw the overlay
        self.overlay.queue_draw()

        self.numpad_visible = True
        logging.info("Numpad displayed successfully")


    
    def hide_numpad(self, widget=None):
        if "keypad" in self.labels and self.labels["keypad"].get_parent():
            self.numpad_placeholder.remove(self.labels["keypad"])
            self.numpad_placeholder.remove(self.labels["label"])
            self.numpad_placeholder.remove(self.labels["vbox"])

        # Fully hide the numpad_placeholder to prevent event blocking
        self.numpad_placeholder.set_sensitive(False)
        self.numpad_placeholder.hide()
        # Re-enable all UI elements
        for child in self.main_box.get_children():
            child.set_sensitive(True)

        # Reset focus to the main box
        self.main_box.grab_focus()

        # Refresh the overlay
        self.overlay.queue_draw()
        self.numpad_visible = False

    def on_numpad_button_clicked(self, button, entry):
        entry.set_text(entry.get_text() + button.get_label())

    def set_temperature(self, button, entry, device, dialog):
        try:
            target_temp = float(entry.get_text())
            print(f"Setting {device} temperature to {target_temp}°C")
            dialog.destroy()
        except ValueError:
            print("Invalid temperature entered")
    
    def change_target_temp(self, temp):
        name = self.active_heater.split()[1] if len(self.active_heater.split()) > 1 else self.active_heater
        temp = self.verify_max_temp(temp)
        if temp is False:
            return

        if self.active_heater.startswith('extruder'):
            self._screen._ws.klippy.set_tool_temp(self._printer.get_tool_number(self.active_heater), temp)
        elif self.active_heater == "heater_bed":
            self._screen._ws.klippy.set_bed_temp(temp)
        elif self.active_heater.startswith('heater_generic '):
            self._screen._ws.klippy.set_heater_temp(name, temp)
        elif self.active_heater.startswith('temperature_fan '):
            self._screen._ws.klippy.set_temp_fan_temp(name, temp)
        else:
            logging.info(f"Unknown heater: {self.active_heater}")
            self._screen.show_popup_message(_("Unknown Heater") + " " + self.active_heater)
        self._printer.set_stat(name, {"target": temp})
    
    def pid_calibrate(self, temp):
        heater = self.active_heater.split(' ', maxsplit=1)[-1]
        if self.verify_max_temp(temp):
            script = {"script": f"PID_CALIBRATE HEATER={heater} TARGET={temp}"}
            self._screen._confirm_send_action(
                None,
                _("Initiate a PID calibration for:")
                + f" {heater} @ {temp} ºC"
                + "\n\n"
                + _("It may take more than 5 minutes depending on the heater power."),
                "printer.gcode.script",
                script
            )
    
    def verify_max_temp(self, temp):
        temp = int(temp)
        max_temp = int(float(self._printer.get_config_section(self.active_heater)['max_temp']))
        logging.debug(f"{temp}/{max_temp}")
        if temp > max_temp:
            self._screen.show_popup_message(_("Can't set above the maximum:") + f' {max_temp}')
            return False
        return max(temp, 0)

    def button1_clicked(self, button):
        self._screen.show_panel("move")

    def button2_clicked(self, button):
        self._screen.show_panel("settings")

    def button3_clicked(self, button):
        #self._screen._ws.klippy.gcode_script("K_ROS MESSAGE=GCODE,Start")
        self._screen.show_panel("print_screen")
        #self.back()
        #print("Going back")