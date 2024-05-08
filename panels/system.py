import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.current_row = 0
        sysinfo = screen.printer.system_info
        logging.debug(sysinfo)

        self.grid = Gtk.Grid(column_spacing=10, row_spacing=5)
        self.populate_info(sysinfo)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.grid)
        self.content.add(scroll)

    def add_label_to_grid(self, text, column, bold=False):
        if bold:
            text = f"<b>{text}</b>"
        label = Gtk.Label(label=text, use_markup=True, xalign=0, wrap=True)
        self.grid.attach(label, column, self.current_row, 1, 1)
        self.current_row += 1

    def populate_info(self, sysinfo):
        logging.debug(sysinfo.items())
        for category, data in sysinfo.items():
            if category == "python":
                self.add_label_to_grid(self.prettify(category), 0, bold=True)
                self.add_label_to_grid(
                    f'Version: {data["version"][0]}.{data["version"][1]}', 1
                )
                continue

            if (
                category
                in (
                    "virtualization",
                    "provider",
                    "available_services",
                    "service_state",
                    "instance_ids",
                )
                or not sysinfo[category]
            ):
                continue

            self.add_label_to_grid(self.prettify(category), 0, bold=True)

            if isinstance(data, dict):
                for key, value in data.items():
                    if key in ("version_parts", "memory_units") or not value:
                        continue
                    if key == "total_memory":
                        memory_units = data.get("memory_units", "kB").lower()
                        units_mapping = {
                            "kb": 1024,
                            "mb": 1024**2,
                            "gb": 1024**3,
                            "tb": 1024**4,
                            "pb": 1024**5,
                        }
                        multiplier = units_mapping.get(memory_units, 1)
                        value = self.format_size(int(value) * multiplier)
                    if isinstance(value, dict):
                        self.add_label_to_grid(self.prettify(key), 0)
                        self.current_row -= 1
                        for sub_key, sub_value in value.items():
                            if not sub_value:
                                continue
                            elif (
                                isinstance(sub_value, list)
                                and sub_key == "ip_addresses"
                            ):
                                logging.info(sub_value)
                                for _ip in sub_value:
                                    self.add_label_to_grid(
                                        f"{self.prettify(sub_key)}: {_ip['address']}", 1
                                    )
                                continue
                            self.add_label_to_grid(
                                f"{self.prettify(sub_key)}: {sub_value}", 1
                            )
                    else:
                        self.add_label_to_grid(f"{self.prettify(key)}: {value}", 1)
