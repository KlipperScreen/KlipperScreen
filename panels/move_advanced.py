import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.keypad import Keypad


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Advanced Move")
        super().__init__(screen, title)
        self.axes = ["X", "Y", "Z"]
        self.endstop_status = {}
        self.buttons = {}
        self.numpad_visible = False
        self.numpad_target = None
        self.build_grid()
        self.query_endstops(None)
        self.content.add(self.grid)
        self.content.show_all()

    def build_grid(self):
        self.grid = Gtk.Grid(
            row_homogeneous=True, column_homogeneous=True, hexpand=True, vexpand=True
        )

        if self._screen.vertical_mode:
            self.grid.attach(self.build_axis_buttons(), 0, 0, 1, 2)
            self.grid.attach(self.build_second_panel(), 0, 2, 1, 2)
        else:
            self.grid.attach(self.build_axis_buttons(), 0, 0, 1, 1)
            self.grid.attach(self.build_second_panel(), 1, 0, 1, 1)

    def build_axis_buttons(self):
        axis_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            vexpand=True,
        )

        for i, axis in enumerate(self.axes):
            btn = self._gtk.Button(
                label=axis,
                style=f"color{i % 3 + 1}",
            )
            btn.connect("clicked", self.show_numpad, axis)
            self.buttons[axis] = btn
            axis_box.pack_start(btn, True, True, 0)

        return axis_box

    def build_endstop_panel(self):
        if "endstop_box" not in self.labels:
            self.labels["endstop_box"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.labels["endstop_list"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            scroll = self._gtk.ScrolledWindow(steppers=False)
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.add(self.labels["endstop_list"])

            endstop_btn = self._gtk.Button("refresh", _("Query Endstops"), "color4")
            endstop_btn.set_vexpand(False)
            endstop_btn.connect("clicked", self.query_endstops)
            self.labels["endstop_box"].pack_start(endstop_btn, False, False, 0)
            self.labels["endstop_box"].pack_start(scroll, True, True, 0)
        return self.labels["endstop_box"]

    def build_second_panel(self):
        if self.numpad_visible:
            return self.build_keypad_panel()
        return self.build_endstop_panel()

    def build_keypad_panel(self):
        if "keypad" not in self.labels:
            self.labels["keypad"] = Keypad(
                self._screen,
                ok_cb=self.submit_position,
                cancel_cb=self.hide_numpad,
                entry_max=8,
                error_msg=_("Invalid position"),
            )
        return self.labels["keypad"]

    def show_numpad(self, widget, axis):
        self.numpad_visible = True
        self.numpad_target = axis
        if self._screen.vertical_mode:
            self.grid.remove(self.grid.get_child_at(0, 2))
            self.grid.attach(self.build_second_panel(), 0, 2, 1, 2)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self.build_second_panel(), 1, 0, 1, 1)
        self.grid.show_all()

    def hide_numpad(self, widget=None):
        self.numpad_visible = False
        if self._screen.vertical_mode:
            numpad = self.grid.get_child_at(0, 2)
            if numpad:
                self.grid.remove(numpad)
            self.grid.attach(self.build_second_panel(), 0, 2, 1, 2)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self.build_second_panel(), 1, 0, 1, 1)
        self.grid.show_all()

    def submit_position(self, value):
        axis = self.numpad_target
        if not axis:
            return
        homed_axes = self._printer.get_stat("toolhead", "homed_axes")
        if axis.lower() not in homed_axes:
            self._screen.show_popup_message(_(f"{axis} axis not homed"))
            return

        printer_cfg = self._printer.get_config_section("printer")
        max_velocity = max(int(float(printer_cfg["max_velocity"])), 2)
        config_key = "move_speed_z" if axis == "Z" else "move_speed_xy"
        if axis == "Z" and "max_z_velocity" in printer_cfg:
            max_velocity = max(int(float(printer_cfg["max_z_velocity"])), 2)
        speed = (
            None if self.ks_printer_cfg is None else self.ks_printer_cfg.getint(config_key, None)
        )
        if speed is None:
            speed = self._config.get_config()["main"].getint(config_key, max_velocity)
        speed = 60 * max(1, speed)

        script = f"{KlippyGcodes.MOVE_ABSOLUTE}\nG0 {axis}{value} F{speed}"
        self._screen._send_action(None, "printer.gcode.script", {"script": script})

        self.hide_numpad()

    def query_endstops(self, widget):
        self._screen._ws.send_method("printer.query_endstops.status", callback=self.cb_query)

    def cb_query(self, data, method, params):
        if "error" in data or "result" not in data or not data["result"]:
            logging.error(data)
            return
        endstops = data["result"]
        logging.debug(endstops)
        for endstop in endstops:
            if endstop not in self.endstop_status:
                self.endstop_status[endstop] = Gtk.Label()
                self.labels["endstop_list"].pack_start(
                    self.endstop_status[endstop], False, False, 0
                )
                self.endstop_status[endstop].get_style_context().add_class("endstop")
            label = f"{endstop.upper()}: {endstops[endstop].capitalize()}"
            self.endstop_status[endstop].set_label(label)
            self.endstop_status[endstop].show()
            ctx = self.endstop_status[endstop].get_style_context()
            ctx.add_class("endstop")
            if endstops[endstop].lower() == "triggered":
                ctx.add_class("endstop-triggered")
                ctx.remove_class("endstop-open")
            else:
                ctx.add_class("endstop-open")
                ctx.remove_class("endstop-triggered")
        if "QUERY_PROBE" in self._printer.available_commands:
            self._screen._ws.api.gcode_script("QUERY_PROBE")

    def process_update(self, action, data):
        if action == "notify_gcode_response" and "probe:" in data.lower():
            logging.info(data)
            open = "open" in data
            label = f"Probe: {'Open' if open else 'Triggered'}"
            logging.info(label)
            if "probe" not in self.endstop_status and "endstop_list" in self.labels:
                self.endstop_status["probe"] = Gtk.Label()
                self.labels["endstop_list"].pack_start(
                    self.endstop_status["probe"], False, False, 0
                )
                self.endstop_status["probe"].get_style_context().add_class("endstop")
            ctx = self.endstop_status["probe"].get_style_context()
            if open:
                ctx.add_class("endstop-open")
                ctx.remove_class("endstop-triggered")
            else:
                ctx.add_class("endstop-triggered")
                ctx.remove_class("endstop-open")

            self.endstop_status["probe"].set_label(label)
            self.endstop_status["probe"].show()
        if action != "notify_status_update":
            return
        if "gcode_move" in data or "toolhead" in data and "homed_axes" in data["toolhead"]:
            homed_axes = self._printer.get_stat("toolhead", "homed_axes")
            for i, axis in enumerate(self.axes):
                if axis.lower() not in homed_axes:
                    self.buttons[axis].set_label(f"{axis}: ?")
                elif "gcode_move" in data and "gcode_position" in data["gcode_move"]:
                    self.buttons[axis].set_label(
                        f"{axis}: {data['gcode_move']['gcode_position'][i]:.2f}"
                    )

    def back(self):
        return False

    def deactivate(self):
        self.hide_numpad()
