# -*- coding: utf-8 -*-
import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango, GdkPixbuf
from jinja2 import Environment
from datetime import datetime
from math import log
from ks_includes.screen_panel import ScreenPanel

try:
    import psutil
    psutil_available = True
except ImportError:
    psutil_available = False
    logging.debug("psutil is not installed. Unable to do battery check.")


class BasePanel(ScreenPanel):
    def __init__(self, screen, title=None):
        super().__init__(screen, title)
        self.current_panel = None
        self.time_min = -1
        self.time_format = self._config.get_main_config().getboolean("24htime", True)
        self.time_update = None
        self.battery_update = None
        self.titlebar_items = []
        self.titlebar_name_type = None
        self.current_extruder = None
        self.last_usage_report = datetime.now()
        self.usage_report = 0
        self.active_nav = None

        styles_dir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles")

        # ===== Navigation Bar =====----------------------------------------------------------------------------------------------
        self.nav_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.nav_bar.set_hexpand(False)
        self.nav_bar.set_vexpand(True)
        self.nav_bar.get_style_context().add_class('nav-bar')
        self.nav_bar.set_size_request(70, -1)

        # WorkCell logo at top
        logo_path = os.path.join(styles_dir, "workcell_logo.svg")
        if os.path.exists(logo_path):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(logo_path, 48, 48)
            logo_image = Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            logo_image = Gtk.Image()
        logo_box = Gtk.Box()
        logo_box.get_style_context().add_class('nav-logo')
        logo_box.set_halign(Gtk.Align.CENTER)
        logo_box.set_valign(Gtk.Align.START)
        logo_box.set_margin_top(8)
        logo_box.set_margin_bottom(4)
        logo_box.add(logo_image)
        self.nav_bar.pack_start(logo_box, False, False, 0)

        # Nav button definitions: (key, icon_svg, panel_name)
        self.nav_buttons = {}
        nav_items = [
            ('home', os.path.join(styles_dir, "nav_home.svg"), 'main_menu'),
            ('controls', os.path.join(styles_dir, "nav_controls.svg"), 'move'),
            ('queue', os.path.join(styles_dir, "nav_queue.svg"), 'print_screen'),
            ('filament', os.path.join(styles_dir, "nav_filament.svg"), 'filament_panel'),
        ]

        for key, icon_path, panel_name in nav_items:
            btn = Gtk.Button()
            btn.set_can_focus(False)
            if os.path.exists(icon_path):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 32, 32)
                img = Gtk.Image.new_from_pixbuf(pixbuf)
            else:
                img = Gtk.Image()
            btn.set_image(img)
            btn.set_always_show_image(True)
            btn.connect("clicked", self._on_nav_clicked, panel_name, key)
            self.nav_buttons[key] = btn
            self.nav_bar.pack_start(btn, False, False, 0)

        # Spacer to push nav buttons toward top
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        self.nav_bar.pack_start(spacer, True, True, 0)

        # Keep control dict for compatibility with KlipperScreen internals
        self.control['back'] = Gtk.Button()
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = Gtk.Button()
        self.control['home'].connect("clicked", self._screen._menu_go_back, True)
        self.control['estop'] = Gtk.Button()
        self.control['estop'].connect("clicked", self.emergency_stop)
        self.control['estop'].set_no_show_all(True)
        self.shutdown = {"panel": "shutdown"}
        self.control['shutdown'] = Gtk.Button()
        self.control['shutdown'].connect("clicked", self.menu_item_clicked, self.shutdown)
        self.control['shutdown'].set_no_show_all(True)
        self.control['printer_select'] = Gtk.Button()
        self.control['printer_select'].connect("clicked", self._screen.show_printer_select)
        self.control['printer_select'].set_no_show_all(True)
        self.shorcut = {"panel": "gcode_macros", "icon": "custom-script"}
        self.control['shortcut'] = Gtk.Button()
        self.control['shortcut'].connect("clicked", self.menu_item_clicked, self.shorcut)
        self.control['shortcut'].set_no_show_all(True)

        # Hidden action bar for compatibility (not displayed)
        self.action_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.action_bar.set_no_show_all(True)

        # Titlebar (hidden but kept for compatibility)
        self.control['temp_box'] = Gtk.Box(spacing=10)
        self.titlelbl = Gtk.Label(hexpand=True, halign=Gtk.Align.CENTER, ellipsize=Pango.EllipsizeMode.END)
        self.control['time'] = Gtk.Label(label="00:00 AM")
        self.control['time_box'] = Gtk.Box(halign=Gtk.Align.END)
        self.control['time_box'].pack_end(self.control['time'], True, True, 10)

        self.labels['battery'] = Gtk.Label()
        self.labels['battery_icon'] = Gtk.Image()
        self.control['battery_box'] = Gtk.Box(halign=Gtk.Align.END)
        self.control['battery_box'].set_no_show_all(True)

        self.titlebar = Gtk.Box(spacing=5, valign=Gtk.Align.CENTER)
        self.titlebar.get_style_context().add_class("title_bar")
        self.titlebar.set_no_show_all(True)

        # Main layout: nav bar on left, content on right
        self.main_grid = Gtk.Grid()
        self.main_grid.attach(self.nav_bar, 0, 0, 1, 1)
        self.main_grid.attach(self.content, 1, 0, 1, 1)

        self.update_time()

    def _on_nav_clicked(self, widget, panel_name, nav_key):
        """Handle nav button click - navigate to the target panel."""
        # Don't navigate if we're already on this panel
        if self._screen._cur_panels and panel_name == self._screen._cur_panels[-1]:
            return
        self._screen.show_panel(panel_name, remove_all=True)

    def set_nav_active(self, nav_key):
        """Highlight the active nav button."""
        for key, btn in self.nav_buttons.items():
            ctx = btn.get_style_context()
            if key == nav_key:
                if not ctx.has_class('nav-active'):
                    ctx.add_class('nav-active')
            else:
                ctx.remove_class('nav-active')
        self.active_nav = nav_key

    def update_nav_from_panel(self, panel_name):
        """Update nav highlight based on which panel is showing."""
        panel_to_nav = {
            'main_menu': 'home',
            'job_status': 'home',
            'move': 'controls',
            'print_screen': 'queue',
            'filament_panel': 'filament',
        }
        nav_key = panel_to_nav.get(panel_name)
        if nav_key:
            self.set_nav_active(nav_key)

    # ===== Compatibility methods (kept for KlipperScreen internals) =====

    def load_battery_icons(self):
        return {}

    def reload_icons(self):
        pass

    def show_heaters(self, show=True):
        pass

    def get_icon(self, device, img_size):
        return None

    def activate(self):
        if self.time_update is None:
            self.time_update = GLib.timeout_add_seconds(1, self.update_time)

    def add_content(self, panel):
        self.current_panel = panel
        self.set_title(panel.title)
        self.content.add(panel.content)
        # Update nav highlight
        if self._screen._cur_panels:
            self.update_nav_from_panel(self._screen._cur_panels[-1])

    def back(self, widget=None):
        if self.current_panel is None:
            return
        self._screen.remove_keyboard()
        if hasattr(self.current_panel, "back") \
                and not self.current_panel.back() \
                or not hasattr(self.current_panel, "back"):
            self._screen._menu_go_back()

    def process_update(self, action, data):
        if action == "notify_proc_stat_update":
            return
        if action == "notify_update_response":
            if self.update_dialog is None:
                self.show_update_dialog()
            if 'message' in data:
                self.labels['update_progress'].set_text(
                    f"{self.labels['update_progress'].get_text().strip()}\n"
                    f"{data['message']}\n")
            if 'complete' in data and data['complete']:
                logging.info("Update complete")
                if self.update_dialog is not None:
                    try:
                        self.update_dialog.set_response_sensitive(Gtk.ResponseType.OK, True)
                        self.update_dialog.get_widget_for_response(Gtk.ResponseType.OK).show()
                    except AttributeError:
                        logging.error("error trying to show the updater button the dialog might be closed")
                        self._screen.updating = False
                        for dialog in self._screen.dialogs:
                            self._gtk.remove_dialog(dialog)
            return
        if action != "notify_status_update" or self._screen.printer is None:
            return

    def remove(self, widget):
        self.content.remove(widget)

    def set_control_sensitive(self, value=True, control='shortcut'):
        if control in self.control:
            self.control[control].set_sensitive(value)

    def show_shortcut(self, show=True):
        pass

    def show_printer_select(self, show=True):
        pass

    def set_title(self, title):
        pass

    def update_time(self):
        now = datetime.now()
        confopt = self._config.get_main_config().getboolean("24htime", True)
        if now.minute != self.time_min or self.time_format != confopt:
            if confopt:
                self.control['time'].set_text(f'{now:%H:%M }')
            else:
                self.control['time'].set_text(f'{now:%I:%M %p}')
            self.time_min = now.minute
            self.time_format = confopt
        return True

    def battery_percentage(self):
        return False

    def set_ks_printer_cfg(self, printer):
        ScreenPanel.ks_printer_cfg = self._config.get_printer_config(printer)
        if self.ks_printer_cfg is not None:
            self.titlebar_name_type = self.ks_printer_cfg.get("titlebar_name_type", None)
            titlebar_items = self.ks_printer_cfg.get("titlebar_items", None)
            if titlebar_items is not None:
                self.titlebar_items = [str(i.strip()) for i in titlebar_items.split(',')]
                logging.info(f"Titlebar name type: {self.titlebar_name_type} items: {self.titlebar_items}")
            else:
                self.titlebar_items = []

    def show_update_dialog(self):
        if self.update_dialog is not None:
            return
        button = [{"name": _("Finish"), "response": Gtk.ResponseType.OK}]
        self.labels['update_progress'] = Gtk.Label(hexpand=True, vexpand=True, ellipsize=Pango.EllipsizeMode.END)
        self.labels['update_scroll'] = self._gtk.ScrolledWindow(steppers=False)
        self.labels['update_scroll'].set_property("overlay-scrolling", True)
        self.labels['update_scroll'].add(self.labels['update_progress'])
        self.labels['update_scroll'].connect("size-allocate", self._autoscroll)
        dialog = self._gtk.Dialog(_("Updating"), button, self.labels['update_scroll'], self.finish_updating)
        dialog.connect("delete-event", self.close_update_dialog)
        dialog.set_response_sensitive(Gtk.ResponseType.OK, False)
        dialog.get_widget_for_response(Gtk.ResponseType.OK).hide()
        self.update_dialog = dialog
        self._screen.updating = True

    def finish_updating(self, dialog, response_id):
        if response_id != Gtk.ResponseType.OK:
            return
        logging.info("Finishing update")
        self._screen.updating = False
        self._gtk.remove_dialog(dialog)
        self._screen._menu_go_back(home=True)

    def close_update_dialog(self, *args):
        logging.info("Closing update dialog")
        if self.update_dialog in self._screen.dialogs:
            self._screen.dialogs.remove(self.update_dialog)
        self.update_dialog = None
        self._screen._menu_go_back(home=True)
