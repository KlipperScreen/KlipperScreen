import logging
import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Macros")
        super().__init__(screen, title)
        self.sort_reverse = False
        self.sort_btn = self._gtk.Button("arrow-up", _("Name"), "color1", self.bts, Gtk.PositionType.RIGHT, 1)
        self.sort_btn.connect("clicked", self.change_sort)
        self.sort_btn.set_hexpand(True)
        self.sort_btn.get_style_context().add_class("buttons_slim")
        self.options = {}
        self.macros = {}
        self.menu = ['macros_menu']

        adjust = self._gtk.Button("settings", " " + _("Settings"), "color2", self.bts, Gtk.PositionType.LEFT, 1)
        adjust.get_style_context().add_class("buttons_slim")
        adjust.connect("clicked", self.load_menu, 'options', _("Settings"))
        adjust.set_hexpand(False)

        sbox = Gtk.Box(vexpand=False)
        sbox.pack_start(self.sort_btn, True, True, 5)
        sbox.pack_start(adjust, True, True, 5)

        self.labels['macros_list'] = self._gtk.ScrolledWindow()
        self.labels['macros'] = Gtk.Grid()
        self.labels['macros_list'].add(self.labels['macros'])

        self.labels['macros_menu'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.labels['macros_menu'].pack_start(sbox, False, False, 0)
        self.labels['macros_menu'].pack_start(self.labels['macros_list'], True, True, 0)

        self.content.add(self.labels['macros_menu'])
        self.labels['options_menu'] = self._gtk.ScrolledWindow()
        self.labels['options'] = Gtk.Grid()
        self.labels['options_menu'].add(self.labels['options'])

    def activate(self):
        self.reload_macros()

    def add_gcode_macro(self, macro):
        section = self._printer.get_macro(macro)
        if section:
            if "rename_existing" in section:
                return
            if "gcode" in section:
                gcode = section["gcode"].split("\n")
            else:
                logging.error(f"gcode not found in {macro}\n{section}")
                return
        else:
            logging.debug(f"Couldn't load {macro}\n{section}")
            return
        name = Gtk.Label(hexpand=True, vexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
                         wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        name.set_markup(f"<big><b>{macro}</b></big>")

        btn = self._gtk.Button("resume", style="color3")
        btn.connect("clicked", self.run_gcode_macro, macro)
        btn.set_hexpand(False)
        btn.set_halign(Gtk.Align.END)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)

        row = Gtk.Box(spacing=5)
        row.get_style_context().add_class("frame-item")
        row.add(labels)
        row.add(btn)

        self.macros[macro] = {
            "row": row,
            "params": {},
        }

        pattern = re.compile(r'params\.(?P<param>[a-zA-Z0-9_]+)'
                             r'(?:\s*\|\s*default\(\s*(?P<default>[^\)]+)\s*\))?'
                             r'(?:\s*\|\s*(?P<type_hint>[a-zA-Z]+))?')
        for line in gcode:
            if line.startswith("{") and "params." in line:
                result = re.search(pattern, line)
                if result:
                    result = result.groupdict()
                    default = result.get("default", "")
                    type_hint = result.get("type_hint", "")
                    entry = Gtk.Entry(placeholder_text=default)
                    if type_hint == "int":
                        entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
                        entry.set_input_hints(Gtk.InputHints.NO_EMOJI)
                        entry.get_style_context().add_class("active")
                    elif type_hint == "float":
                        entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
                        entry.set_input_hints(Gtk.InputHints.EMOJI)
                        entry.get_style_context().add_class("active")
                    else:
                        entry.set_input_purpose(Gtk.InputPurpose.ALPHA)
                        entry.set_input_hints(Gtk.InputHints.NONE)
                    icon = self._gtk.PixbufFromIcon("hashtag")
                    entry.set_icon_from_pixbuf(Gtk.EntryIconPosition.SECONDARY, icon)
                    entry.connect("icon-press", self.on_icon_pressed)
                    self.macros[macro]["params"].update({result["param"]: entry})

        for param in self.macros[macro]["params"]:
            labels.add(Gtk.Label(param))
            self.macros[macro]["params"][param].connect("focus-in-event", self.show_keyboard)
            self.macros[macro]["params"][param].connect("focus-out-event", self._screen.remove_keyboard)
            labels.add(self.macros[macro]["params"][param])

    def show_keyboard(self, entry, event):
        self._screen.show_keyboard(entry, event)
        GLib.timeout_add(100, self.scroll_to_entry, entry)

    def scroll_to_entry(self, entry):
        self.labels['macros_list'].get_vadjustment().set_value(
            entry.get_allocation().y - 50
        )

    def on_icon_pressed(self, entry, icon_pos, event):
        entry.grab_focus()
        self._screen.remove_keyboard()
        if entry.get_input_purpose() == Gtk.InputPurpose.ALPHA:
            if entry.get_input_hints() in (Gtk.InputHints.NONE, Gtk.InputHints.EMOJI):
                entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
            else:
                entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
            entry.get_style_context().add_class("active")
        else:
            entry.set_input_purpose(Gtk.InputPurpose.ALPHA)
            entry.get_style_context().remove_class("active")
        self.show_keyboard(entry, event)

    def run_gcode_macro(self, widget, macro):
        params = ""
        for param in self.macros[macro]["params"]:
            self.macros[macro]["params"][param].set_sensitive(False)  # Move focus to prevent
            self.macros[macro]["params"][param].set_sensitive(True)  # reopening the osk
            value = self.macros[macro]["params"][param].get_text()
            if value:
                if re.findall(r'[G|M]\d{1,3}', macro):
                    params += f' {param}{value}'
                else:
                    params += f' {param}={value}'
        self._screen.show_popup_message(f"{macro} {params}", 1)
        self._screen._send_action(widget, "printer.gcode.script", {"script": f"{macro}{params}"})

    def change_sort(self, widget):
        self.sort_reverse ^= True
        if self.sort_reverse:
            self.sort_btn.set_image(self._gtk.Image("arrow-down", self._gtk.img_scale * self.bts))
        else:
            self.sort_btn.set_image(self._gtk.Image("arrow-up", self._gtk.img_scale * self.bts))
        self.sort_btn.show()

        GLib.idle_add(self.reload_macros)

    def reload_macros(self):
        self.labels['macros'].remove_column(0)
        self.macros = {}
        self.options = {}
        self.labels['options'].remove_column(0)
        self.load_gcode_macros()
        return False

    def load_gcode_macros(self):
        for macro in self._printer.get_gcode_macros():
            self.options[macro] = {
                "name": macro,
                "section": f"displayed_macros {self._screen.connected_printer}",
                "type": "binary"
            }
            show = self._config.get_config().getboolean(self.options[macro]["section"], macro.lower(), fallback=True)
            if macro not in self.macros and show:
                self.add_gcode_macro(macro)

        for macro in list(self.options):
            self.add_option('options', self.options, macro, self.options[macro])
        macros = sorted(self.macros, reverse=self.sort_reverse, key=str.casefold)
        for macro in macros:
            pos = macros.index(macro)
            self.labels['macros'].insert_row(pos)
            self.labels['macros'].attach(self.macros[macro]['row'], 0, pos, 1, 1)
            self.labels['macros'].show_all()

    def back(self):
        if len(self.menu) > 1:
            self.unload_menu()
            self.reload_macros()
            return True
        return False
