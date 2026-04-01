from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gtk, Pango

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title, extra=None):
        title = title or _("Spool")
        super().__init__(screen, title)
        self.spool = None
        self.selected_weight_mode = "filament"
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, hexpand=True, vexpand=True)
        self.set_extra(extra=extra)

    def set_extra(self, extra=None, **kwargs):
        self.spool = extra
        if self.selected_weight_mode not in {"measured", "filament"}:
            self.selected_weight_mode = "filament"
        if self.spool is not None:
            self.title = self._get_display_name()
        for child in self.content.get_children():
            self.content.remove(child)
        self._build_grid()
        self.content.add(self.grid)
        self.content.show_all()

    def _build_grid(self):
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, hexpand=True, vexpand=True)

        if self.spool is None:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
            label = Gtk.Label(label=_("No spool selected"), wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
            box.set_valign(Gtk.Align.CENTER)
            box.add(label)
            self.grid.attach(box, 0, 0, 1, 1)
            return

        if self._screen.vertical_mode:
            self.grid.attach(self._build_info_box(), 0, 0, 1, 2)
            self.grid.attach(self._build_right_panel(), 0, 2, 1, 2)
        else:
            self.grid.attach(self._build_info_box(), 0, 0, 1, 1)
            self.grid.attach(self._build_right_panel(), 1, 0, 1, 1)

    def _build_info_box(self):
        click_area = Gtk.EventBox()
        click_area.set_visible_window(False)
        click_area.connect("button-press-event", self._on_info_panel_clicked)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, vexpand=True)
        info.set_valign(Gtk.Align.CENTER)

        icon_box = Gtk.Box(hexpand=True)
        icon_box.set_halign(Gtk.Align.CENTER)
        icon_box.set_margin_bottom(round(self._gtk.font_size * 0.9))
        icon_pixbuf = self.spool.icon
        if icon_pixbuf is not None:
            icon_pixbuf = icon_pixbuf.scale_simple(
                int(round(icon_pixbuf.get_width() * 1.5)),
                int(round(icon_pixbuf.get_height() * 1.5)),
                GdkPixbuf.InterpType.BILINEAR,
            )
        icon = Gtk.Image.new_from_pixbuf(icon_pixbuf)
        icon.set_halign(Gtk.Align.CENTER)
        icon_box.pack_start(icon, False, False, 0)
        info.pack_start(icon_box, False, False, 0)

        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        details.set_halign(Gtk.Align.FILL)
        details.set_margin_start(24)
        details.set_margin_end(12)

        title = Gtk.Label(halign=Gtk.Align.START, xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        title.set_markup(f"<big><b>{self._get_display_name()}</b></big>")
        details.pack_start(title, False, False, 0)

        for line in self._get_spool_property_lines():
            label = Gtk.Label(halign=Gtk.Align.START, xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
            label.set_markup(line)
            details.pack_start(label, False, False, 0)

        info.pack_start(details, False, False, 0)
        info.pack_start(self._build_measurement_details_box(), False, False, 0)

        click_area.add(info)
        return click_area

    def _get_spool_property_lines(self):
        lines = [f'ID: <b>{self.spool.id}</b>']
        material = getattr(self.spool.filament, "material", None)
        if material:
            lines.append(f'{_("Material")}: <b>{material}</b>')
        if getattr(self.spool, "comment", None):
            lines.append(f'{_("Comment")}: <b>{self.spool.comment}</b>')
        last_used = getattr(self.spool, "last_used", None)
        lines.append(
            f'{_("Last used")}: <b>{self._format_last_used(last_used) if last_used else "-"}</b>'
        )
        return lines

    def _build_measurement_details_box(self):
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        details.set_halign(Gtk.Align.FILL)
        details.set_margin_start(24)
        details.set_margin_end(12)

        for row in self._get_measurement_rows():
            label = Gtk.Label(halign=Gtk.Align.START, xalign=0, hexpand=True)
            label.set_line_wrap(False)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_markup(self._format_measurement_row_markup(row))
            details.pack_start(label, False, False, 0)

        return details

    def _get_measurement_rows(self):
        rows = []
        remaining_weight = getattr(self.spool, "remaining_weight", None)
        empty_spool_weight = self._get_empty_spool_weight()
        if remaining_weight is not None:
            measured_weight = (
                remaining_weight + empty_spool_weight
                if empty_spool_weight is not None
                else remaining_weight
            )
            rows.append({
                "mode": "measured",
                "label": _("Measured weight"),
                "value": measured_weight,
                "selectable": True,
            })
            rows.append({
                "mode": "filament",
                "label": _("Filament weight"),
                "value": remaining_weight,
                "selectable": True,
            })
        if empty_spool_weight is not None:
            rows.append({
                "mode": "empty",
                "label": _("Empty spool weight"),
                "value": empty_spool_weight,
                "selectable": False,
            })
        return rows

    def _format_measurement_row_markup(self, row):
        formatted_value = f'{round(row["value"], 2)} g'
        if row["selectable"] and row["mode"] == self.selected_weight_mode:
            return f'<b>{row["label"]}: {formatted_value}</b>'
        return f'{row["label"]}: <b>{formatted_value}</b>'

    def _on_info_panel_clicked(self, widget, event):
        self.selected_weight_mode = "measured" if self.selected_weight_mode == "filament" else "filament"
        self.labels['entry'].set_text("")
        self.set_extra(extra=self.spool)
        return True

    def _get_empty_spool_weight(self):
        spool_weight = getattr(self.spool, "spool_weight", None)
        vendor_spool_weight = getattr(getattr(self.spool.filament, "vendor", None), "empty_spool_weight", None)
        return vendor_spool_weight if vendor_spool_weight is not None else spool_weight

    def _get_full_filament_weight(self):
        initial_weight = getattr(self.spool, "initial_weight", None)
        filament_weight = getattr(self.spool.filament, "weight", None)
        if initial_weight is not None:
            return initial_weight
        return filament_weight

    def _get_display_name(self):
        parts = []
        vendor_name = getattr(getattr(self.spool.filament, "vendor", None), "name", None)
        filament_name = getattr(self.spool.filament, "name", None) or getattr(self.spool, "name", None)
        if vendor_name:
            parts.append(vendor_name)
        if filament_name:
            parts.append(filament_name)
        return " - ".join(parts) if parts else self.spool.name

    def _format_last_used(self, value):
        if isinstance(value, datetime):
            if self._config.get_main_config().getboolean("24htime", True):
                return value.astimezone().strftime("%Y-%m-%d %H:%M")
            return value.astimezone().strftime("%Y-%m-%d %I:%M %p")
        return str(value)

    def _build_right_panel(self):
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, vexpand=True)
        right.add(self._build_spool_keypad())
        return right

    def _set_weight_placeholder(self, value):
        self._screen.show_popup_message(
            _("Placeholder: set spool #{spool_id} to {value} g").format(
                spool_id=self.spool.id if self.spool is not None else "-",
                value=value
            )
        )

    def _show_placeholder(self, widget, action):
        self._screen.show_popup_message(
            _("Placeholder: {action} for spool #{spool_id}").format(
                action=action,
                spool_id=self.spool.id if self.spool is not None else "-"
            )
        )

    def _build_spool_keypad(self):
        keypad = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.labels["entry"] = Gtk.Entry(hexpand=True, xalign=0.5, max_length=8)
        self.labels['entry'].connect("activate", self._submit_entry)
        entry_side_margin = round(self._gtk.font_size * 0.15)
        self.labels["entry"].set_margin_start(entry_side_margin)
        self.labels["entry"].set_margin_end(entry_side_margin)

        numpad = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        numpad.set_direction(Gtk.TextDirection.LTR)
        numpad.get_style_context().add_class('numpad')
        numpad.set_hexpand(True)

        keys = [
            ['1', 'numpad_tleft'],
            ['2', 'numpad_top'],
            ['3', 'numpad_tright'],
            ['4', 'numpad_left'],
            ['5', 'numpad_button'],
            ['6', 'numpad_right'],
            ['7', 'numpad_left'],
            ['8', 'numpad_button'],
            ['9', 'numpad_right'],
            ['B', 'numpad_bleft'],
            ['0', 'numpad_bottom'],
            ['.', 'numpad_bright']
        ]
        for i, key in enumerate(keys):
            label, style_class = key
            if label == "B":
                button = self._gtk.Button("backspace", scale=.66, style="numpad_key")
            else:
                button = self._gtk.Button(label=label, style="numpad_key")
            button.connect('clicked', self._on_spool_keypad_button, label)
            button.get_style_context().add_class(style_class)
            numpad.attach(button, i % 3, i // 3, 1, 1)

        ok = self._gtk.Button('complete', style="color1", scale=1.1)
        if self._screen.vertical_mode:
            ok.set_size_request(-1, self._gtk.font_size * 4)
        else:
            ok.set_size_request(-1, self._gtk.font_size * 5)
        ok.connect('clicked', self._submit_entry)
        ok.set_vexpand(False)

        reset = self._gtk.Button(
            'refresh', _("Reset"), "color2", self._gtk.bsidescale, Gtk.PositionType.LEFT, 1
        )
        reset.set_vexpand(False)
        reset.connect("clicked", self._reset_placeholder)

        bottom = Gtk.Box()
        bottom.add(reset)
        bottom.add(ok)

        keypad.add(self.labels["entry"])
        keypad.add(numpad)
        keypad.add(bottom)
        return keypad

    def _on_spool_keypad_button(self, widget, digit):
        if digit == 'B':
            self.labels['entry'].set_text(self.labels['entry'].get_text()[:-1])
        else:
            self.labels['entry'].set_text(f"{self.labels['entry'].get_text()}{digit}")

    @staticmethod
    def _format_entry_weight(value):
        if value is None:
            return ""
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _submit_entry(self, widget=None):
        try:
            value = float(self.labels['entry'].get_text())
        except ValueError:
            self._screen.show_popup_message(_("Invalid weight"))
            return
        if self.selected_weight_mode == "measured":
            empty_spool_weight = self._get_empty_spool_weight()
            if empty_spool_weight is not None:
                value -= empty_spool_weight
            if value < 0:
                self._screen.show_popup_message(_("Measured weight is below empty spool weight"))
                return
        result = self._screen.apiclient.post_request("server/spoolman/proxy", json={
            "use_v2_response": True,
            "request_method": "PATCH",
            "path": f"/v1/spool/{self.spool.id}",
            "body": {
                "remaining_weight": value
            }
        })
        if not result:
            self._screen.show_popup_message(_("Error updating filament weight"))
            return
        if result.get("error"):
            self._screen.show_popup_message(
                _("Error updating filament weight") + f"\n{result['error'].get('message', '')}"
            )
            return
        response = result.get("response") or {}
        self.spool.remaining_weight = response.get("remaining_weight", value)
        if "used_weight" in response:
            self.spool.used_weight = response["used_weight"]
        if "remaining_length" in response:
            self.spool.remaining_length = response["remaining_length"]
        if self._screen.printer is not None and self._screen.printer.active_spool_id == self.spool.id:
            self._screen.base_panel.refresh_spoolman_weight(
                self._screen.printer.state not in {'disconnected', 'startup', 'shutdown', 'error'},
                spool_id=self.spool.id
            )
        self.set_extra(extra=self.spool)
        self._screen.show_popup_message(_("Filament weight updated"), 1)

    def _reset_placeholder(self, widget=None):
        full_filament_weight = self._get_full_filament_weight()
        if full_filament_weight is None:
            self._screen.show_popup_message(_("Unable to determine full filament weight"))
            return
        if self.selected_weight_mode == "measured":
            empty_spool_weight = self._get_empty_spool_weight()
            value = (
                full_filament_weight + empty_spool_weight
                if empty_spool_weight is not None
                else full_filament_weight
            )
        else:
            value = full_filament_weight
        self.labels['entry'].set_text(self._format_entry_weight(value))

    def back(self):
        return False
