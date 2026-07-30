import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.gcode_renderer import RENDERER_OPTION_KEYS
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Settings")
        super().__init__(screen, title)
        self.printers = {}
        self.settings = {}
        self.langs = {}
        self.renderer_settings = {}
        self.menu = ["settings_menu"]
        renderer_options = []
        settings_options = []
        for option in self._config.get_configurable_options():
            name = list(option)[0]
            if name in RENDERER_OPTION_KEYS:
                renderer_options.append(option)
            else:
                settings_options.append(option)
        settings_options.append(
            {
                "gcode_renderer": {
                    "name": _("G-code Renderer"),
                    "icon": "bed-mesh",
                    "type": "menu",
                    "menu": "gcode_renderer",
                }
            }
        )
        settings_options.append(
            {"printers": {"name": _("Printer Connections"), "type": "menu", "menu": "printers"}}
        )
        settings_options.append({"lang": {"name": _("Language"), "type": "menu", "menu": "lang"}})
        self.labels["settings_menu"] = self._gtk.ScrolledWindow()
        self.labels["settings"] = Gtk.Grid()
        self.labels["settings_menu"].add(self.labels["settings"])
        for option in settings_options:
            name = list(option)[0]
            self.add_option("settings", self.settings, name, option[name])

        self.labels["gcode_renderer_menu"] = self._gtk.ScrolledWindow()
        self.labels["gcode_renderer"] = Gtk.Grid()
        self.labels["gcode_renderer_menu"].add(self.labels["gcode_renderer"])
        for option in renderer_options:
            name = list(option)[0]
            self.add_option("gcode_renderer", self.renderer_settings, name, option[name])

        self.labels["lang_menu"] = self._gtk.ScrolledWindow()
        self.labels["lang"] = Gtk.Grid()
        self.labels["lang_menu"].add(self.labels["lang"])
        for lang in ["system_lang", *self._config.lang_list]:
            self.langs[lang] = {
                "name": lang,
                "type": "button",
                "callback": self._screen.change_language,
            }
            self.add_option("lang", self.langs, lang, self.langs[lang])

        self.labels["printers_menu"] = self._gtk.ScrolledWindow()
        self.labels["printers"] = Gtk.Grid()
        self.labels["printers_menu"].add(self.labels["printers"])
        for printer in self._config.get_printers():
            pname = list(printer)[0]
            self.printers[pname] = {
                "name": pname,
                "section": f"printer {pname}",
                "type": "printer",
                "moonraker_host": printer[pname]["moonraker_host"],
                "moonraker_port": printer[pname]["moonraker_port"],
            }
            self.add_option("printers", self.printers, pname, self.printers[pname])

        self.content.add(self.labels["settings_menu"])
