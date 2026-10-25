import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Settings")
        super().__init__(screen, title)
        self.printers = self.settings = self.langs = {}
        self.menu = ["settings_menu"]
        options = self._config.get_configurable_options().copy()

        # Group the displayable options by category
        # anything without a category falls back to "Others"
        categories = {}
        for option in options:
            name = list(option)[0]
            if name == "use_dpms" and screen.wayland:
                continue
            opt = option[name]
            if opt.get("type") is None:
                # Displayed on the specific panel itself
                continue
            category = opt.get("category", _("Others"))
            categories.setdefault(category, []).append(option)

        # Main settings menu: one entry per category
        self.labels["settings_menu"] = self._gtk.ScrolledWindow()
        self.labels["settings"] = Gtk.Grid()
        self.labels["settings"].set_row_spacing(2)
        self.labels["settings_menu"].add(self.labels["settings"])

        for category_name, cat_options in categories.items():
            key = category_name.lower().replace(" ", "_")

            grid = Gtk.Grid()
            grid.set_row_spacing(2)
            self.labels[f"{key}_grid"] = grid

            header = Gtk.Label()
            header.set_markup(f"<big><b>{category_name}</b></big>")
            header.set_halign(Gtk.Align.START)
            header.set_margin_top(10)
            header.set_margin_bottom(8)
            header.set_margin_start(10)
            header.set_margin_end(10)
            grid.attach(header, 0, 0, 1, 1)

            cat_opts = {}
            for option in cat_options:
                optname = list(option)[0]
                self.add_option(
                    f"{key}_grid",
                    cat_opts,
                    optname,
                    option[optname],
                    row_offset=1,
                )

            self.labels[f"{key}_menu"] = self._gtk.ScrolledWindow()
            self.labels[f"{key}_menu"].add(grid)

            self.add_option(
                "settings",
                self.settings,
                key,
                {"name": category_name, "type": "menu", "menu": key},
            )

        self.labels["lang_menu"] = self._gtk.ScrolledWindow()
        self.labels["lang"] = Gtk.Grid()
        self.labels["lang_menu"].add(self.labels["lang"])
        for lang in ["system_lang", *self._config.lang_list]:
            if lang == "system_lang":
                name = _("System language")
            else:
                name = f"{self._config.get_language_name(lang)} ({lang})"
            self.langs[lang] = {
                "name": name,
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

        # Top-level entries that navigate to the grids built above
        self.add_option(
            "settings",
            self.settings,
            "printers",
            {"name": _("Printer Connections"), "type": "menu", "menu": "printers"},
        )
        self.add_option(
            "settings",
            self.settings,
            "lang",
            {"name": _("Language"), "type": "menu", "menu": "lang"},
        )

        self.content.add(self.labels["settings_menu"])
