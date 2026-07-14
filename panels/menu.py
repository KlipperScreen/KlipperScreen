import json
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.autogrid import AutoGrid


class Panel(ScreenPanel):
    def __init__(self, screen, title, items=None):
        super().__init__(screen, title)
        self.items = items
        self.j2_data = self._printer.get_printer_status_data()
        self._compiled_enable = {}
        self.create_menu_items()
        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.autogrid = AutoGrid()

    def activate(self):
        self.j2_data = self._printer.get_printer_status_data()
        self.add_content()

    def add_content(self):
        for child in self.scroll.get_children():
            self.scroll.remove(child)
        self.scroll.add(self.arrangeMenuItems(self.items))
        if not self.content.get_children():
            self.content.add(self.scroll)

    def arrangeMenuItems(self, items, columns=None, expand_last=False):
        self.autogrid.clear()
        enabled = []
        for item in items:
            key = list(item)[0]
            if not self.evaluate_enable(item[key]["enable"]):
                logging.debug(f"X > {key}")
                continue
            if item[key]["panel"] and self._is_shortcut_item(item[key]):
                continue
            enabled.append(self.labels[key])
        self.autogrid.__init__(enabled, columns, expand_last, self._screen.vertical_mode)
        return self.autogrid

    def create_menu_items(self):
        count = sum(bool(self.evaluate_enable(i[next(iter(i))]["enable"])) for i in self.items)
        scale = 1.08 if 12 < count <= 16 else None  # hack to fit a 4th row
        for i in range(len(self.items)):
            key = list(self.items[i])[0]
            item = self.items[i][key]

            name = self._screen.env.from_string(item["name"]).render(self.j2_data)
            icon = (
                self._screen.env.from_string(item["icon"]).render(self.j2_data)
                if item["icon"]
                else None
            )
            style = (
                self._screen.env.from_string(item["style"]).render(self.j2_data)
                if item["style"]
                else None
            )

            if icon == "notifications" and (
                bool(self._screen.server_info["warnings"])
                or bool(self._printer.warnings)
                or bool(self._screen.server_info["failed_components"])
                or bool(self._screen.server_info["missing_klippy_requirements"])
            ):
                icon = "notification_important"

            b = self._gtk.Button(icon, name, style or f"color{i % 4 + 1}", scale=scale)

            if item["panel"]:
                b.connect("clicked", self.menu_item_clicked, item)
            elif item["method"] == "ks_confirm_save":
                b.connect("clicked", self._screen.confirm_save)
            elif item["method"]:
                params = {}

                if item["params"] is not False:
                    try:
                        p = self._screen.env.from_string(item["params"]).render(self.j2_data)
                        params = json.loads(p)
                    except Exception as e:
                        logging.exception(f"Unable to parse parameters for [{name}]:\n{e}")
                        params = {}

                if item["confirm"] is not None:
                    b.connect(
                        "clicked",
                        self._screen._confirm_send_action,
                        item["confirm"],
                        item["method"],
                        params,
                    )
                else:
                    b.connect("clicked", self._screen._send_action, item["method"], params)
            else:
                b.connect("clicked", self._screen._go_to_submenu, key)
            self.labels[key] = b

    def evaluate_enable(self, enable):
        if enable == "True":
            return True

        if enable == "False":
            return False

        if enable == "{{ moonraker_connected }}":
            return self._screen.state.connected

        try:
            tmpl = self._compiled_enable.get(enable)
            if tmpl is None:
                tmpl = self._screen.env.from_string(enable)
                self._compiled_enable[enable] = tmpl

            return tmpl.render(self.j2_data) == "True"

        except Exception as e:
            logging.debug(f"Error evaluating enable statement: {enable}\n{e}")
            return False

    def _is_shortcut_item(self, item):
        shortcut_target = self._screen._config.get_main_config().get(
            "side_shortcut_target", fallback="notifications"
        )
        return item.get("panel") == shortcut_target
