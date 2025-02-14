import gi
import logging
from datetime import datetime

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GLib
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

        commands = Gtk.ListStore(str)
        commands.append({"Syncraft X1"})
        commands.append({"Syncraft IDEX"})

        self.dropdown = Gtk.ComboBox.new_with_model(commands)
        self.dropdown.connect("changed", self.on_dropdown_change)
        self.dropdown.connect("notify::popup-shown", self.on_popup_shown)
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_property("ellipsize", Pango.EllipsizeMode.END)
        self.dropdown.pack_start(renderer_text, True)
        self.dropdown.add_attribute(renderer_text, "text", 0)
        self.dropdown.set_active(0)

        finish_button = self._gtk.Button("complete", _("Finish"), None)
        finish_button.connect("clicked", self.finish)

        form_content = Gtk.Grid(column_homogeneous=True)
        form_content.set_valign(Gtk.Align.CENTER)
        form_content.set_halign(Gtk.Align.CENTER)
        form_content.add(self.dropdown)
        form_content.add(finish_button)

        self.content.add(form_content)


    def on_dropdown_change(self, dropdown):
        iterable = dropdown.get_active_iter()
        if iterable is None:
            self._screen.show_popup_message("Unknown error with dropdown")
            return
        model = dropdown.get_model()
        printer_model = model[iterable][0]
        self._config.set("syncraft", "model", printer_model)
        logging.debug(f"Selected {printer_model}")


    def on_popup_shown(self, combo_box, param):
        if combo_box.get_property("popup-shown"):
            logging.debug("Dropdown popup show")
            self.last_drop_time = datetime.now()
        else:
            elapsed = (datetime.now() - self.last_drop_time).total_seconds()
            if elapsed < 0.2:
                logging.debug(f"Dropdown closed too fast ({elapsed}s)")
                GLib.timeout_add(50, self.dropdown_keep_open)
                return
            logging.debug("Dropdown popup close")


    def finish(self, button):
        self._config.save_user_config_options()
        self._screen.restart_ks()

        
    def dropdown_keep_open(self):
        self.dropdown.popup()
        return False