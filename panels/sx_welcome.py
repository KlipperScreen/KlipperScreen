import gi
import os
import pathlib

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.screen_panel import ScreenPanel

syncraft_path = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "syncraft")
syncraft_images_path = os.path.join(syncraft_path, "images")

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Welcome")
        super().__init__(screen, title)
        
        self.texts = [
            f'{_("Welcome to Syncraft")}',
            f'{_("Here are some recommended steps to get started")}',
            f'{_("If you want, you can adjust all of this later")}',
        ]

        for i, content in enumerate(self.texts):
            text = Gtk.Label(content)
            text.set_line_wrap(True)
            text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            text.set_halign(Gtk.Align.CENTER)
            text.set_valign(Gtk.Align.CENTER)
            if i == 0:
                markup = '<span size="xx-large">{}</span>'.format(content)
            else:
                markup = '<span size="large">{}</span>'.format(content)
            text.set_markup(markup)
            self.content.pack_start(text, expand=True, fill=True, padding=3)
            self.content.add(text)

        self.buttons = {
            'STEP_01': self._gtk.Button("network", _("Connect"), "color3"),
            'STEP_02': self._gtk.Button ("settings", _("Settings"), "color1"),
            'STEP_03': self._gtk.Button("bed-level", _("Calibrate"), "color2"),
            'FINISH': self._gtk.Button("complete", _("Finish"), None),
        }
        self.buttons['STEP_01'].connect("clicked", self.menu_item_clicked, {
            "name": _("Network"),
            "panel": "network"
        })
        self.buttons['STEP_02'].connect("clicked", self.menu_item_clicked, {
            "name":_("Settings"),
            "panel": "settings"
        })
        self.buttons['STEP_03'].connect("clicked", self.menu_item_clicked, {
            "name": _("Calibrate"),
            "panel": "zcalibrate"
        })
        self.buttons['FINISH'].connect("clicked", self.finish)

        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)

        for i, button in enumerate(self.buttons):
            if i < len(self.buttons)-1:
                # HACK
                number_button = self._gtk.Button(f"extruder-{i+1}", None, None)
                grid.attach(number_button, i, 0, 1, 1)
            grid.attach(self.buttons[button], i, 1, 1, 2)

        self.labels['syncraft_panel'] = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        self.labels['syncraft_panel'].attach(grid, 0, 0, 1, 2)

        self.content.add(self.labels['syncraft_panel'])


    def finish(self, button):
        self._config.set("syncraft", "welcome", "False")
        self._config.save_user_config_options()
        self._screen.restart_ks()