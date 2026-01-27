import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Settings")
        super().__init__(screen, title)
        self.printers = self.settings = self.langs = {}
        self.menu = ['settings_menu']
        options = self._config.get_configurable_options().copy()
        options.append({"printers": {
            "name": _("Printer Connections"),
            "type": "menu",
            "menu": "printers"
        }})
        options.append({"lang": {
            "name": _("Language"),
            "type": "menu",
            "menu": "lang"
        }})
        self.labels['settings_menu'] = self._gtk.ScrolledWindow()
        self.labels['settings'] = Gtk.Grid()
        self.labels['settings_menu'].add(self.labels['settings'])
        for option in options:
            name = list(option)[0]
            if name == "use_dpms" and screen.wayland:
                continue
            self.add_option('settings', self.settings, name, option[name])

        self.labels['lang_menu'] = self._gtk.ScrolledWindow()
        self.labels['lang'] = Gtk.Grid()
        self.labels['lang_menu'].add(self.labels['lang'])
        for lang in ["system_lang", *self._config.lang_list]:
            self.langs[lang] = {
                "name": lang,
                "type": "button",
                "callback": self._screen.change_language,
            }
            self.add_option("lang", self.langs, lang, self.langs[lang])

        self.labels['printers_menu'] = self._gtk.ScrolledWindow()
        self.labels['printers'] = Gtk.Grid()
        self.labels['printers_menu'].add(self.labels['printers'])
        for printer in self._config.get_printers():
            pname = list(printer)[0]
            self.printers[pname] = {
                "name": pname,
                "section": f"printer {pname}",
                "type": "printer",
                "moonraker_host": printer[pname]['moonraker_host'],
                "moonraker_port": printer[pname]['moonraker_port'],
            }
            self.add_option("printers", self.printers, pname, self.printers[pname])

        self.content.add(self.labels['settings_menu'])
