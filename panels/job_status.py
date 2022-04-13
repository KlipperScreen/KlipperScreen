# -*- coding: utf-8 -*-
import gi
import logging
import math
import os

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return JobStatusPanel(*args)

class JobStatusPanel(ScreenPanel):
    is_paused = False
    filename = None
    file_metadata = {}
    progress = 0
    state = "standby"
    zoffset = 0

    def __init__(self, screen, title, back=False):
        super().__init__(screen, title, False)

    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.timeleft_type = "file"
        self.state_timeout = None
        self.close_timeouts = []

        self.create_buttons()

        self.labels['button_grid'] = self._gtk.HomogeneousGrid()
        self.labels['button_grid'].set_vexpand(False)

        fi_box = Gtk.VBox(spacing=0)
        fi_box.set_hexpand(True)
        fi_box.set_vexpand(False)
        fi_box.set_halign(Gtk.Align.START)

        self.labels['file'] = Gtk.Label("Filename")
        self.labels['file'].set_halign(Gtk.Align.START)
        self.labels['file'].set_vexpand(False)
        self.labels['file'].get_style_context().add_class("printing-filename")
        self.labels['file'].set_ellipsize(True)
        self.labels['file'].set_ellipsize(Pango.EllipsizeMode.END)
        self.labels['status'] = Gtk.Label("Status")
        self.labels['status'].set_halign(Gtk.Align.START)
        self.labels['status'].set_vexpand(False)
        self.labels['status'].get_style_context().add_class("printing-status")
        self.labels['status'].set_ellipsize(True)
        self.labels['status'].set_ellipsize(Pango.EllipsizeMode.END)
        self.labels['lcdmessage'] = Gtk.Label("Message")
        self.labels['lcdmessage'].set_halign(Gtk.Align.START)
        self.labels['lcdmessage'].set_vexpand(False)
        self.labels['lcdmessage'].get_style_context().add_class("printing-status")
        self.labels['lcdmessage'].set_ellipsize(True)
        self.labels['lcdmessage'].set_ellipsize(Pango.EllipsizeMode.END)

        fi_box.add(self.labels['file'])
        fi_box.add(self.labels['status'])
        fi_box.add(self.labels['lcdmessage'])
        fi_box.set_valign(Gtk.Align.CENTER)

        self.labels['darea'] = Gtk.DrawingArea()
        self.labels['darea'].connect("draw", self.on_draw)

        box = Gtk.Box()
        box.set_hexpand(True)
        box.set_vexpand(True)
        box.set_halign(Gtk.Align.CENTER)
        self.labels['progress_text'] = Gtk.Label("0 %")
        self.labels['progress_text'].get_style_context().add_class("printing-progress-text")
        box.add(self.labels['progress_text'])

        overlay = Gtk.Overlay()
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        overlay.add(self.labels['darea'])
        overlay.add_overlay(box)

        self.labels['thumbnail'] = self._gtk.Image("file", 2)
        self.labels['thumbnail'].set_size_request(self._screen.width/3, 0)

        self.labels['heater_bed'] = Gtk.Label("-/-")
        self.labels['left'] = Gtk.Label(_("Left:"))
        self.labels['left'].set_halign(Gtk.Align.START)
        self.labels['time_left'] = Gtk.Label("-")
        self.labels['elapsed'] = Gtk.Label(_("Elapsed:"))
        self.labels['elapsed'].set_halign(Gtk.Align.START)
        self.labels['duration'] = Gtk.Label("-")
        self.labels['total'] = Gtk.Label(_("Total:"))
        self.labels['total'].set_halign(Gtk.Align.START)
        self.labels['est_time'] = Gtk.Label("-")
        self.labels['total'] = Gtk.Label(_("Total:"))
        self.labels['total'].set_halign(Gtk.Align.START)
        self.labels['slicer'] = Gtk.Label(_("Slicer:"))
        self.labels['slicer'].set_halign(Gtk.Align.START)
        self.labels['slicer_time'] = Gtk.Label("-")
        self.labels['file_tlbl'] = Gtk.Label(_("File:"))
        self.labels['file_tlbl'].set_halign(Gtk.Align.START)
        self.labels['file_time'] = Gtk.Label("-")
        self.labels['fila_tlbl'] = Gtk.Label(_("Filament:"))
        self.labels['fila_tlbl'].set_halign(Gtk.Align.START)
        self.labels['filament_time'] = Gtk.Label("-")
        self.labels['pos_x'] = Gtk.Label("X: -")
        self.labels['pos_y'] = Gtk.Label("Y: -")
        self.labels['pos_z'] = Gtk.Label("Z: -")
        self.labels['speed_lbl'] = Gtk.Label(_("Speed:"))
        self.labels['speed_lbl'].set_halign(Gtk.Align.START)
        self.labels['speed'] = Gtk.Label("-")
        self.labels['cur_speed'] = Gtk.Label("-")
        self.labels['accel_lbl'] = Gtk.Label(_("Acceleration:"))
        self.labels['accel_lbl'].set_halign(Gtk.Align.START)
        self.labels['max_accel'] = Gtk.Label("-")
        self.labels['flow'] = Gtk.Label(_("Flow:"))
        self.labels['flow'].set_halign(Gtk.Align.START)
        self.labels['extrusion'] = Gtk.Label("-")
        self.labels['flowrate'] = Gtk.Label(_("Flowrate:"))
        self.labels['flowrate'].set_halign(Gtk.Align.START)
        self.labels['fan'] = Gtk.Label("-")
        self.labels['zoffset_lbl'] = Gtk.Label(_("Z offset:"))
        self.labels['zoffset_lbl'].set_halign(Gtk.Align.START)
        self.labels['zoffset'] = Gtk.Label("-")
        self.labels['layer_lbl'] = Gtk.Label(_("Layer:"))
        self.labels['layer_lbl'].set_halign(Gtk.Align.START)
        self.labels['layer'] = Gtk.Label("-")
        self.labels['layer'].set_halign(Gtk.Align.START)
        self.labels['fila_used_lbl'] = Gtk.Label("Filament used:")
        self.labels['fila_used_lbl'].set_halign(Gtk.Align.START)
        self.labels['filament_used'] = Gtk.Label("-")
        self.labels['filament_used'].set_halign(Gtk.Align.START)
        self.labels['pa_lbl'] = Gtk.Label("Pressure Advance:")
        self.labels['pa_lbl'].set_halign(Gtk.Align.START)
        self.labels['advance'] = Gtk.Label("-")
        self.labels['advance'].set_halign(Gtk.Align.START)

        self.labels['info_grid'] = Gtk.Grid()
        if self._screen.vertical_mode:
            self.labels['info_grid'].attach(self.labels['thumbnail'], 0, 0, 1, 1)
            self.labels['info_grid'].attach(info, 0, 1, 1, 1)
        else:
            self.labels['info_grid'].attach(self.labels['thumbnail'], 0, 0, 1, 1)
            self.create_status_grid()

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        grid.attach(overlay, 0, 0, 1, 1)
        grid.attach(fi_box, 1, 0, 3, 1)
        grid.attach(self.labels['info_grid'], 0, 1, 4, 2)
        grid.attach(self.labels['button_grid'], 0, 3, 4, 1)

        self.grid = grid
        self.content.add(grid)
        self._screen.wake_screen()

    def create_status_grid(self, widget=None):
        self.labels['info_grid'].remove_column(1)
        temp = self._gtk.ButtonImage("heat-up", None, None, .6)
        position = self._gtk.ButtonImage("move", None, None, .6)
        position.connect("clicked", self.create_speed_grid)
        clock = self._gtk.ButtonImage("clock", None, None, .6)
        clock.connect("clicked", self.create_time_grid)
        hourglass = self._gtk.ButtonImage("hourglass", None, None, .6)
        hourglass.connect("clicked", self.create_time_grid)

        i = 0
        for extruder in self._printer.get_tools():
            self.labels[extruder + '_box'] = Gtk.Box(spacing=0)
            self.labels[extruder] = Gtk.Label("0/0")
            if i <= 4:
                ext_img = self._gtk.Image("extruder-%s" % i, .6)
                self.labels[extruder + '_box'].add(ext_img)
            self.labels[extruder + '_box'].add(self.labels[extruder])
            i += 1
        temp_grid = self._gtk.HomogeneousGrid()
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        temp_grid.attach(self.labels[self.current_extruder + '_box'], 1, 0, 1, 1)
        if self._printer.has_heated_bed():
            heater_bed = self._gtk.Image("bed", .6)
            heater_bed_box = Gtk.Box(spacing=0)
            heater_bed_box.add(heater_bed)
            heater_bed_box.add(self.labels['heater_bed'])
            temp_grid.attach(heater_bed_box, 2, 0, 1, 1)
        self.labels['temp_grid'] = temp_grid

        posgrid = self._gtk.HomogeneousGrid()
        posgrid.set_hexpand(True)
        posgrid.attach(self.labels['pos_x'], 0, 0, 1, 1)
        posgrid.attach(self.labels['pos_y'], 1, 0, 1, 1)
        posgrid.attach(self.labels['pos_z'], 2, 0, 1, 1)

        speed = self._gtk.ButtonImage("speed+", None, None, .6)
        speed.connect("clicked", self.create_speed_grid)
        speed_box = Gtk.Box(spacing=0)
        speed_box.add(speed)
        speed_box.add(self.labels['speed'])
        extrusion = self._gtk.ButtonImage("extrude", None, None, .6)
        extrusion.connect("clicked", self.create_extrusion_grid)
        extrusion_box = Gtk.Box(spacing=0)
        extrusion_box.add(extrusion)
        extrusion_box.add(self.labels['extrusion'])
        fan = self._gtk.ButtonImage("fan", None, None, .6)
        fan_box = Gtk.Box(spacing=0)
        fan_box.add(fan)
        fan_box.add(self.labels['fan'])

        sfe_grid = self._gtk.HomogeneousGrid()
        sfe_grid.set_hexpand(True)
        sfe_grid.attach(speed_box, 0, 0, 1, 1)
        sfe_grid.attach(extrusion_box, 1, 0, 1, 1)
        sfe_grid.attach(fan_box, 2, 0, 1, 1)

        itl_box = Gtk.Box(spacing=0)
        itl_box.add(self.labels['left'])
        itl_box.add(self.labels['time_left'])

        it1_box = Gtk.Box(spacing=0)
        it1_box.add(self.labels['elapsed'])
        it1_box.add(self.labels['duration'])

        info = Gtk.Grid()
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.get_style_context().add_class("printing-info-box")
        info.set_valign(Gtk.Align.CENTER)
        info.attach(temp, 0, 0, 1, 1)
        info.attach(self.labels['temp_grid'], 1, 0, 1, 1)
        info.attach(position, 0, 1, 1, 1)
        info.attach(posgrid, 1, 1, 1, 1)
        info.attach(sfe_grid, 0, 2, 2, 1)
        info.attach(clock, 0, 3, 1, 1)
        info.attach(it1_box, 1, 3, 1, 1)
        info.attach(hourglass, 0, 4, 1, 1)
        info.attach(itl_box, 1, 4, 1, 1)
        self.labels['info_grid'].attach(info, 1, 0, 1, 1)
        self.labels['info_grid'].show_all()

    def create_extrusion_grid(self, widget=None):
        self.labels['info_grid'].remove_column(1)
        goback = self._gtk.ButtonImage("back")
        goback.connect("clicked", self.create_status_grid)
        info = Gtk.Grid()
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("printing-info-box")
        info.attach(self.labels['flow'], 1, 0, 1, 1)
        info.attach(self.labels['extrusion'], 2, 0, 1, 1)
        info.attach(self.labels['flowrate'], 1, 1, 1, 1)
        info.attach(Gtk.Label("- mm3/s"), 2, 1, 1, 1)
        info.attach(self.labels['pa_lbl'], 1, 2, 1, 1)
        info.attach(self.labels['advance'], 2, 2, 1, 1)
        info.attach(self.labels['fila_used_lbl'], 1, 3, 1, 1)
        info.attach(self.labels['filament_used'], 2, 3, 1, 1)
        info.attach(goback, 0, 0, 1, 6)
        self.labels['info_grid'].attach(info, 1, 0, 1, 1)
        self.labels['info_grid'].show_all()

    def create_speed_grid(self, widget=None):
        self.labels['info_grid'].remove_column(1)
        goback = self._gtk.ButtonImage("back")
        goback.connect("clicked", self.create_status_grid)

        posgrid = self._gtk.HomogeneousGrid()
        posgrid.set_hexpand(True)
        posgrid.attach(self.labels['pos_x'], 0, 0, 1, 1)
        posgrid.attach(self.labels['pos_y'], 1, 0, 1, 1)
        posgrid.attach(self.labels['pos_z'], 2, 0, 1, 1)

        info = Gtk.Grid()
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("printing-info-box")
        info.attach(self.labels['speed_lbl'], 1, 0, 1, 1)
        info.attach(self.labels['cur_speed'], 2, 0, 1, 1)
        info.attach(self.labels['accel_lbl'], 1, 1, 1, 1)
        info.attach(self.labels['max_accel'], 2, 1, 1, 1)
        info.attach(posgrid, 1, 2, 2, 1)
        info.attach(self.labels['layer_lbl'], 1, 3, 1, 1)
        info.attach(self.labels['layer'], 2, 3, 1, 1)
        info.attach(self.labels['zoffset_lbl'], 1, 4, 1, 1)
        info.attach(self.labels['zoffset'], 2, 4, 1, 1)
        info.attach(goback, 0, 0, 1, 6)
        self.labels['info_grid'].attach(info, 1, 0, 1, 1)
        self.labels['info_grid'].show_all()

    def create_time_grid(self, widget=None):
        self.labels['info_grid'].remove_column(1)
        goback = self._gtk.ButtonImage("back")
        goback.connect("clicked", self.create_status_grid)
        info = Gtk.Grid()
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("printing-info-box")
        info.attach(self._gtk.Image("clock", .6), 1, 0, 1, 1)
        info.attach(self.labels['elapsed'], 2, 0, 1, 1)
        info.attach(self.labels['duration'], 3, 0, 1, 1)
        info.attach(self.labels['total'], 2, 1, 1, 1)
        info.attach(self.labels['est_time'], 3, 1, 1, 1)
        info.attach(self._gtk.Image("hourglass", .6), 1, 2, 1, 1)
        info.attach(self.labels['left'], 2, 2, 1, 1)
        info.attach(self.labels['time_left'], 3, 2, 1, 1)
        info.attach(self.labels['slicer'], 2, 3, 1, 1)
        info.attach(self.labels['slicer_time'], 3, 3, 1, 1)
        info.attach(self.labels['file_tlbl'], 2, 4, 1, 1)
        info.attach(self.labels['file_time'], 3, 4, 1, 1)
        info.attach(self.labels['fila_tlbl'], 2, 5, 1, 1)
        info.attach(self.labels['filament_time'], 3, 5, 1, 1)
        info.attach(goback, 0, 0, 1, 6)
        self.labels['info_grid'].attach(info, 1, 0, 1, 1)
        self.labels['info_grid'].show_all()

    def on_draw(self, da, ctx):
        w = da.get_allocated_width()
        h = da.get_allocated_height()
        r = min(w, h)*.4

        ctx.set_source_rgb(0.6, 0.6, 0.6)
        ctx.set_line_width(self._gtk.get_font_size() * .75)
        ctx.translate(w / 2, h / 2)
        ctx.arc(0, 0, r, 0, 2*math.pi)
        ctx.stroke()

        ctx.set_source_rgb(1, 0, 0)
        ctx.arc(0, 0, r, 3/2*math.pi, 3/2*math.pi+(self.progress*2*math.pi))
        ctx.stroke()

    def activate(self):
        _ = self.lang.gettext
        ps = self._printer.get_stat("print_stats")
        self.set_state(ps['state'])
        if self.state_timeout is None:
            self.state_timeout = GLib.timeout_add_seconds(1, self.state_check)

    def create_buttons(self):
        _ = self.lang.gettext
        self.labels['cancel'] = self._gtk.ButtonImage("stop", _("Cancel"), "color2")
        self.labels['cancel'].connect("clicked", self.cancel)
        self.labels['control'] = self._gtk.ButtonImage("settings", _("Settings"), "color3")
        self.labels['control'].connect("clicked", self._screen._go_to_submenu, "")
        self.labels['fine_tune'] = self._gtk.ButtonImage("fine-tune", _("Fine Tuning"), "color4")
        self.labels['fine_tune'].connect("clicked", self.menu_item_clicked, "fine_tune", {
            "panel": "fine_tune", "name": _("Fine Tuning")})
        self.labels['menu'] = self._gtk.ButtonImage("complete", _("Main Menu"), "color4")
        self.labels['menu'].connect("clicked", self.close_panel)
        self.labels['pause'] = self._gtk.ButtonImage("pause", _("Pause"), "color1")
        self.labels['pause'].connect("clicked", self.pause)
        self.labels['restart'] = self._gtk.ButtonImage("refresh", _("Restart"), "color3")
        self.labels['restart'].connect("clicked", self.restart)
        self.labels['resume'] = self._gtk.ButtonImage("resume", _("Resume"), "color1")
        self.labels['resume'].connect("clicked", self.resume)
        self.labels['save_offset_probe'] = self._gtk.ButtonImage("home-z", _("Save Z") + "\n" + "Probe", "color1")
        self.labels['save_offset_probe'].connect("clicked", self.save_offset_probe)
        self.labels['save_offset_endstop'] = self._gtk.ButtonImage("home-z", _("Save Z") + "\n" + "Endstop", "color2")
        self.labels['save_offset_endstop'].connect("clicked", self.save_offset_endstop)

    def save_offset_probe(self, widget):
        self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_PROBE")
        self._screen._ws.klippy.gcode_script("SAVE_CONFIG")

    def save_offset_endstop(self, widget):
        self._screen._ws.klippy.gcode_script("Z_OFFSET_APPLY_ENDSTOP")
        self._screen._ws.klippy.gcode_script("SAVE_CONFIG")

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
        _ = self.lang.gettext

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
        for to in self.close_timeouts:
            GLib.source_remove(to)
            self.close_timeouts.remove(to)

    def enable_button(self, *args):
        for arg in args:
            self.labels[arg].set_sensitive(True)

    def disable_button(self, *args):
        for arg in args:
            self.labels[arg].set_sensitive(False)

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
        _ = self.lang.gettext

        if self._printer.has_heated_bed():
            self.update_temp(
                "heater_bed",
                self._printer.get_dev_stat("heater_bed", "temperature"),
                self._printer.get_dev_stat("heater_bed", "target")
            )
        for x in self._printer.get_tools():
            self.update_temp(
                x,
                self._printer.get_dev_stat(x, "temperature"),
                self._printer.get_dev_stat(x, "target")
            )

        ps = self._printer.get_stat("print_stats")
        self.update_message()
        logging.info(data)

        if "toolhead" in data:
            if "extruder" in data["toolhead"]:
                if data["toolhead"]["extruder"] != self.current_extruder:
                    self.labels['temp_grid'].remove_column(0)
                    self.labels['temp_grid'].insert_column(0)
                    self.current_extruder = data["toolhead"]["extruder"]
                    self.labels['temp_grid'].attach(self.labels[self.current_extruder + '_box'], 0, 0, 1, 1)
                    self._screen.show_all()
                if "max_accel" in data["toolhead"]:
                    self.labels['max_accel'].set_text("%d mm/s2" % (data["toolhead"]["max_accel"]))

        if "gcode_move" in data:
            if "gcode_position" in data["gcode_move"]:
                self.labels['pos_x'].set_text("X: %.2f" % (data["gcode_move"]["gcode_position"][0]))
                self.labels['pos_y'].set_text("Y: %.2f" % (data["gcode_move"]["gcode_position"][1]))
                self.labels['pos_z'].set_text("Z: %.2f" % (data["gcode_move"]["gcode_position"][2]))
            if "extrude_factor" in data["gcode_move"]:
                self.extrusion = int(round(data["gcode_move"]["extrude_factor"]*100))
                self.labels['extrusion'].set_text("%3d%%" % self.extrusion)
            if "speed_factor" in data["gcode_move"]:
                self.speed = int(round(data["gcode_move"]["speed_factor"]*100))
                self.labels['speed'].set_text("%3d%%" % self.speed)
            if "homing_origin" in data["gcode_move"]:
                self.zoffset = data["gcode_move"]["homing_origin"][2]
                self.labels['zoffset'].set_text("%.2f" % self.zoffset)
            if "speed" in data["gcode_move"]:
                self.cur_speed = int(data["gcode_move"]["speed"]/60)
                self.labels['cur_speed'].set_text("%d mm/s" % self.cur_speed)


        self.labels['filament_used'].set_text("%.1f" % ps['filament_used'])
        if "extruder" in data:
             self.labels['advance'].set_text("%.2f" % data['extruder']['pressure_advance'])

        if "fan" in data and "speed" in data['fan']:
            self.fan = int(round(self._printer.get_fan_speed("fan", data['fan']['speed']), 2)*100)
            self.labels['fan'].set_text("%3d%%" % self.fan)

        self.state_check()
        if self.state not in ["printing", "paused"]:
            return

        if ps['filename'] and (ps['filename'] != self.filename):
            logging.debug("Changing filename: '%s' to '%s'" % (self.filename, ps['filename']))
            self.update_filename()
        else:
            self.update_percent_complete()

        self.update_text("duration", str(self._gtk.formatTimeString(ps['print_duration'])))
        self.update_text("time_left", self.calculate_time_left(ps['print_duration'], ps['filament_used']))

    def calculate_time_left(self, duration=0, filament_used=0):
        total_duration = None
        if self.progress < 1:
            slicer_time = filament_time = file_time = None
            timeleft_type = self._config.get_config()['main'].get('print_estimate_method', 'auto')
            slicer_correction = (self._config.get_config()['main'].getint('print_estimate_compensation', 100) / 100)
            # speed_factor compensation based on empirical testing
            spdcomp = math.sqrt(self.speed / 100)

            if "estimated_time" in self.file_metadata:
                if self.file_metadata['estimated_time'] > 0:
                    slicer_time = (self.file_metadata['estimated_time'] * slicer_correction) / spdcomp
                    if slicer_time < duration:
                        slicer_time = None

            if "filament_total" in self.file_metadata:
                if self.file_metadata['filament_total'] > 0 and filament_used > 0:
                    if self.file_metadata['filament_total'] > filament_used:
                        filament_time = duration / (filament_used / self.file_metadata['filament_total'])
                        if filament_time < duration:
                            filament_time = None

            if self.progress > 0:
                file_time = duration / self.progress

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

        if total_duration is None:
            return "-"
        self.update_text("est_time", str(self._gtk.formatTimeString(total_duration)))
        if slicer_time is not None:
            self.update_text("slicer_time", str(self._gtk.formatTimeString(slicer_time)))
        if file_time is not None:
            self.update_text("file_time", str(self._gtk.formatTimeString(file_time)))
        if filament_time is not None:
            self.update_text("filament_time", str(self._gtk.formatTimeString(filament_time)))
        return str(self._gtk.formatTimeString((total_duration - duration)))

    def state_check(self):
        ps = self._printer.get_stat("print_stats")

        if ps['state'] == self.state:
            return True
        _ = self.lang.gettext

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
            timeout = self._config.get_main_config().getint("job_complete_timeout", 30)
            if timeout != 0:
                self.close_timeouts.append(GLib.timeout_add_seconds(timeout, self.close_panel))
            return False
        elif ps['state'] == "error":
            logging.debug("Error!")
            self.set_state("error")
            self.labels['status'].set_text("%s - %s" % (_("Error"), ps['message']))
            self._screen.wake_screen()
            self.remove_close_timeout()
            timeout = self._config.get_main_config().getint("job_error_timeout", 0)
            if timeout != 0:
                self.close_timeouts.append(GLib.timeout_add_seconds(timeout, self.close_panel))
            return False
        elif ps['state'] == "cancelled":
            # Print was cancelled
            self.set_state("cancelled")
            self._screen.wake_screen()
            self.remove_close_timeout()
            timeout = self._config.get_main_config().getint("job_cancelled_timeout", 0)
            if timeout != 0:
                self.close_timeouts.append(GLib.timeout_add_seconds(timeout, self.close_panel))
            return False
        elif ps['state'] == "paused":
            self.set_state("paused")
        elif ps['state'] == "standby":
            self.set_state("standby")
        return True

    def set_state(self, state):
        _ = self.lang.gettext

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
        self.labels['button_grid'].remove_row(0)
        self.labels['button_grid'].insert_row(0)
        if self.state == "printing":
            self.labels['button_grid'].attach(self.labels['pause'], 0, 0, 1, 1)
            self.labels['button_grid'].attach(self.labels['cancel'], 1, 0, 1, 1)
            self.labels['button_grid'].attach(self.labels['fine_tune'], 2, 0, 1, 1)
            self.labels['button_grid'].attach(self.labels['control'], 3, 0, 1, 1)
            self.enable_button("pause", "cancel")
        elif self.state == "paused":
            self.labels['button_grid'].attach(self.labels['resume'], 0, 0, 1, 1)
            self.labels['button_grid'].attach(self.labels['cancel'], 1, 0, 1, 1)
            self.labels['button_grid'].attach(self.labels['fine_tune'], 2, 0, 1, 1)
            self.labels['button_grid'].attach(self.labels['control'], 3, 0, 1, 1)
            self.enable_button("resume", "cancel")
        else:
            if self.zoffset != 0:
                endstop = (self._screen.printer.config_section_exists("stepper_z") and
                           not self._screen.printer.get_config_section("stepper_z")['endstop_pin'].startswith("probe"))
                if endstop:
                    self.labels['button_grid'].attach(self.labels["save_offset_endstop"], 0, 0, 1, 1)
                else:
                    self.labels['button_grid'].attach(Gtk.Label(""), 0, 0, 1, 1)
                if (self._printer.config_section_exists("probe") or self._printer.config_section_exists("bltouch")):
                    self.labels['button_grid'].attach(self.labels["save_offset_probe"], 1, 0, 1, 1)
                else:
                    self.labels['button_grid'].attach(Gtk.Label(""), 1, 0, 1, 1)
            else:
                self.labels['button_grid'].attach(Gtk.Label(""), 0, 0, 1, 1)
                self.labels['button_grid'].attach(Gtk.Label(""), 1, 0, 1, 1)

            self.labels['button_grid'].attach(self.labels['restart'], 2, 0, 1, 1)
            self.labels['button_grid'].attach(self.labels['menu'], 3, 0, 1, 1)
        self.show_all()

    def show_file_thumbnail(self):
        if self._files.has_thumbnail(self.filename):
            pixbuf = self.get_file_image(self.filename, 7, 3.25)
            if pixbuf is not None:
                self.labels['thumbnail'].set_from_pixbuf(pixbuf)

    def update_filename(self):
        self.filename = self._printer.get_stat('print_stats', 'filename')
        self.update_text("file", os.path.splitext(self._printer.get_stat('print_stats', 'filename'))[0])
        self.update_percent_complete()
        self.update_file_metadata()

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
        self.labels['progress_text'].set_text("%s%%" % (str(min(int(self.progress*100), 100))))

    def update_message(self):
        msg = self._printer.get_stat("display_status", "message")
        if type(msg) == str:
            self.labels['lcdmessage'].set_text(msg)

    def update_temp(self, x, temp, target):
        self.labels[x].set_markup(
            "%.1f<big>/</big>%.0f °C" % (temp, target)
        )
