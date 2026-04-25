import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gtk, Pango

from datetime import datetime
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.keypad import Keypad


class Panel(ScreenPanel):
    def __init__(self, screen, title, extra=None):
        title = title or _("Spool")
        super().__init__(screen, title)
        self.spool = None
        self.selected_weight_mode = "filament"
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, hexpand=True, vexpand=True)
        self.set_extra(extra=extra)
        self.saved_weight = 0

    def set_extra(self, extra=None, **kwargs):
        self.spool = extra
        self.saved_weight = getattr(self.spool, "remaining_weight", 0)
        if self.selected_weight_mode not in {"measured", "filament"}:
            self.selected_weight_mode = "filament"
        self.title = _("Spool")
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
                "label": _("Remaining weight"),
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
        self.set_extra(extra=self.spool)
        return True

    def _get_empty_spool_weight(self):
        spool_weight = getattr(self.spool, "spool_weight", None)
        vendor_spool_weight = getattr(getattr(self.spool.filament, "vendor", None), "empty_spool_weight", None)
        return spool_weight if spool_weight is not None else vendor_spool_weight

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
        self.labels["keypad"] = Keypad(
            self._screen,
            ok_cb=self._submit_entry,
            cancel_cb=self._clear_entry,
            entry_max=8,
            error_msg=_("Invalid weight")
        )

        self.labels["keypad"].add_extra_button(
            self._restore_value,
            icon="refresh",
            label=_("Restore"),
        )

        right.pack_start(self.labels["keypad"], True, True, 0)
        return right

    def _clear_entry(self, widget=None):
        self.labels["keypad"].clear()

    @staticmethod
    def _format_entry_weight(value):
        if value is None:
            return ""
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _submit_entry(self, value):
        if self.spool is None:
            return

        if self.selected_weight_mode == "measured":
            empty_spool_weight = self._get_empty_spool_weight() or 0
            if empty_spool_weight:
                value -= empty_spool_weight
            if value < 0:
                self._screen.show_popup_message(_("Measured weight is below empty spool weight"))
                return
        result = self._screen.spoolman_api.update_spool_weight(
            spool_id=self.spool.id,
            remaining_weight=value
        )
        if not result:
            self._screen.show_popup_message(_("Error updating filament weight"))
            return

        if result.get("error"):
            self._screen.show_popup_message(
                _("Error updating filament weight") + f"\n{result['error'].get('message', '')}"
            )
            return

        self.spool.remaining_weight = result.get("remaining_weight", value)

        if "used_weight" in result:
            self.spool.used_weight = result["used_weight"]

        if self._screen.printer is not None and getattr(self._screen.printer, 'active_spool_id', None) == self.spool.id:
            self._screen.printer.active_spool['remaining_weight'] = result.get("remaining_weight")

        self.set_extra(extra=self.spool)
        self._screen.show_popup_message(_("Filament weight updated"), 1)

    def _restore_value(self, entry_val):
        self.labels['keypad'].entry.set_text(f"{self.saved_weight:.1f}")

    def back(self):
        return False
