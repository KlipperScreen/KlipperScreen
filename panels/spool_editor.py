import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from datetime import datetime
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.keypad import Keypad


class Panel(ScreenPanel):
    def __init__(self, screen, title, extra=None):
        title = _("Spool editor")
        super().__init__(screen, title)
        self.selected_weight_mode = "filament"
        self.saved_weight = 0
        self.numpad_visible = False
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, hexpand=True, vexpand=True)
        self.set_extra(extra)

    def set_extra(self, extra):
        self.spool = extra
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
            self.grid.attach(self._build_first_panel(), 0, 0, 1, 2)
            self.grid.attach(self._build_second_panel(), 0, 2, 1, 2)
        else:
            self.grid.attach(self._build_first_panel(), 0, 0, 1, 1)
            self.grid.attach(self._build_second_panel(), 1, 0, 1, 1)

    def _build_first_panel(self):
        title_box = Gtk.Box(hexpand=True)
        title_box.get_style_context().add_class("spool_title")

        icon_pixbuf = self.spool.icon
        icon = Gtk.Image.new_from_pixbuf(icon_pixbuf)
        icon.set_halign(Gtk.Align.CENTER)
        icon.get_style_context().add_class("spool_icon")

        title_box.pack_start(icon, False, False, 0)
        title = Gtk.Label(halign=Gtk.Align.START, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        title.set_markup(f"<big><b>{self._get_display_name()}</b></big>")
        title_box.pack_start(title, False, False, 0)

        buttons = self._build_measurement_details_box()

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, vexpand=True)
        info.set_valign(Gtk.Align.FILL)
        info.pack_start(title_box, False, False, 0)
        info.pack_start(buttons, True, True, 0)

        return info

    def _build_measurement_details_box(self):
        buttons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, vexpand=True)
        buttons.set_margin_start(24)
        buttons.set_margin_end(12)

        for i, row in enumerate(self._get_measurement_rows()):
            btn = self._gtk.Button(
                label=self._format_measurement_row_markup(row),
                style=f"color{i % 4 + 1}",
            )
            btn.connect("clicked", self._show_numpad, row["mode"])
            buttons.pack_start(btn, True, True, 0)

        return buttons

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
            })
            rows.append({
                "mode": "remaining",
                "label": _("Remaining weight"),
                "value": remaining_weight,
            })
        remaining_weight = getattr(self.spool, "remaining_weight", None)

        initial_weight = self._get_initial_weight()
        if initial_weight is not None:
            rows.append({
                "mode": "initial",
                "label": _("Initial weight"),
                "value": initial_weight,
            })
        if empty_spool_weight is not None:
            rows.append({
                "mode": "empty",
                "label": _("Empty weight"),
                "value": empty_spool_weight,
            })
        return rows

    def _format_measurement_row_markup(self, row):
        formatted_value = f'{round(row["value"], 2)} g'
        return f'{row["label"]}: {formatted_value}'


    def _get_initial_weight(self):
        return getattr(self.spool, "initial_weight", None)

    def _get_empty_spool_weight(self):
        spool_weight = getattr(self.spool, "spool_weight", None)
        vendor_spool_weight = getattr(getattr(self.spool.filament, "vendor", None), "empty_spool_weight", None)
        return spool_weight if spool_weight is not None else vendor_spool_weight

    def _get_full_filament_weight(self):
        # initial_weight should be net weight
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

    def _build_keypad_panel(self):
        if "keypad" not in self.labels:
            self.labels["keypad"] = Keypad(
                self._screen,
                ok_cb=self._submit_entry,
                cancel_cb=self._hide_numpad,
                entry_max=8,
                error_msg=_("Invalid weight")
            )
            self.labels["keypad"].add_extra_button(
                self._restore_value,
                icon="refresh",
                label=_("Restore")
            )
        return self.labels["keypad"]

    def _build_progress_bar(self):
        used = getattr(self.spool, "used_weight", 0) or 0
        initial = self._get_full_filament_weight() or 1000
        fraction = min(max(used / initial, 0.0), 1.0)
        progress = Gtk.ProgressBar()
        progress.set_fraction(fraction)
        progress.set_text(f"{round(used, 1)} / {round(initial, 1)} g")
        progress.set_show_text(True)
        progress.set_margin_start(10)
        progress.set_margin_end(10)
        progress.set_margin_top(5)
        progress.set_margin_bottom(5)
        progress.set_halign(Gtk.Align.FILL)
        return progress

    def _build_second_panel(self):
        if self.numpad_visible:
            return self._build_keypad_panel()
        return self._build_info_panel()


    def _build_info_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, hexpand=True, vexpand=True)
        box.set_halign(Gtk.Align.FILL)
        box.set_valign(Gtk.Align.FILL)

        # Progress Bar
        progress = self._build_progress_bar()
        box.pack_start(progress, False, False, 0)

        # Info Labels
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, hexpand=True)

        vendor = getattr(getattr(getattr(self.spool, "filament", None), "vendor", None), "name", None) or "-"
        material = getattr(getattr(self.spool, "filament", None), "material", None) or "-"
        location = getattr(self.spool, "location", None) or "-"
        last_used = self._format_last_used(getattr(self.spool, "last_used", None))
        archived = _("Yes") if getattr(self.spool, "archived", None) else _("No")
        price = getattr(self.spool, "price", None) or "-"
        info_items = [
            (_("Vendor"), vendor),
            (_("Material"), material),
            (_("Used"), last_used),
            (_("Location"), location),
            (_("Archived"), archived),
            (_("Price"), price),
        ]
        for label_text, value in info_items:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True)
            lbl = Gtk.Label(label=f"{label_text}: ", halign=Gtk.Align.START)
            val = Gtk.Label(label=str(value), halign=Gtk.Align.START)
            row.pack_start(lbl, False, False, 0)
            row.pack_start(val, True, True, 0)
            info_box.pack_start(row, False, False, 0)

        comment = _("Comment") + ": " + (getattr(self.spool, "comment", None) or "-")
        comment_lbl = Gtk.Label(label=comment, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        comment_lbl.set_alignment(0.0, 0.0)
        comment_area = self._gtk.ScrolledWindow()
        comment_area.add(comment_lbl)
        info_box.pack_start(comment_area, True, True, 0)

        box.pack_start(info_box, True, True, 0)
        return box

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
        result = {}
        if self.selected_weight_mode == "measured":
            empty_spool_weight = self._get_empty_spool_weight() or 0
            if empty_spool_weight:
                value -= empty_spool_weight
            if value < 0:
                self._screen.show_popup_message(_("Measured weight is below empty spool weight"))
                return
            result = self._screen.spoolman_api.update_spool(
                spool_id=self.spool.id,
                payload={"remaining_weight": value}

            )
        if self.selected_weight_mode == "remaining":
            if value < 0:
                self._screen.show_popup_message(_("Value must be positive"))
                return
            result = self._screen.spoolman_api.update_spool(
                spool_id=self.spool.id,
                payload={"remaining_weight": value}
            )
        if self.selected_weight_mode == "empty":
            if value < 0:
                self._screen.show_popup_message(_("Value must be positive"))
                return
            result = self._screen.spoolman_api.update_spool(
                spool_id=self.spool.id,
                payload={"spool_weight": value}
            )
        if self.selected_weight_mode == "initial":
            if value < 0:
                self._screen.show_popup_message(_("Value must be positive"))
                return
            result = self._screen.spoolman_api.update_spool(
                spool_id=self.spool.id,
                payload={"Initial_weight": value}
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

        self._screen.show_popup_message(_("Filament weight updated"), 1)
        self._hide_numpad(None)

    def _restore_value(self, entry_val):
        if "keypad" in self.labels:
            self.labels['keypad'].entry.set_text(f"{self.saved_weight:.1f}")

    def back(self):
        return False

    def _show_numpad(self, widget, mode):
        self.selected_weight_mode = mode
        if mode == "measured":
            self.saved_weight = self.spool.remaining_weight + self.spool.spool_weight
        if mode == "remaining":
            self.saved_weight = self.spool.remaining_weight
        if mode == "empty":
            self.saved_weight = self.spool.spool_weight
        if mode == "initial":
            self.saved_weight = self.spool.initial_weight
        self.numpad_visible = True
        if self._screen.vertical_mode:
            self.grid.remove(self.grid.get_child_at(0, 2))
            self.grid.attach(self._build_second_panel(), 0, 2, 1, 2)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self._build_second_panel(), 1, 0, 1, 1)
        self.grid.show_all()


    def _hide_numpad(self, widget=None):
        self.numpad_visible = False
        if self._screen.vertical_mode:
            numpad = self.grid.get_child_at(0, 2)
            if numpad:
                self.grid.remove(numpad)
            self.grid.attach(self._build_second_panel(), 0, 2, 1, 2)
        else:
            self.grid.remove_column(1)
            self.grid.attach(self._build_second_panel(), 1, 0, 1, 1)
        self.grid.show_all()  # needed?
