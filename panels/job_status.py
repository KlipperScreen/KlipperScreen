# -*- coding: utf-8 -*-
import gi
import logging
import os
import time

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango
from numpy import sqrt, pi, dot, array, median
from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return JobStatusPanel(*args)


class JobStatusPanel(ScreenPanel):
    is_paused = False
    filename = state_timeout = prev_pos = prev_gpos = vel_timeout = animation_timeout = close_timeout = None
    file_metadata = labels = {}
    state = "standby"
    timeleft_type = "auto"
    progress = zoffset = flowrate = vel = 0
    main_status_displayed = True
    velstore = flowstore = []

    def __init__(self, screen, title, back=False):
        super().__init__(screen, title, False)

    def initialize(self, panel_name):

        data = ['pos_x', 'pos_y', 'pos_z', 'time_left', 'duration', 'slicer_time', 'file_time',
                'filament_time', 'est_time', 'speed_factor', 'req_speed', 'max_accel', 'extrude_factor', 'zoffset',
                'zoffset', 'filament_used', 'filament_total', 'advance', 'fan', 'layer', 'total_layers', 'height',
                'flowrate']

        for item in data:
            self.labels[item] = Gtk.Label("-")
            self.labels[item].set_vexpand(True)
            self.labels[item].set_hexpand(True)

        self.labels['left'] = Gtk.Label(_("Left:"))
        self.labels['elapsed'] = Gtk.Label(_("Elapsed:"))
        self.labels['total'] = Gtk.Label(_("Total:"))
        self.labels['slicer'] = Gtk.Label(_("Slicer:"))
        self.labels['file_tlbl'] = Gtk.Label(_("File:"))
        self.labels['fila_tlbl'] = Gtk.Label(_("Filament:"))
        self.labels['speed_lbl'] = Gtk.Label(_("Speed:"))
        self.labels['accel_lbl'] = Gtk.Label(_("Acceleration:"))
        self.labels['flow'] = Gtk.Label(_("Flow:"))
        self.labels['zoffset_lbl'] = Gtk.Label(_("Z offset:"))
        self.labels['fila_used_lbl'] = Gtk.Label(_("Filament used:"))
        self.labels['fila_total_lbl'] = Gtk.Label(_("Filament total:"))
        self.labels['pa_lbl'] = Gtk.Label(_("Pressure Advance:"))
        self.labels['flowrate_lbl'] = Gtk.Label(_("Flowrate:"))
        self.labels['height_lbl'] = Gtk.Label(_("Height:"))
        self.labels['layer_lbl'] = Gtk.Label(_("Layer:"))

        self.fans = {}
        for fan in self._printer.get_fans():
            # fan_types = ["controller_fan", "fan_generic", "heater_fan"]
            if fan == "fan":
                name = " "
            elif fan.startswith("fan_generic"):
                name = fan.split(" ")[1:][0][:1].upper() + ":"
                if name.startswith("_"):
                    continue
            else:
                continue
            self.fans[fan] = {
                "name": name,
                "speed": "-"
            }

        self.create_buttons()
        self.buttons['button_grid'] = self._gtk.HomogeneousGrid()
        self.buttons['button_grid'].set_vexpand(False)

        self.labels['file'] = Gtk.Label("Filename")
        self.labels['file'].get_style_context().add_class("printing-filename")
        self.labels['file'].set_hexpand(True)
        self.labels['status'] = Gtk.Label("Status")
        self.labels['status'].get_style_context().add_class("printing-status")
        self.labels['lcdmessage'] = Gtk.Label("")
        self.labels['lcdmessage'].get_style_context().add_class("printing-status")

        for label in self.labels:
            self.labels[label].set_halign(Gtk.Align.START)
            self.labels[label].set_ellipsize(Pango.EllipsizeMode.END)

        fi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        fi_box.add(self.labels['file'])
        fi_box.add(self.labels['status'])
        fi_box.add(self.labels['lcdmessage'])

        self.labels['darea'] = Gtk.DrawingArea()
        self.labels['darea'].connect("draw", self.on_draw)

        box = Gtk.Box()
        box.set_halign(Gtk.Align.CENTER)
        self.labels['progress_text'] = Gtk.Label("0%")
        self.labels['progress_text'].get_style_context().add_class("printing-progress-text")
        box.add(self.labels['progress_text'])

        overlay = Gtk.Overlay()
        overlay.set_hexpand(True)
        overlay.add(self.labels['darea'])
        overlay.add_overlay(box)

        self.labels['thumbnail'] = self._gtk.Image("file", 2)
        if self._screen.vertical_mode:
            self.labels['thumbnail'].set_size_request(0, self._screen.height / 4)
        else:
            self.labels['thumbnail'].set_size_request(self._screen.width / 3, 0)

        self.labels['info_grid'] = Gtk.Grid()
        self.labels['info_grid'].attach(self.labels['thumbnail'], 0, 0, 1, 1)
        self.create_status_grid()

        self.grid = self._gtk.HomogeneousGrid()
        self.grid.set_row_homogeneous(False)
        self.grid.attach(overlay, 0, 0, 1, 1)
        self.grid.attach(fi_box, 1, 0, 3, 1)
        self.grid.attach(self.labels['info_grid'], 0, 1, 4, 2)
        self.grid.attach(self.buttons['button_grid'], 0, 3, 4, 1)

        self.content.add(self.grid)
        self._screen.wake_screen()

        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        # the diameter may change with extruders but is highly unusual
        diameter = float(self._printer.get_config_section(self.current_extruder)['filament_diameter'])
        self.fila_section = pi * ((diameter / 2) ** 2)

    def create_status_grid(self, widget=None):

        self.main_status_displayed = True

        self.labels['temp_grid'] = Gtk.Grid()
        if self._screen.width <= 480:
            nlimit = 2
        else:
            nlimit = 3
        n = 0
        self.extruder_button = {}
        if self._screen.printer.get_tools():
            for i, extruder in enumerate(self._printer.get_tools()):
                self.labels[extruder] = Gtk.Label("-")
                self.extruder_button[extruder] = self._gtk.ButtonImage("extruder-%s" % i,
                                                                       None, None, .6, Gtk.PositionType.LEFT)
                self.extruder_button[extruder].set_label(self.labels[extruder].get_text())
                self.extruder_button[extruder].connect("clicked", self.menu_item_clicked, "temperature",
                                                       {"panel": "temperature", "name": _("Temperature")})
                self.extruder_button[extruder].set_halign(Gtk.Align.START)
            self.current_extruder = self._printer.get_stat("toolhead", "extruder")
            self.labels['temp_grid'].attach(self.extruder_button[self.current_extruder], n, 0, 1, 1)
            n += 1
        else:
            self.current_extruder = None
        self.heater_button = {}
        if self._printer.has_heated_bed():
            self.heater_button['heater_bed'] = self._gtk.ButtonImage("bed",
                                                                     None, None, .6, Gtk.PositionType.LEFT)
            self.labels['heater_bed'] = Gtk.Label("-")
            self.heater_button['heater_bed'].set_label(self.labels['heater_bed'].get_text())
            self.heater_button['heater_bed'].connect("clicked", self.menu_item_clicked, "temperature",
                                                     {"panel": "temperature", "name": _("Temperature")})
            self.heater_button['heater_bed'].set_halign(Gtk.Align.START)
            self.labels['temp_grid'].attach(self.heater_button['heater_bed'], n, 0, 1, 1)
            n += 1
        for device in self._screen.printer.get_heaters():
            if n >= nlimit:
                break
            if device.startswith("heater_generic"):
                self.heater_button[device] = self._gtk.ButtonImage("heater",
                                                                   None, None, .6, Gtk.PositionType.LEFT)
                self.labels[device] = Gtk.Label("-")
                self.heater_button[device].set_label(self.labels[device].get_text())
                self.heater_button[device].connect("clicked", self.menu_item_clicked, "temperature",
                                                   {"panel": "temperature", "name": _("Temperature")})
                self.heater_button[device].set_halign(Gtk.Align.START)
                self.labels['temp_grid'].attach(self.heater_button[device], n, 0, 1, 1)
                n += 1
        extra_item = True
        printer_cfg = self._config.get_printer_config(self._screen.connected_printer)
        if printer_cfg is not None:
            titlebar_items = printer_cfg.get("titlebar_items", "")
            if titlebar_items is not None:
                titlebar_items = [str(i.strip()) for i in titlebar_items.split(',')]
                logging.info("Titlebar items: %s", titlebar_items)
                for device in self._screen.printer.get_heaters():
                    if device.startswith("temperature_sensor"):
                        name = device.split(" ")[1:][0]
                        for item in titlebar_items:
                            if name == item:
                                if extra_item:
                                    extra_item = False
                                    nlimit += 1
                                if n >= nlimit:
                                    break
                                self.heater_button[device] = self._gtk.ButtonImage("heat-up", None, None, .6,
                                                                                   Gtk.PositionType.LEFT)
                                self.labels[device] = Gtk.Label("-")
                                self.heater_button[device].set_label(self.labels[device].get_text())
                                self.heater_button[device].connect("clicked", self.menu_item_clicked, "temperature",
                                                                   {"panel": "temperature", "name": _("Temperature")})
                                self.heater_button[device].set_halign(Gtk.Align.START)
                                self.labels['temp_grid'].attach(self.heater_button[device], n, 0, 1, 1)
                                n += 1
                                break

        self.z_button = self._gtk.ButtonImage("home-z", None, None, .6, Gtk.PositionType.LEFT)
        self.z_button.set_label(self.labels['pos_z'].get_text())
        self.z_button.connect("clicked", self.create_move_grid)
        self.z_button.set_halign(Gtk.Align.START)

        self.speed_button = self._gtk.ButtonImage("speed+", None, None, .6, Gtk.PositionType.LEFT)
        self.speed_button.set_label(self.labels['speed_factor'].get_text())
        self.speed_button.connect("clicked", self.create_move_grid)
        self.speed_button.set_halign(Gtk.Align.START)

        self.extrusion_button = self._gtk.ButtonImage("extrude", None, None, .6, Gtk.PositionType.LEFT)
        self.extrusion_button.set_label(self.labels['extrude_factor'].get_text())
        self.extrusion_button.connect("clicked", self.create_extrusion_grid)
        self.extrusion_button.set_halign(Gtk.Align.START)

        self.fan_button = self._gtk.ButtonImage("fan", None, None, .6, Gtk.PositionType.LEFT)
        self.fan_button.set_label(self.labels['fan'].get_text())
        self.fan_button.connect("clicked", self.menu_item_clicked, "fan", {"panel": "fan", "name": _("Fan")})
        self.fan_button.set_halign(Gtk.Align.START)

        elapsed_label = self.labels['elapsed'].get_text() + "  " + self.labels['duration'].get_text()
        self.elapsed_button = self._gtk.ButtonImage("clock", elapsed_label, None, .6, Gtk.PositionType.LEFT, False)
        self.elapsed_button.connect("clicked", self.create_time_grid)
        self.elapsed_button.set_halign(Gtk.Align.START)

        remaining_label = self.labels['left'].get_text() + "  " + self.labels['time_left'].get_text()
        self.left_button = self._gtk.ButtonImage("hourglass", remaining_label, None, .6, Gtk.PositionType.LEFT, False)
        self.left_button.connect("clicked", self.create_time_grid)
        self.left_button.set_halign(Gtk.Align.START)

        szfe = Gtk.Grid()
        szfe.attach(self.speed_button, 0, 0, 1, 1)
        szfe.attach(self.z_button, 1, 0, 1, 1)
        szfe.attach(self.extrusion_button, 0, 1, 1, 1)
        szfe.attach(self.fan_button, 1, 1, 1, 1)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info.get_style_context().add_class("printing-info")
        info.add(self.labels['temp_grid'])
        info.add(szfe)
        info.add(self.elapsed_button)
        info.add(self.left_button)
        self.switch_info(info)

    def create_extrusion_grid(self, widget=None):
        self.main_status_displayed = False
        goback = self._gtk.ButtonImage("back", None, "color1", .66, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.create_status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")

        info = Gtk.Grid()
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels['flow'], 1, 0, 1, 1)
        info.attach(self.labels['extrude_factor'], 2, 0, 1, 1)
        info.attach(self.labels['flowrate_lbl'], 1, 1, 1, 1)
        info.attach(self.labels['flowrate'], 2, 1, 1, 1)
        info.attach(self.labels['pa_lbl'], 1, 2, 1, 1)
        info.attach(self.labels['advance'], 2, 2, 1, 1)
        info.attach(self.labels['fila_used_lbl'], 1, 3, 1, 1)
        info.attach(self.labels['filament_used'], 2, 3, 1, 1)
        info.attach(self.labels['fila_total_lbl'], 1, 4, 1, 1)
        info.attach(self.labels['filament_total'], 2, 4, 1, 1)
        self.switch_info(info)

    def create_move_grid(self, widget=None):
        self.main_status_displayed = False
        goback = self._gtk.ButtonImage("back", None, "color2", .66, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.create_status_grid)
        goback.set_hexpand(False)
        goback.get_style_context().add_class("printing-info")

        pos_box = Gtk.Box(spacing=5)
        pos_box.add(self.labels['pos_x'])
        pos_box.add(self.labels['pos_y'])
        pos_box.add(self.labels['pos_z'])

        info = Gtk.Grid()
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels['speed_lbl'], 1, 0, 1, 1)
        info.attach(self.labels['req_speed'], 2, 0, 1, 1)
        info.attach(self.labels['accel_lbl'], 1, 1, 1, 1)
        info.attach(self.labels['max_accel'], 2, 1, 1, 1)
        info.attach(pos_box, 1, 2, 2, 1)
        info.attach(self.labels['zoffset_lbl'], 1, 3, 1, 1)
        info.attach(self.labels['zoffset'], 2, 3, 1, 1)
        info.attach(self.labels['height_lbl'], 1, 4, 1, 1)
        info.attach(self.labels['height'], 2, 4, 1, 1)
        info.attach(self.labels['layer_lbl'], 1, 5, 1, 1)
        info.attach(self.labels['layer'], 2, 5, 1, 1)
        self.switch_info(info)

    def create_time_grid(self, widget=None):
        self.main_status_displayed = False
        goback = self._gtk.ButtonImage("back", None, "color3", .66, Gtk.PositionType.TOP, False)
        goback.connect("clicked", self.create_status_grid)
        goback.set_hexpand(False)

        info = Gtk.Grid()
        info.get_style_context().add_class("printing-info-secondary")
        info.attach(goback, 0, 0, 1, 6)
        info.attach(self.labels['elapsed'], 1, 0, 1, 1)
        info.attach(self.labels['duration'], 2, 0, 1, 1)
        info.attach(self.labels['total'], 1, 1, 1, 1)
        info.attach(self.labels['est_time'], 2, 1, 1, 1)
        info.attach(self.labels['left'], 1, 2, 1, 1)
        info.attach(self.labels['time_left'], 2, 2, 1, 1)
        info.attach(self.labels['slicer'], 1, 3, 1, 1)
        info.attach(self.labels['slicer_time'], 2, 3, 1, 1)
        info.attach(self.labels['file_tlbl'], 1, 4, 1, 1)
        info.attach(self.labels['file_time'], 2, 4, 1, 1)
        info.attach(self.labels['fila_tlbl'], 1, 5, 1, 1)
        info.attach(self.labels['filament_time'], 2, 5, 1, 1)
        self.switch_info(info)

    def switch_info(self, info):
        if self._screen.vertical_mode:
            self.labels['info_grid'].remove_row(1)
            self.labels['info_grid'].attach(info, 0, 1, 1, 1)
        else:
            self.labels['info_grid'].remove_column(1)
            self.labels['info_grid'].attach(info, 1, 0, 1, 1)
        self.labels['info_grid'].show_all()

    def on_draw(self, da, ctx):
        w = da.get_allocated_width()
        h = da.get_allocated_height()
        r = min(w, h) * .42

        ctx.set_source_rgb(0.13, 0.13, 0.13)
        ctx.set_line_width(self._gtk.get_font_size() * .75)
        ctx.translate(w / 2, h / 2)
        ctx.arc(0, 0, r, 0, 2 * pi)
        ctx.stroke()
        ctx.set_source_rgb(0.718, 0.110, 0.110)
        ctx.arc(0, 0, r, 3 / 2 * pi, 3 / 2 * pi + (self.progress * 2 * pi))
        ctx.stroke()

    def activate(self):

        ps = self._printer.get_stat("print_stats")
        self.set_state(ps['state'])
        if self.state_timeout is None:
            self.state_timeout = GLib.timeout_add_seconds(1, self.state_check)
        self.create_status_grid()

    def create_buttons(self):

        self.buttons = {
            'cancel': self._gtk.ButtonImage("stop", _("Cancel"), "color2"),
            'control': self._gtk.ButtonImage("settings", _("Settings"), "color3"),
            'fine_tune': self._gtk.ButtonImage("fine-tune", _("Fine Tuning"), "color4"),
            'menu': self._gtk.ButtonImage("complete", _("Main Menu"), "color4"),
            'pause': self._gtk.ButtonImage("pause", _("Pause"), "color1"),
            'restart': self._gtk.ButtonImage("refresh", _("Restart"), "color3"),
            'resume': self._gtk.ButtonImage("resume", _("Resume"), "color1"),
            'save_offset_probe': self._gtk.ButtonImage("home-z", _("Save Z") + "\n" + "Probe", "color1"),
            'save_offset_endstop': self._gtk.ButtonImage("home-z", _("Save Z") + "\n" + "Endstop", "color2"),
        }
        self.buttons['cancel'].connect("clicked", self.cancel)
        self.buttons['control'].connect("clicked", self._screen._go_to_submenu, "")
        self.buttons['fine_tune'].connect("clicked", self.menu_item_clicked, "fine_tune", {
            "panel": "fine_tune", "name": _("Fine Tuning")})
        self.buttons['menu'].connect("clicked", self.close_panel)
        self.buttons['pause'].connect("clicked", self.pause)
        self.buttons['restart'].connect("clicked", self.restart)
        self.buttons['resume'].connect("clicked", self.resume)
        self.buttons['save_offset_probe'].connect("clicked", self.save_offset, "probe")
        self.buttons['save_offset_endstop'].connect("clicked", self.save_offset, "endstop")

    def save_offset(self, widget, device):

        saved_z_offset = 0
        if self._printer.config_section_exists("probe"):
            saved_z_offset = float(self._screen.printer.get_config_section("probe")['z_offset'])
        elif self._printer.config_section_exists("bltouch"):
            saved_z_offset = float(self._screen.printer.get_config_section("bltouch")['z_offset'])

        if self.zoffset > 0:
            sign = "+"
        else:
            sign = "-"
        label = Gtk.Label()
        if device == "probe":
            label.set_text(_("Apply %s%.2f offset to Probe?") % (sign, abs(self.zoffset))
                           + "\n\n"
                           + _("Saved offset: %s") % saved_z_offset)
        elif device == "endstop":
            label.set_text(_("Apply %.2f offset to Endstop?") % self.zoffset)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = self._gtk.HomogeneousGrid()
        grid.attach(label, 0, 0, 1, 1)
        buttons = [
            {"name": _("Apply"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        self._gtk.Dialog(self._screen, buttons, grid, self.save_confirm, device)

    def save_confirm(self, widget, response_id, device):
        if response_id == Gtk.ResponseType.APPLY:
            if device == "probe":
                self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_PROBE")
            if device == "endstop":
                self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_ENDSTOP")
            self._screen._ws.klippy.gcode_script("SAVE_CONFIG")
        widget.destroy()

    def restart(self, widget):
        if self.filename != "none":
            self._screen._ws.klippy.print_start(self.filename)
            self.new_print()

    def resume(self, widget):
        self._screen._ws.klippy.print_resume(self._response_callback, "enable_button", "pause", "cancel")
        self._screen.show_all()

    def pause(self, widget):
        self._screen._ws.klippy.print_pause(self._response_callback, "enable_button", "resume", "cancel")
        self._screen.show_all()

    def cancel(self, widget):

        buttons = [
            {"name": _("Cancel Print"), "response": Gtk.ResponseType.OK},
            {"name": _("Go Back"), "response": Gtk.ResponseType.CANCEL}
        ]

        label = Gtk.Label()
        label.set_markup(_("Are you sure you wish to cancel this print?"))
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self._gtk.Dialog(self._screen, buttons, label, self.cancel_confirm)
        self.disable_button("pause", "cancel")

    def cancel_confirm(self, widget, response_id):
        widget.destroy()

        if response_id == Gtk.ResponseType.CANCEL:
            self.enable_button("pause", "cancel")
            return

        logging.debug("Canceling print")
        self.set_state("cancelling")
        self.disable_button("pause", "resume", "cancel")
        self._screen._ws.klippy.print_cancel(self._response_callback)

    def _response_callback(self, response, method, params, func=None, *args):
        if func == "enable_button":
            self.enable_button(*args)

    def close_panel(self, widget=None):
        logging.debug("Closing job_status panel")
        self.remove_close_timeout()
        self.state_check()
        if self.state not in ["printing", "paused"]:
            self._screen.printer_ready()
        return False

    def remove_close_timeout(self):
        if self.close_timeout is not None:
            GLib.source_remove(self.close_timeout)
            self.close_timeout = None

    def enable_button(self, *args):
        for arg in args:
            self.buttons[arg].set_sensitive(True)

    def disable_button(self, *args):
        for arg in args:
            self.buttons[arg].set_sensitive(False)

    def _callback_metadata(self, newfiles, deletedfiles, modifiedfiles):
        if bool(self.file_metadata) is False and self.filename in modifiedfiles:
            self.update_file_metadata()
            self._files.remove_file_callback(self._callback_metadata)

    def new_print(self):
        self.remove_close_timeout()
        if self.state_timeout is None:
            self.state_timeout = GLib.timeout_add_seconds(1, self.state_check)
        self._screen.wake_screen()
        self.state_check()

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            if "action:cancel" in data:
                self.set_state("cancelling")
            elif "action:paused" in data:
                self.set_state("paused")
            elif "action:resumed" in data:
                self.set_state("printing")
            return
        elif action != "notify_status_update":
            return

        if self.main_status_displayed:
            for x in self._printer.get_tools():
                self.update_temp(
                    x,
                    self._printer.get_dev_stat(x, "temperature"),
                    self._printer.get_dev_stat(x, "target")
                )
                self.extruder_button[x].set_label(self.labels[x].get_text())
            for x in self._printer.get_heaters():
                if x in self.labels:
                    self.update_temp(
                        x,
                        self._printer.get_dev_stat(x, "temperature"),
                        self._printer.get_dev_stat(x, "target")
                    )
                    self.heater_button[x].set_label(self.labels[x].get_text())

        self.update_message()

        if "toolhead" in data and "extruder" in data["toolhead"]:
            if self.current_extruder is not None and data["toolhead"]["extruder"] != self.current_extruder:
                self.labels['temp_grid'].remove_column(0)
                self.labels['temp_grid'].insert_column(0)
                self.current_extruder = data["toolhead"]["extruder"]
                self.labels['temp_grid'].attach(self.extruder_button[self.current_extruder], 0, 0, 1, 1)
                self._screen.show_all()
            if "max_accel" in data["toolhead"]:
                self.labels['max_accel'].set_text("%d mm/s²" % (data["toolhead"]["max_accel"]))

        if "extruder" in data and "pressure_advance" in data['extruder']:
            self.labels['advance'].set_text("%.2f" % data['extruder']['pressure_advance'])

        if "gcode_move" in data:
            if "gcode_position" in data["gcode_move"]:
                self.labels['pos_x'].set_text("X: %6.2f" % (data["gcode_move"]["gcode_position"][0]))
                self.labels['pos_y'].set_text("Y: %6.2f" % (data["gcode_move"]["gcode_position"][1]))
                self.labels['pos_z'].set_text("Z: %6.2f" % (data["gcode_move"]["gcode_position"][2]))
                self.pos_z = data["gcode_move"]["gcode_position"][2]
                if self.main_status_displayed:
                    self.z_button.set_label(self.labels['pos_z'].get_text())
                now = time.time()
                pos = data["gcode_move"]["gcode_position"]
                if self.prev_gpos is not None:
                    interval = now - self.prev_gpos[1]
                    # Calculate Velocity
                    vel = [(pos[0] - self.prev_gpos[0][0]),
                           (pos[1] - self.prev_gpos[0][1]),
                           (pos[2] - self.prev_gpos[0][2])]
                    vel = array(vel)
                    self.velstore.append(sqrt(vel.dot(vel)) / interval)
                self.prev_gpos = [pos, now]
            if "extrude_factor" in data["gcode_move"]:
                self.extrusion = int(round(data["gcode_move"]["extrude_factor"] * 100))
                self.labels['extrude_factor'].set_text("%3d%%" % self.extrusion)
                if self.main_status_displayed:
                    self.extrusion_button.set_label("%3d%%" % self.extrusion)
            if "speed_factor" in data["gcode_move"]:
                self.speed = int(round(data["gcode_move"]["speed_factor"] * 100))
                self.speed_factor = float(data["gcode_move"]["speed_factor"])
                self.labels['speed_factor'].set_text("%3d%%" % self.speed)
            if "speed" in data["gcode_move"]:
                self.req_speed = int(round(data["gcode_move"]["speed"] / 60 * self.speed_factor))
            if "homing_origin" in data["gcode_move"]:
                self.zoffset = data["gcode_move"]["homing_origin"][2]
                self.labels['zoffset'].set_text("%.2f" % self.zoffset)
            if "motion_report" in data:
                if 'live_position' in data["motion_report"]:
                    now = time.time()
                    pos = data["motion_report"]["live_position"]
                    if self.prev_pos is not None:
                        interval = (now - self.prev_pos[1])
                        # Calculate Flowrate
                        evelocity = (pos[3] - self.prev_pos[0][3]) / interval
                        self.flowstore.append(self.fila_section * evelocity)
                        # Calculate Velocity
                        vel = [(pos[0] - self.prev_pos[0][0]),
                               (pos[1] - self.prev_pos[0][1]),
                               (pos[2] - self.prev_pos[0][2])]
                        vel = array(vel)
                        self.velstore.append(sqrt(vel.dot(vel)) / interval)
                    self.prev_pos = [pos, now]
                if "live_velocity" in data["motion_report"]:
                    self.velstore.append(data["motion_report"]["live_velocity"])
                if "live_extruder_velocity" in data["motion_report"]:
                    self.flowstore.append(self.flowrate)

        for fan in self.fans:
            if fan in data and "speed" in data[fan]:
                fan_speed = int(round(self._printer.get_fan_speed(fan, data[fan]["speed"]), 2) * 100)
                self.fans[fan]['speed'] = ("%3d%%" % fan_speed)
        fan_label = ""
        for fan in self.fans:
            fan_label += self.fans[fan]['name'] + self.fans[fan]['speed'] + " "
        self.labels['fan'].set_text(fan_label[:12])

        if "layer_height" in self.file_metadata and "object_height" in self.file_metadata:
            layer_label = str(1 + round((self.pos_z - self.f_layer_h) / self.layer_h))
            layer_label += " / " + self.labels['total_layers'].get_text()
            self.labels['layer'].set_label(layer_label)

        self.state_check()
        if self.state not in ["printing", "paused"]:
            return

        ps = self._printer.get_stat("print_stats")
        if int(ps['print_duration']) == 0 and self.progress > 0.001:
            # Print duration remains at 0 when using No-extusion tests
            duration = ps['total_duration']
        else:
            duration = ps['print_duration']
        if 'filament_used' in ps:
            fila_used = float(ps['filament_used'])
            self.labels['filament_used'].set_text("%.1f m" % (fila_used / 1000))
        if 'filename' in ps and (ps['filename'] != self.filename):
            logging.debug("Changing filename: '%s' to '%s'" % (self.filename, ps['filename']))
            self.update_filename()
        else:
            self.update_percent_complete()
        self.update_text("duration", str(self._gtk.formatTimeString(duration)))
        self.update_text("time_left", self.calculate_time_left(duration, ps['filament_used']))

        if self.main_status_displayed:
            self.fan_button.set_label(self.labels['fan'].get_text())
            elapsed_label = self.labels['elapsed'].get_text() + "  " + self.labels['duration'].get_text()
            self.elapsed_button.set_label(elapsed_label)
            remaining_label = self.labels['left'].get_text() + "  " + self.labels['time_left'].get_text()
            self.left_button.set_label(remaining_label)
        if self.vel_timeout is None:
            self.vel_timeout = GLib.timeout_add_seconds(1, self.update_velocity)

    def update_velocity(self):
        if len(self.velstore) > 0:
            self.vel = (self.vel + median(array(self.velstore))) / 2
            self.velstore = []
        if len(self.flowstore) > 0:
            self.flowrate = (self.flowrate + median(array(self.flowstore))) / 2
            self.flowstore = []

        self.labels['flowrate'].set_label("%.1f mm³/s" % self.flowrate)
        self.labels['req_speed'].set_text("%d/%d mm/s" % (self.vel, self.req_speed))
        if self.main_status_displayed:
            self.speed_button.set_label("%3d%% %5d mm/s" % (self.speed, self.vel))
            self.extrusion_button.set_label("%3d%% %5.1f mm³/s" % (self.extrusion, self.flowrate))
        return True

    def calculate_time_left(self, duration=0, filament_used=0):
        total_duration = None
        if self.progress < 1:
            slicer_time = filament_time = file_time = None
            timeleft_type = self._config.get_config()['main'].get('print_estimate_method', 'auto')
            slicer_correction = (self._config.get_config()['main'].getint('print_estimate_compensation', 100) / 100)
            # speed_factor compensation based on empirical testing
            spdcomp = sqrt(self.speed_factor)

            if "estimated_time" in self.file_metadata:
                if self.file_metadata['estimated_time'] > 0:
                    slicer_time = (self.file_metadata['estimated_time'] * slicer_correction) / spdcomp
                    if slicer_time < duration:
                        slicer_time = None
                        self.update_text("slicer_time", "-")
                    else:
                        self.update_text("slicer_time", str(self._gtk.formatTimeString(slicer_time)))

            if "filament_total" in self.file_metadata:
                if self.file_metadata['filament_total'] > 0 and filament_used > 0:
                    if self.file_metadata['filament_total'] > filament_used:
                        filament_time = duration / (filament_used / self.file_metadata['filament_total'])
                        if filament_time < duration:
                            filament_time = None
                        self.update_text("filament_time", "-")
                    else:
                        self.update_text("filament_time", str(self._gtk.formatTimeString(slicer_time)))

            if self.progress > 0:
                file_time = duration / self.progress
                self.update_text("file_time", str(self._gtk.formatTimeString(file_time)))
            else:
                self.update_text("file_time", "-")

            if timeleft_type == "file" and file_time is not None:
                total_duration = file_time
            elif timeleft_type == "filament" and filament_time is not None:
                total_duration = filament_time
            elif slicer_time is not None:
                if timeleft_type == "slicer":
                    total_duration = slicer_time
                else:
                    if filament_time is not None and self.progress > 0.14:
                        # Weighted arithmetic mean (Slicer is the most accurate)
                        total_duration = (slicer_time * 3 + filament_time + file_time) / 5
                    else:
                        # At the begining file and filament are innacurate
                        total_duration = slicer_time
            elif file_time is not None:
                if filament_time is not None:
                    total_duration = (filament_time + file_time) / 2
                else:
                    total_duration = file_time

        if total_duration is not None:
            self.update_text("est_time", str(self._gtk.formatTimeString(total_duration)))
            return str(self._gtk.formatTimeString((total_duration - duration)))
        else:
            return "-"

    def state_check(self):
        ps = self._printer.get_stat("print_stats")

        if ps['state'] == self.state:
            return True

        if ps['state'] == "printing":
            if self.state == "cancelling":
                return True
            self.set_state("printing")
            self.update_filename()
        elif ps['state'] == "complete":
            self.progress = 1
            self.update_progress()
            self.set_state("complete")
            self._screen.wake_screen()
            self.remove_close_timeout()
            timeout = self._config.get_main_config().getint("job_complete_timeout", 0)
            if timeout != 0:
                self.close_timeout = GLib.timeout_add_seconds(timeout, self.close_panel)
            return False
        elif ps['state'] == "error":
            logging.debug("Error!")
            self.set_state("error")
            self.labels['status'].set_text("%s" % (_("Error")))
            self._screen.show_popup_message(ps['message'])
            self._screen.wake_screen()
            self.remove_close_timeout()
            timeout = self._config.get_main_config().getint("job_error_timeout", 0)
            if timeout != 0:
                self.close_timeout = GLib.timeout_add_seconds(timeout, self.close_panel)
            return False
        elif ps['state'] == "cancelled":
            # Print was cancelled
            self.set_state("cancelled")
            self._screen.wake_screen()
            self.remove_close_timeout()
            timeout = self._config.get_main_config().getint("job_cancelled_timeout", 0)
            if timeout != 0:
                self.close_timeout = GLib.timeout_add_seconds(timeout, self.close_panel)
            return False
        elif ps['state'] == "paused":
            self.set_state("paused")
        elif ps['state'] == "standby":
            self.set_state("standby")
        return True

    def set_state(self, state):

        if self.state != state:
            logging.debug("Changing job_status state from '%s' to '%s'" % (self.state, state))
        if state == "paused":
            self.update_text("status", _("Paused"))
        elif state == "printing":
            self.update_text("status", _("Printing"))
        elif state == "cancelling":
            self.update_text("status", _("Cancelling"))
        elif state == "cancelled" or (state == "standby" and self.state == "cancelling"):
            self.update_text("status", _("Cancelled"))
        elif state == "complete":
            self.update_text("status", _("Complete"))
        self.state = state
        self.show_buttons_for_state()

    def show_buttons_for_state(self):
        self.buttons['button_grid'].remove_row(0)
        self.buttons['button_grid'].insert_row(0)
        if self.state == "printing":
            self.buttons['button_grid'].attach(self.buttons['pause'], 0, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['cancel'], 1, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['fine_tune'], 2, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['control'], 3, 0, 1, 1)
            self.enable_button("pause", "cancel")
        elif self.state == "paused":
            self.buttons['button_grid'].attach(self.buttons['resume'], 0, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['cancel'], 1, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['fine_tune'], 2, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['control'], 3, 0, 1, 1)
            self.enable_button("resume", "cancel")
        else:
            if self.zoffset != 0:
                endstop = (self._screen.printer.config_section_exists("stepper_z") and
                           not self._screen.printer.get_config_section("stepper_z")['endstop_pin'].startswith("probe"))
                if endstop:
                    self.buttons['button_grid'].attach(self.buttons["save_offset_endstop"], 0, 0, 1, 1)
                else:
                    self.buttons['button_grid'].attach(Gtk.Label(""), 0, 0, 1, 1)
                if self._printer.config_section_exists("probe") or self._printer.config_section_exists("bltouch"):
                    self.buttons['button_grid'].attach(self.buttons["save_offset_probe"], 1, 0, 1, 1)
                else:
                    self.buttons['button_grid'].attach(Gtk.Label(""), 1, 0, 1, 1)
            else:
                self.buttons['button_grid'].attach(Gtk.Label(""), 0, 0, 1, 1)
                self.buttons['button_grid'].attach(Gtk.Label(""), 1, 0, 1, 1)

            if self.filename is not None:
                self.buttons['button_grid'].attach(self.buttons['restart'], 2, 0, 1, 1)
            self.buttons['button_grid'].attach(self.buttons['menu'], 3, 0, 1, 1)
        self.show_all()

    def show_file_thumbnail(self):
        if self._files.has_thumbnail(self.filename):
            pixbuf = self.get_file_image(self.filename, 5, 4)
            if pixbuf is not None:
                self.labels['thumbnail'].set_from_pixbuf(pixbuf)

    def update_filename(self):
        self.filename = self._printer.get_stat('print_stats', 'filename')
        self.update_text("file", os.path.splitext(self.filename)[0])
        self.filename_label = {
            "complete": self.labels['file'].get_label(),
            "current": self.labels['file'].get_label(),
            "position": 0,
            "limit": 24,
            "length": len(self.labels['file'].get_label())
        }

        if self.animation_timeout is None:
            # if self.labels['file'].is_ellipsized(): <- currently this doesn't work
            if (self.filename_label['length'] - self.filename_label['limit']) > 0:
                self.animation_timeout = GLib.timeout_add_seconds(1, self.animate_label)
        self.update_percent_complete()
        self.update_file_metadata()

    def animate_label(self):
        pos = self.filename_label['position']
        current = self.filename_label['current']
        complete = self.filename_label['complete']

        if pos > (self.filename_label['length'] - self.filename_label['limit']):
            self.filename_label['position'] = 0
            self.labels['file'].set_label(complete)
        else:
            self.labels['file'].set_label(current[pos:self.filename_label['length']])
            self.filename_label['position'] += 1
        return True

    def update_file_metadata(self):
        if self._files.file_metadata_exists(self.filename):
            self.file_metadata = self._files.get_file_info(self.filename)
            logging.info("Update Metadata. File: %s Size: %s" % (self.filename, self.file_metadata['size']))
            if "estimated_time" in self.file_metadata and self.timeleft_type == "slicer":
                self.update_text("est_time",
                                 str(self._gtk.formatTimeString(self.file_metadata['estimated_time'])))
            if "thumbnails" in self.file_metadata:
                tmp = self.file_metadata['thumbnails'].copy()
                for i in tmp:
                    i['data'] = ""
            self.show_file_thumbnail()
            if "object_height" in self.file_metadata:
                self.height = float(self.file_metadata['object_height'])
                self.labels['height'].set_label(str(self.height) + " mm")
                if "layer_height" in self.file_metadata:
                    self.layer_h = float(self.file_metadata['layer_height'])
                    if "first_layer_height" in self.file_metadata:
                        self.f_layer_h = float(self.file_metadata['first_layer_height'])
                    else:
                        self.f_layer_h = self.layer_h
                    self.labels['total_layers'].set_label(str(int((self.height - self.f_layer_h) / self.layer_h) + 1))
            if "filament_total" in self.file_metadata:
                filament_total = float(self.file_metadata['filament_total']) / 1000
                self.labels['filament_total'].set_text("%.1f m" % filament_total)
        else:
            self.file_metadata = {}
            logging.debug("Cannot find file metadata. Listening for updated metadata")
            self._screen.files.add_file_callback(self._callback_metadata)

    def update_image_text(self, label, text):
        if label in self.labels and 'l' in self.labels[label]:
            self.labels[label]['l'].set_text(text)

    def update_percent_complete(self):
        if self.state not in ["printing", "paused"]:
            return

        if "gcode_start_byte" in self.file_metadata:
            progress = (max(self._printer.get_stat('virtual_sdcard', 'file_position') -
                            self.file_metadata['gcode_start_byte'], 0) / (self.file_metadata['gcode_end_byte'] -
                                                                          self.file_metadata['gcode_start_byte']))
        else:
            progress = self._printer.get_stat('virtual_sdcard', 'progress')

        if progress != self.progress:
            self.progress = progress
            self.labels['darea'].queue_draw()
            self.update_progress()

    def update_text(self, label, text):
        if label in self.labels:
            self.labels[label].set_text(text)

    def update_progress(self):
        if self.progress < 1:
            self.labels['progress_text'].set_text("%s%%" % (str((int(self.progress * 100)))))
        else:
            self.labels['progress_text'].set_text("100")

    def update_message(self):
        msg = self._printer.get_stat("display_status", "message")
        if msg is None:
            msg = " "
        self.labels['lcdmessage'].set_text(str(msg))

    def update_temp(self, x, temp, target):
        if x in self.labels and temp is not None:
            if target is not None and target > 0:
                self.labels[x].set_label("%3d/%3d°" % (temp, target))
            else:
                self.labels[x].set_label("%3d°" % temp)
