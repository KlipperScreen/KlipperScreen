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

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)

        self.labels['button_grid'] = self._gtk.HomogeneousGrid()
        self.labels['button_grid'].set_vexpand(False)

        fi_box = Gtk.VBox(spacing=0)
        fi_box.set_hexpand(True)
        fi_box.set_vexpand(False)
        fi_box.set_halign(Gtk.Align.START)

        self.labels['file'] = Gtk.Label(label="file")
        self.labels['file'].set_halign(Gtk.Align.START)
        self.labels['file'].set_vexpand(False)
        self.labels['file'].get_style_context().add_class("printing-filename")
        self.labels['file'].set_ellipsize(True)
        self.labels['file'].set_ellipsize(Pango.EllipsizeMode.END)
        self.labels['status'] = Gtk.Label()
        self.labels['status'].set_halign(Gtk.Align.START)
        self.labels['status'].set_vexpand(False)
        self.labels['status'].get_style_context().add_class("printing-status")
        self.labels['status'].set_line_wrap(True)
        self.labels['lcdmessage'] = Gtk.Label("")
        self.labels['lcdmessage'].set_halign(Gtk.Align.START)
        self.labels['lcdmessage'].set_vexpand(False)
        self.labels['lcdmessage'].get_style_context().add_class("printing-status")
        self.labels['lcdmessage'].set_ellipsize(True)
        self.labels['lcdmessage'].set_ellipsize(Pango.EllipsizeMode.END)

        fi_box.add(self.labels['file'])
        fi_box.add(self.labels['status'])
        fi_box.add(self.labels['lcdmessage'])
        fi_box.set_valign(Gtk.Align.CENTER)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info.props.valign = Gtk.Align.CENTER
        info.set_hexpand(True)
        info.set_vexpand(True)

        self.labels['darea'] = Gtk.DrawingArea()
        self.labels['darea'].connect("draw", self.on_draw)

        box = Gtk.Box()
        box.set_hexpand(True)
        box.set_vexpand(True)
        box.set_halign(Gtk.Align.CENTER)
        self.labels['progress_text'] = Gtk.Label()
        self.labels['progress_text'].get_style_context().add_class("printing-progress-text")
        box.add(self.labels['progress_text'])

        overlay = Gtk.Overlay()
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        overlay.add(self.labels['darea'])
        overlay.add_overlay(box)

        self.labels['thumbnail'] = self._gtk.Image("file", 2)

        i = 0
        for extruder in self._printer.get_tools():
            self.labels[extruder + '_box'] = Gtk.Box(spacing=0)
            self.labels[extruder] = Gtk.Label(label="")
            self.labels[extruder].get_style_context().add_class("printing-info")
            if i <= 4:
                ext_img = self._gtk.Image("extruder-%s" % i, .6)
                self.labels[extruder + '_box'].add(ext_img)
            self.labels[extruder + '_box'].add(self.labels[extruder])
            i += 1

        temp_grid = self._gtk.HomogeneousGrid()
        self.current_extruder = self._printer.get_stat("toolhead", "extruder")
        temp_grid.attach(self.labels[self.current_extruder + '_box'], 0, 0, 1, 1)
        if self._printer.has_heated_bed():
            heater_bed = self._gtk.Image("bed", .6)
            self.labels['heater_bed'] = Gtk.Label(label="")
            self.labels['heater_bed'].get_style_context().add_class("printing-info")
            heater_bed_box = Gtk.Box(spacing=0)
            heater_bed_box.add(heater_bed)
            heater_bed_box.add(self.labels['heater_bed'])
            temp_grid.attach(heater_bed_box, 1, 0, 1, 1)
        self.labels['temp_grid'] = temp_grid

        # Create time remaining items
        hourglass = self._gtk.Image("hourglass", .6)
        self.labels['left'] = Gtk.Label(label=_("Left:"))
        self.labels['left'].get_style_context().add_class("printing-info")
        self.labels['time_left'] = Gtk.Label(label="0s")
        self.labels['time_left'].get_style_context().add_class("printing-info")
        itl_box = Gtk.Box(spacing=0)
        itl_box.add(hourglass)
        itl_box.add(self.labels['left'])
        itl_box.add(self.labels['time_left'])
        self.labels['itl_box'] = itl_box

        # Create overall items
        clock = self._gtk.Image("clock", .6)
        self.labels['elapsed'] = Gtk.Label(label=_("Elapsed:"))
        self.labels['elapsed'].get_style_context().add_class("printing-info")
        self.labels['duration'] = Gtk.Label(label="0s")
        self.labels['duration'].get_style_context().add_class("printing-info")
        self.labels['total'] = Gtk.Label(label=_("Total:"))
        self.labels['total'].get_style_context().add_class("printing-info")
        self.labels['est_time'] = Gtk.Label(label="0s")
        self.labels['est_time'].get_style_context().add_class("printing-info")
        timegrid = Gtk.Grid()
        it1_box = Gtk.Box(spacing=0)
        it1_box.add(self.labels['elapsed'])
        it1_box.add(self.labels['duration'])
        it2_box = Gtk.Box(spacing=0)
        it2_box.add(self.labels['total'])
        it2_box.add(self.labels['est_time'])
        timegrid.attach(clock, 0, 0, 1, 2)
        timegrid.attach(it1_box, 1, 0, 1, 1)
        timegrid.attach(it2_box, 1, 1, 1, 1)
        self.labels['timegrid'] = timegrid

        position = self._gtk.Image("move", .6)
        self.labels['pos_x'] = Gtk.Label(label="X: 0")
        self.labels['pos_x'].get_style_context().add_class("printing-info")
        self.labels['pos_y'] = Gtk.Label(label="Y: 0")
        self.labels['pos_y'].get_style_context().add_class("printing-info")
        self.labels['pos_z'] = Gtk.Label(label="Z: 0")
        self.labels['pos_z'].get_style_context().add_class("printing-info")
        pos_box = Gtk.Box(spacing=0)
        posgrid = self._gtk.HomogeneousGrid()
        posgrid.set_hexpand(True)
        posgrid.attach(self.labels['pos_x'], 0, 0, 1, 1)
        posgrid.attach(self.labels['pos_y'], 1, 0, 1, 1)
        posgrid.attach(self.labels['pos_z'], 2, 0, 1, 1)
        pos_box.add(position)
        pos_box.add(posgrid)
        self.labels['pos_box'] = pos_box

        speed = self._gtk.Image("speed+", .6)
        self.labels['speed'] = Gtk.Label(label="")
        self.labels['speed'].get_style_context().add_class("printing-info")
        speed_box = Gtk.Box(spacing=0)
        speed_box.add(speed)
        speed_box.add(self.labels['speed'])
        extrusion = self._gtk.Image("extrude", .6)
        self.labels['extrusion'] = Gtk.Label(label="")
        self.labels['extrusion'].get_style_context().add_class("printing-info")
        extrusion_box = Gtk.Box(spacing=0)
        extrusion_box.add(extrusion)
        extrusion_box.add(self.labels['extrusion'])
        fan = self._gtk.Image("fan", .6)
        self.labels['fan'] = Gtk.Label(label="")
        self.labels['fan'].get_style_context().add_class("printing-info")
        fan_box = Gtk.Box(spacing=0)
        fan_box.add(fan)
        fan_box.add(self.labels['fan'])
        sfe_grid = self._gtk.HomogeneousGrid()
        sfe_grid.set_hexpand(True)
        sfe_grid.attach(speed_box, 0, 0, 1, 1)
        sfe_grid.attach(extrusion_box, 1, 0, 1, 1)
        sfe_grid.attach(fan_box, 2, 0, 1, 1)
        self.labels['sfe_grid'] = sfe_grid

        self.labels['i1_box'] = Gtk.HBox(spacing=0)
        self.labels['i1_box'].set_vexpand(True)
        self.labels['i1_box'].get_style_context().add_class("printing-info-box")
        self.labels['i1_box'].set_valign(Gtk.Align.CENTER)
        self.labels['i2_box'] = Gtk.VBox(spacing=0)
        self.labels['i2_box'].set_vexpand(True)
        self.labels['i2_box'].get_style_context().add_class("printing-info-box")
        self.labels['i2_box'].set_valign(Gtk.Align.CENTER)
        self.labels['info_grid'] = self._gtk.HomogeneousGrid()
        if self._screen.vertical_mode:
            self.labels['info_grid'].attach(self.labels['i1_box'], 0, 0, 1, 1)
            self.labels['info_grid'].attach(self.labels['i2_box'], 0, 1, 1, 1)
        else:
            self.labels['info_grid'].attach(self.labels['i1_box'], 0, 0, 2, 1)
            self.labels['info_grid'].attach(self.labels['i2_box'], 2, 0, 3, 1)

        grid.attach(overlay, 0, 0, 1, 1)
        grid.attach(fi_box, 1, 0, 3, 1)
        grid.attach(self.labels['info_grid'], 0, 1, 4, 2)
        grid.attach(self.labels['button_grid'], 0, 3, 4, 1)

        self.add_labels()

        self.grid = grid
        self.content.add(grid)
        self._screen.wake_screen()

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

    def add_labels(self):
        for child in self.labels['i1_box'].get_children():
            self.labels['i1_box'].remove(child)
        for child in self.labels['i2_box'].get_children():
            self.labels['i2_box'].remove(child)

        self.labels['i1_box'].add(self.labels['thumbnail'])
        self.labels['i2_box'].add(self.labels['temp_grid'])
        self.labels['i2_box'].add(self.labels['pos_box'])
        self.labels['i2_box'].add(self.labels['sfe_grid'])
        self.labels['i2_box'].add(self.labels['timegrid'])
        self.labels['i2_box'].add(self.labels['itl_box'])


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

        if "toolhead" in data:
            if "extruder" in data["toolhead"]:
                if data["toolhead"]["extruder"] != self.current_extruder:
                    self.labels['temp_grid'].remove_column(0)
                    self.labels['temp_grid'].insert_column(0)
                    self.current_extruder = data["toolhead"]["extruder"]
                    self.labels['temp_grid'].attach(self.labels[self.current_extruder + '_box'], 0, 0, 1, 1)
                    self._screen.show_all()

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
                if not self._screen.printer.get_config_section("stepper_z")['endstop_pin'].startswith("probe"):
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
