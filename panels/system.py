import datetime
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("System")
        super().__init__(screen, title)
        self.current_row = 0
        self.mem_multiplier = None
        self.cpu_flowbox = None
        self.cpu_labels = []
        self.scales = {}
        self.labels = {}
        self.grid = Gtk.Grid(column_spacing=10, row_spacing=5)
        self.backend = "Wayland" if screen.wayland else "XServer"
        self.disk_usages = []
        self._roots_pending = 0
        self._activation_id = 0

        self.sysinfo = screen.printer.system_info
        if not self.sysinfo:
            logging.debug("Asking for info")
            self.sysinfo = screen.restApi.send_request("machine/system_info")
            if "system_info" in self.sysinfo:
                screen.printer.system_info = self.sysinfo["system_info"]
                self.sysinfo = self.sysinfo["system_info"]

        if self.sysinfo:
            self.create_layout()
        else:
            self.content.add(Gtk.Label(label=_("No info available"), vexpand=True))

    def back(self):
        if not self.sysinfo:
            self._screen.panels_reinit.append("system")
        return False

    def activate(self):
        self._activation_id += 1
        self._current_activation = self._activation_id
        self._roots_pending = 0
        self.disk_usages = []
        for widget in self.labels.get("disk_usage", []):
            try:
                self.grid.remove(widget)
            except Exception:
                pass
            widget.destroy()
        for widget in self.scales.get("disk_usage", []):
            try:
                self.grid.remove(widget)
            except Exception:
                pass
            widget.destroy()
        self.labels["disk_usage"] = []
        self.scales["disk_usage"] = []
        self._screen._ws.api.get_file_roots(self._on_roots_received)

    def _on_roots_received(self, data, method, params):
        if getattr(self, "_activation_id", 0) != self._current_activation:
            return
        if "error" in data:
            logging.error(f"Error getting file roots {data['error']}")
            self._update_disk_display()
            return
        roots = data.get("result", [])
        if not roots:
            logging.debug("No file roots found, falling back to gcodes")
            self._roots_pending = 1
            self._screen._ws.api.get_dir_info(self._update_disk_usage, "gcodes")
            return
        for root in roots:
            root_name = root.get("name", "unknown")
            self._roots_pending += 1
            self._screen._ws.api.get_dir_info(self._update_disk_usage, root_name)

    def _update_disk_usage(self, data, method, params):
        if getattr(self, "_activation_id", 0) != self._current_activation:
            return
        if "error" in data:
            logging.error(f"Error getting disk usage {data['error']}")
            self._roots_pending -= 1
            if self._roots_pending <= 0:
                self._update_disk_display()
            return
        if "disk_usage" not in data.get("result", {}):
            logging.error(data)
            self._roots_pending -= 1
            if self._roots_pending <= 0:
                self._update_disk_display()
            return
        disk_usage = data["result"]["disk_usage"]
        root_info = data["result"].get("root_info", {})
        root_name = root_info.get("name") or (
            params.get("path") if isinstance(params, dict) else str(params)
        )
        key = (disk_usage.get("total"), disk_usage.get("used"), disk_usage.get("free"))
        for entry in self.disk_usages:
            if (
                entry["disk_usage"].get("total") == key[0]
                and entry["disk_usage"].get("used") == key[1]
                and entry["disk_usage"].get("free") == key[2]
            ):
                if root_name not in entry["names"]:
                    entry["names"].append(root_name)
                logging.debug(f"Root {root_name} merged with existing entry")
                self._roots_pending -= 1
                if self._roots_pending <= 0:
                    self._update_disk_display()
                return
        self.disk_usages.append({"names": [root_name], "disk_usage": disk_usage})
        self._roots_pending -= 1
        if self._roots_pending <= 0:
            self._update_disk_display()

    def _update_disk_display(self):
        GLib.idle_add(self._ui_rebuild_disks)

    def _ui_rebuild_disks(self):
        for child in self.disk_container.get_children():
            self.disk_container.remove(child)
            child.destroy()

        self.labels["disk_usage"] = []
        self.scales["disk_usage"] = []

        for du in self.disk_usages:
            names = ", ".join(du["names"])
            usage = du["disk_usage"]
            used = usage.get("used", 0)
            total = usage.get("total", 1)
            used_percent = (used / total) * 100 if total > 0 else 0

            label = Gtk.Label(label="", xalign=0, wrap=True, max_width_chars=50)
            label.set_line_wrap_mode(Gtk.WrapMode.WORD)
            label.get_style_context().add_class("printing-info")
            if len(self.disk_usages) == 1 and len(du["names"]) > 1:
                label.set_label(
                    f"{_('Disk')}: {self.format_size(used)} / {self.format_size(total)}"
                )
            else:
                label.set_label(
                    f"{_('Disk')} ({names}): {self.format_size(used)} / {self.format_size(total)}"
                )
            self.disk_container.pack_start(label, False, False, 0)
            self.labels["disk_usage"].append(label)

            scale = Gtk.ProgressBar(hexpand=True, show_text=False)
            scale.set_fraction(used_percent / 100)
            self.disk_container.pack_start(scale, False, False, 2)
            self.scales["disk_usage"].append(scale)

        self.disk_container.show_all()
        return False

    def create_layout(self):
        self.cpu_count = int(self.sysinfo["cpu_info"]["cpu_count"])
        self.labels["cpu_usage"] = Gtk.Label(label="", xalign=0)
        self.grid.attach(self.labels["cpu_usage"], 0, self.current_row, 1, 1)
        self.scales["cpu_usage"] = Gtk.ProgressBar(hexpand=True, show_text=False, fraction=0)
        self.grid.attach(self.scales["cpu_usage"], 1, self.current_row, 1, 1)
        self.current_row += 1

        self.labels["core_usage"] = Gtk.Label(label=_("Cores") + ":", xalign=0)
        self.grid.attach(self.labels["core_usage"], 0, self.current_row, 1, 1)

        self.cpu_flowbox = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=True,
            column_spacing=32,
            row_spacing=0,
            halign=Gtk.Align.FILL,
            hexpand=True,
        )
        self.cpu_flowbox.set_min_children_per_line(1)
        self.cpu_flowbox.get_style_context().add_class("monospaced")

        for i in range(self.cpu_count):
            label = Gtk.Label(label="  0%", halign=Gtk.Align.CENTER, hexpand=True)
            label.get_style_context().add_class("printing-info")
            self.cpu_labels.append(label)
            self.cpu_flowbox.add(label)

        self.grid.attach(self.cpu_flowbox, 1, self.current_row, 1, 1)
        self.current_row += 1

        self.labels["memory_usage"] = Gtk.Label(label="", xalign=0)
        self.grid.attach(self.labels["memory_usage"], 0, self.current_row, 1, 1)
        self.scales["memory_usage"] = Gtk.ProgressBar(hexpand=True, show_text=False, fraction=0)
        self.grid.attach(self.scales["memory_usage"], 1, self.current_row, 1, 1)
        self.current_row += 1

        self.labels["disk_usage"] = []
        self.scales["disk_usage"] = []
        self.disk_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.grid.attach(self.disk_container, 0, self.current_row, 2, 1)
        self.current_row += 1

        self.grid.attach(Gtk.Separator(), 0, self.current_row, 2, 1)
        self.current_row += 1
        self.populate_info()

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.grid)
        self.content.add(scroll)

    def set_mem_multiplier(self, data):
        memory_units = data.get("memory_units", "kB").lower()
        units_mapping = {
            "kb": 1024,
            "mb": 1024**2,
            "gb": 1024**3,
            "tb": 1024**4,
            "pb": 1024**5,
        }
        self.mem_multiplier = units_mapping.get(memory_units, 1)

    def add_label_to_grid(self, text, column, bold=False):
        if bold:
            text = f"<b>{text}</b>"
        label = Gtk.Label(label=text, use_markup=True, xalign=0, wrap=True)
        label.set_line_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.grid.attach(label, column, self.current_row, 1, 1)
        self.current_row += 1

    def populate_info(self):
        # date
        self.add_label_to_grid(self.prettify("date"), 0, bold=True)
        self.labels["date"] = Gtk.Label(label="", xalign=0)
        self.grid.attach(self.labels["date"], 1, self.current_row - 1, 1, 1)
        self.add_label_to_grid("", 0)

        # backend
        self.add_label_to_grid(self.prettify("backend"), 0, bold=True)
        self.labels["backend"] = Gtk.Label(label="", xalign=0)
        self.grid.attach(self.labels["backend"], 1, self.current_row - 1, 1, 1)
        self.add_label_to_grid("", 0)

        for category, data in self.sysinfo.items():
            if category == "python":
                self.add_label_to_grid(self.prettify(category), 0, bold=True)
                self.current_row -= 1
                self.add_label_to_grid(f"Version: {data['version_string'].split(' ')[0]}", 1)
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
                or not self.sysinfo[category]
            ):
                continue

            self.add_label_to_grid(self.prettify(category), 0, bold=True)

            if isinstance(data, dict):
                for key, value in data.items():
                    if key in ("version_parts", "memory_units") or not value:
                        continue
                    if key == "total_memory":
                        if not self.mem_multiplier:
                            self.set_mem_multiplier(data)
                        value = self.format_size(int(value) * self.mem_multiplier)
                    if isinstance(value, dict):
                        self.add_label_to_grid(self.prettify(key), 0)
                        self.current_row -= 1
                        for sub_key, sub_value in value.items():
                            if not sub_value:
                                continue
                            elif isinstance(sub_value, list) and sub_key == "ip_addresses":
                                for _ip in sub_value:
                                    self.add_label_to_grid(
                                        f"{_('IP Address')}: {_ip['address']}", 1
                                    )
                                continue
                            self.add_label_to_grid(f"{self.prettify(sub_key)}: {sub_value}", 1)
                    else:
                        self.add_label_to_grid(f"{self.prettify(key)}: {value}", 1)
            # Add empty line
            self.add_label_to_grid("", 0)

    def process_update(self, action, data):
        if not self.sysinfo:
            return
        if action == "notify_proc_stat_update":
            self.labels["cpu_usage"].set_label(f"CPU: {data['system_cpu_usage']['cpu']:3.0f}%")
            self.scales["cpu_usage"].set_fraction(float(data["system_cpu_usage"]["cpu"]) / 100)
            for i, label in enumerate(self.cpu_labels):
                label.set_label(f"{data['system_cpu_usage'][f'cpu{i}']:3.0f}%")

            self.labels["memory_usage"].set_label(
                _("Memory")
                + f": {(data['system_memory']['used'] / data['system_memory']['total']) * 100:.0f}%"
            )
            self.scales["memory_usage"].set_fraction(
                float(data["system_memory"]["used"]) / float(data["system_memory"]["total"])
            )

        now = datetime.datetime.now().astimezone()
        self.labels["date"].set_label(now.strftime("%a %b %e %H:%M:%S %Z %Y"))

        self.labels["backend"].set_label(self.backend)
