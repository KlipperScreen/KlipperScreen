import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Set printer model")
        super().__init__(screen, title)

        text = Gtk.Label()
        text.set_line_wrap(True)
        text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        text.set_halign(Gtk.Align.CENTER)
        text.set_valign(Gtk.Align.CENTER)
        markup = '<span size="xx-large">{}</span>'.format(_("Choose the Syncraft 3D printer model"))
        text.set_markup(markup)
        self.content.pack_start(text, expand=True, fill=True, padding=3)
        self.content.add(text)

        dropdown = Gtk.ComboBoxText()
        options = [
            ("syncraft_x1", "Syncraft X1"),
            ("syncraft_idex", "Syncraft IDEX")
        ]

        for i, (value, name) in enumerate(options):
            dropdown.append(value, name)

        dropdown.connect("changed", self.on_dropdown_change)
        dropdown.set_entry_text_column(0)

        finish_button = self._gtk.Button("complete", _("Finish"), None)
        finish_button.connect("clicked", self.finish)

        form_content = Gtk.Grid(column_homogeneous=True)
        form_content.set_valign(Gtk.Align.CENTER)
        form_content.set_halign(Gtk.Align.CENTER)
        form_content.add(dropdown)
        form_content.add(finish_button)

        self.content.add(form_content)

    def on_dropdown_change(self, combo):
        selected_model = combo.get_active_text()
        self._config.set("syncraft", "model", selected_model)
        logging.info(f"Selected: {selected_model}")

    def finish(self, button):
        self._config.save_user_config_options()
        self._screen.restart_ks()