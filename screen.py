#!/usr/bin/python

import ast
import argparse
import gc
import json
import logging
import os
import subprocess
import pathlib
import traceback  # noqa
import locale
import re
import sys
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from importlib import import_module
from jinja2 import Environment
from signal import SIGTERM
from datetime import datetime

from ks_includes import functions
from ks_includes.KlippyWebsocket import KlippyWebsocket
from ks_includes.KlippyRest import KlippyRest
from ks_includes.files import KlippyFiles
from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.printer import Printer
from ks_includes.widgets.keyboard import Keyboard
from ks_includes.widgets.prompts import Prompt
from ks_includes.widgets.lockscreen import LockScreen
from ks_includes.widgets.screensaver import ScreenSaver
from ks_includes.config import KlipperScreenConfig
from panels.base_panel import BasePanel


logging.getLogger("urllib3").setLevel(logging.WARNING)

klipperscreendir = pathlib.Path(__file__).parent.resolve()


def set_text_direction(lang=None):
    rtl_languages = ['he']
    if lang is None:
        for lng in rtl_languages:
            if locale.getlocale()[0].startswith(lng):
                lang = lng
                break
    if lang in rtl_languages:
        Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
        logging.debug("Enabling RTL mode")
        return False
    Gtk.Widget.set_default_direction(Gtk.TextDirection.LTR)
    return True


class KlipperScreen(Gtk.Window):
    _cur_panels = []
    connecting = False
    connecting_to_printer = None
    connected_printer = None
    files = None
    keyboard = None
    panels = {}
    popup_message = None
    printers = None
    printer = None
    updating = False
    _ws = None
    reinit_count = 0
    max_retries = 4
    initialized = False
    initializing = False
    popup_timeout = None
    wayland = False
    notification_log = []
    prompt = None
    tempstore_timeout = None
    check_dpms_timeout = None

    def __init__(self, args):
        self.server_info = None
        try:
            super().__init__(title="KlipperScreen")
        except Exception as e:
            logging.exception(f"{e}\n\n{traceback.format_exc()}")
            raise RuntimeError from e
        GLib.set_prgname('KlipperScreen')
        self.blanking_time = 600
        self.use_dpms = True
        self.apiclient = None
        self.dialogs = []
        self.confirm = None
        self.panels_reinit = []
        self.last_popup_time = datetime.now()

        configfile = os.path.normpath(os.path.expanduser(args.configfile))

        self._config = KlipperScreenConfig(configfile, self)
        self.lang_ltr = set_text_direction(self._config.get_main_config().get("language", None))
        self.env = Environment(extensions=["jinja2.ext.i18n"], autoescape=True)
        self.env.install_gettext_translations(self._config.get_lang())

        self.connect("key-press-event", self._key_press_event)
        self.connect("configure_event", self.update_size)
        display = Gdk.Display.get_default()
        self.display_number = os.environ.get('DISPLAY') or ':0'
        logging.debug(f"Display for xset: {self.display_number}")
        monitor_amount = Gdk.Display.get_n_monitors(display)
        for i in range(monitor_amount):
            m = display.get_monitor(i)
            logging.info(f"Screen {i}: {m.get_geometry().width}x{m.get_geometry().height}")
        try:
            mon_n = int(args.monitor)
            if not (-1 < mon_n < monitor_amount):
                raise ValueError
        except ValueError:
            mon_n = 0
        logging.info(f"Monitors: {monitor_amount} using number: {mon_n}")
        monitor = display.get_monitor(mon_n)
        self.wayland = display.get_name().startswith('wayland') or display.get_primary_monitor() is None
        logging.info(f"Wayland: {self.wayland} Display name: {display.get_name()}")
        self.width = self._config.get_main_config().getint("width", None)
        self.height = self._config.get_main_config().getint("height", None)
        if 'XDG_CURRENT_DESKTOP' in os.environ:
            logging.warning("Running inside a desktop environment is not recommended")
            if not self.width:
                self.width = max(int(monitor.get_geometry().width * .5), 480)
            if not self.height:
                self.height = max(int(monitor.get_geometry().height * .5), 320)
        if self.width or self.height:
            logging.info("Setting windowed mode")
            if mon_n > 0:
                logging.error("Monitor selection is only supported for fullscreen")
            self.set_resizable(True)
        else:
            self.width = monitor.get_geometry().width
            self.height = monitor.get_geometry().height
            self.fullscreen_on_monitor(self.get_screen(), mon_n)
        self.set_default_size(self.width, self.height)
        self.aspect_ratio = self.width / self.height
        self.vertical_mode = self.aspect_ratio < 1.0
        logging.info(f"Screen resolution: {self.width}x{self.height}")
        self.theme = self._config.get_main_config().get('theme')
        self.show_cursor = self._config.get_main_config().getboolean("show_cursor", fallback=False)
        self.setup_gtk_settings()
        self.style_provider = Gtk.CssProvider()
        self.screensaver = ScreenSaver(self)
        self.gtk = KlippyGtk(self)
        self.base_css = ""
        self.load_base_styles()
        self.set_icon_from_file(os.path.join(klipperscreendir, "styles", "icon.svg"))
        self.base_panel = BasePanel(self)
        self.change_theme(self.theme)
        self.overlay = Gtk.Overlay()
        self.add(self.overlay)
        self.overlay.add_overlay(self.base_panel.main_grid)
        self.show_all()
        self.update_cursor(self.show_cursor)
        min_ver = (3, 8)
        if sys.version_info < min_ver:
            self.show_error_modal(
                "Error",
                _("The system doesn't meet the minimum requirement") + "\n"
                + _("Minimum:") + f" Python {min_ver[0]}.{min_ver[1]}" + "\n"
                + _("System:") + f" Python {sys.version_info.major}.{sys.version_info.minor}"
            )
            return
        if self._config.errors:
            self.show_error_modal("Invalid config file", self._config.get_errors())
            return
        self.base_panel.activate()
        self.set_screenblanking_timeout(self._config.get_main_config().get('screen_blanking'))
        self.lock_screen = LockScreen(self)
        self.log_notification("KlipperScreen Started", 1)
        self.initial_connection()

    def update_cursor(self, show: bool):
        self.show_cursor = show
        self.gtk.set_cursor(show, window=self.get_window())

    def state_execute(self, state, callback):
        self.screensaver.close()
        if 'printer_select' in self._cur_panels:
            logging.debug(f"Connected printer chaged {state}")
            return False
        if state in ("printing", "paused"):
            self.set_screenblanking_timeout(self._config.get_main_config().get('screen_blanking_printing'))
        else:
            self.set_screenblanking_timeout(self._config.get_main_config().get('screen_blanking'))
            for warning in self.printer.warnings:
                self.show_popup_message(f"Klipper:\n{warning['message']}", level=2)
        callback()
        return False

    def initial_connection(self):
        self.printers = self._config.get_printers()
        state_callbacks = {
            "disconnected": self.state_disconnected,
            "error": self.state_error,
            "paused": self.state_paused,
            "printing": self.state_printing,
            "ready": self.state_ready,
            "startup": self.state_startup,
            "shutdown": self.state_shutdown
        }
        for printer in self.printers:
            printer["data"] = Printer(self.state_execute, state_callbacks)
        default_printer = self._config.get_main_config().get('default_printer')
        logging.debug(f"Default printer: {default_printer}")
        if [True for p in self.printers if default_printer in p]:
            self.connect_printer(default_printer)
        elif len(self.printers) == 1:
            pname = list(self.printers[0])[0]
            self.connect_printer(pname)
        else:
            self.base_panel.show_printer_select(True)
            self.show_printer_select()

    def close_websocket(self):
        self._ws.close()
        self.connected_printer = None
        self.printer.state = "disconnected"

    def connect_printer(self, name):
        self.connecting_to_printer = name
        if self._ws is not None and self._ws.connected:
            self.printer_initializing("Waiting Websocket closure")
            self.close_websocket()
            return
        gc.collect()
        self.connecting = True
        self.initialized = False
        self.initializing = False
        logging.info(f"Connecting to printer: {name}")
        ind = next(
            (
                self.printers.index(printer)
                for printer in self.printers
                if name == list(printer)[0]
            ),
            0,
        )
        self.printer = self.printers[ind]["data"]
        self.apiclient = KlippyRest(
            self.printers[ind][name]["moonraker_host"],
            self.printers[ind][name]["moonraker_port"],
            self.printers[ind][name]["moonraker_api_key"],
            self.printers[ind][name]["moonraker_path"],
            self.printers[ind][name]["moonraker_ssl"],
        )
        self._ws = KlippyWebsocket(
            {
                "on_connect": self.websocket_connected,
                "on_message": self._websocket_callback,
                "on_close": self.websocket_disconnected,
                "on_cancel": self.websocket_connection_cancel,
            },
            self.printers[ind][name]["moonraker_host"],
            self.printers[ind][name]["moonraker_port"],
            self.printers[ind][name]["moonraker_api_key"],
            self.printers[ind][name]["moonraker_path"],
            self.printers[ind][name]["moonraker_ssl"],
        )
        if self.files is None:
            self.files = KlippyFiles(self)
        else:
            self.files.reinit()

        self.reinit_count = 0
        self.printer_initializing(_("Connecting to %s") % name, True)
        self.connect_to_moonraker()

    def ws_subscribe(self):
        requested_updates = {
            "objects": {
                "bed_mesh": ["profile_name", "mesh_max", "mesh_min", "probed_matrix", "profiles"],
                "configfile": ["config", "warnings"],
                "display_status": ["progress", "message"],
                "fan": ["speed"],
                "gcode_move": ["extrude_factor", "gcode_position", "homing_origin", "speed_factor", "speed"],
                "idle_timeout": ["state"],
                "pause_resume": ["is_paused"],
                "print_stats": ["print_duration", "total_duration", "filament_used", "filename", "state", "message",
                                "info"],
                "toolhead": ["homed_axes", "estimated_print_time", "print_time", "position", "extruder",
                             "max_accel", "minimum_cruise_ratio", "max_velocity", "square_corner_velocity"],
                "virtual_sdcard": ["file_position", "is_active", "progress"],
                "webhooks": ["state", "state_message"],
                "firmware_retraction": ["retract_length", "retract_speed", "unretract_extra_length", "unretract_speed"],
                "motion_report": ["live_position", "live_velocity", "live_extruder_velocity"],
                "exclude_object": ["current_object", "objects", "excluded_objects"],
                "manual_probe": ['is_active'],
                "screws_tilt_adjust": ['results', 'error'],
            }
        }
        for extruder in self.printer.get_tools():
            requested_updates['objects'][extruder] = [
                "target", "temperature", "pressure_advance", "smooth_time", "power"]
        for h in self.printer.get_heaters():
            requested_updates['objects'][h] = ["target", "temperature", "power"]
        for t in self.printer.get_temp_sensors():
            requested_updates['objects'][t] = ["temperature"]
        for f in self.printer.get_temp_fans():
            requested_updates['objects'][f] = ["target", "temperature"]
        for f in self.printer.get_fans():
            requested_updates['objects'][f] = ["speed"]
        for f in self.printer.get_filament_sensors():
            requested_updates['objects'][f] = ["enabled", "filament_detected"]
        for p in self.printer.get_pwm_tools() + self.printer.get_output_pins():
            requested_updates['objects'][p] = ["value"]
        for led in self.printer.get_leds():
            requested_updates['objects'][led] = ["color_data"]

        self._ws.klippy.object_subscription(requested_updates)

    @staticmethod
    def _load_panel(panel):
        logging.debug(f"Loading panel: {panel}")
        panel_path = os.path.join(os.path.dirname(__file__), 'panels', f"{panel}.py")
        if not os.path.exists(panel_path):
            logging.error(f"Panel {panel} does not exist")
            raise FileNotFoundError(os.strerror(2), "\n" + panel_path)
        return import_module(f"panels.{panel}")

    def show_panel(self, panel, title=None, remove_all=False, panel_name=None, **kwargs):
        if panel_name is None:
            panel_name = panel
        if self._cur_panels and panel_name == self._cur_panels[-1]:
            logging.error("Panel is already is in view")
            return
        try:
            if remove_all:
                self.panels_reinit = list(self.panels)
                if panel in self._cur_panels:
                    self._menu_go_back(home=True)
                else:
                    self._remove_all_panels()
                    for dialog in self.dialogs:
                        self.gtk.remove_dialog(dialog)
            else:
                self._remove_current_panel()
            if panel_name not in self.panels:
                try:
                    self.panels[panel_name] = self._load_panel(panel).Panel(self, title, **kwargs)
                except Exception as e:
                    self.show_error_modal(f"Unable to load panel {panel}", f"{e}\n\n{traceback.format_exc()}")
                    return
            elif panel_name in self.panels_reinit:
                logging.info(f"Reinitializing panel {panel}")
                self.panels[panel_name].__init__(self, title, **kwargs)
                self.panels_reinit.remove(panel_name)
            self._cur_panels.append(panel_name)
            if 'extra' in kwargs and hasattr(self.panels[panel], "set_extra"):
                self.panels[panel].set_extra(**kwargs)
            self.attach_panel(panel_name)
        except Exception as e:
            logging.exception(f"Error attaching panel:\n{e}\n\n{traceback.format_exc()}")

    def set_panel_title(self, title):
        self.base_panel.set_title(title)

    def attach_panel(self, panel):
        if panel in self.panels_reinit:
            # this happens when the first panel needs a reinit
            self.reload_panels()
            return
        self.base_panel.add_content(self.panels[panel])
        logging.debug(f"Current panel hierarchy: {' > '.join(self._cur_panels)}")
        while len(self.panels[panel].menu) > 1:
            self.panels[panel].unload_menu()
        if hasattr(self.panels[panel], "process_update"):
            self.process_update("notify_status_update", self.printer.data)
        if hasattr(self.panels[panel], "activate"):
            self.panels[panel].activate()
        self.show_all()

    def log_notification(self, message, level=0):
        time = datetime.now().strftime("%H:%M:%S")
        log_entry = {"message": message, "level": level, "time": time}
        if len(self.notification_log) > 999:
            del self.notification_log[0]
        self.notification_log.append(log_entry)
        self.process_update("notify_log", log_entry)

    def notification_log_clear(self):
        self.notification_log.clear()

    def show_popup_message(self, message, level=3, from_ws=False):
        if from_ws:
            if (datetime.now() - self.last_popup_time).seconds < 1:
                return
            self.last_popup_time = datetime.now()

        self.screensaver.close()
        if self.popup_message is not None:
            self.close_popup_message()

        self.log_notification(message, level)

        msg = Gtk.Button(label=f"{message}", hexpand=True, vexpand=True)
        for widget in msg.get_children():
            if isinstance(widget, Gtk.Label):
                widget.set_line_wrap(True)
                widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                widget.set_max_width_chars(40)
        msg.connect("clicked", self.close_popup_message)
        msg.get_style_context().add_class("message_popup")
        if level == 1:
            msg.get_style_context().add_class("message_popup_echo")
            logging.info(f'echo: {message}')
        elif level == 2:
            msg.get_style_context().add_class("message_popup_warning")
            logging.info(f'warning: {message}')
        else:
            msg.get_style_context().add_class("message_popup_error")
            logging.info(f'error: {message}')

        popup = Gtk.Popover(relative_to=self.base_panel.titlebar,
                            halign=Gtk.Align.CENTER, width_request=int(self.width * .9))
        popup.get_style_context().add_class("message_popup_popover")
        popup.add(msg)
        popup.popup()

        self.popup_message = popup
        self.popup_message.show_all()

        if self._config.get_main_config().getboolean('autoclose_popups', True):
            if self.popup_timeout is not None:
                GLib.source_remove(self.popup_timeout)
                self.popup_timeout = None
            timeout = 300 if level == 2 else 10
            self.popup_timeout = GLib.timeout_add_seconds(timeout, self.close_popup_message)

        return False

    def close_popup_message(self, widget=None):
        if self.popup_message is None:
            return False
        self.popup_message.popdown()
        if self.popup_timeout is not None:
            GLib.source_remove(self.popup_timeout)
            self.popup_timeout = None
        self.popup_message = None
        return False

    def show_error_modal(self, title_msg, description="", help_msg=None):
        logging.error(f"Showing error modal: {title_msg} {description}")

        title = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.CHAR, hexpand=True, halign=Gtk.Align.START)
        title.set_markup(f"<b>{title_msg}</b>\n")
        version = Gtk.Label(label=f"{functions.get_software_version()}", halign=Gtk.Align.END)

        if not help_msg:
            help_msg = _("Provide KlipperScreen.log when asking for help.\n")
        message = Gtk.Label(label=f"{description}\n\n{help_msg}", wrap=True, wrap_mode=Pango.WrapMode.CHAR)
        scroll = self.gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(message)

        grid = Gtk.Grid()
        grid.attach(title, 0, 0, 1, 1)
        grid.attach(version, 1, 0, 1, 1)
        grid.attach(Gtk.Separator(), 0, 1, 2, 1)
        grid.attach(scroll, 0, 2, 2, 1)

        buttons = [
            {"name": _("Close"), "response": Gtk.ResponseType.CLOSE}
        ]
        self.gtk.Dialog(_("Error"), buttons, grid, self.error_modal_response)

    @staticmethod
    def error_modal_response(dialog, response_id):
        os._exit(1)

    def restart_ks(self, *args):
        logging.debug(f"Restarting {sys.executable} {' '.join(sys.argv)}")
        os.execv(sys.executable, ['python'] + sys.argv)
        # noinspection PyUnreachableCode
        self._ws.send_method("machine.services.restart", {"service": "KlipperScreen"})  # Fallback

    def setup_gtk_settings(self):
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-theme-name", "Adwaita")
        settings.set_property("gtk-application-prefer-dark-theme", False)

    def load_base_styles(self):
        base_conf_path = os.path.join(klipperscreendir, "styles", "base.conf")
        with open(base_conf_path) as f:
            self.style_options = json.load(f)
        self.gtk.color_list = self.style_options['graph_colors']
        base_css_path = os.path.join(klipperscreendir, "styles", "base.css")
        self.base_css = pathlib.Path(base_css_path).read_text()
        self.base_css = self.base_css.replace("KS_FONT_SIZE", f"{self.gtk.font_size}")
        self.base_css = self.customize_graph_colors(self.base_css)

        self.style_provider.load_from_data(self.base_css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            Gtk.CssProvider(),
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def load_custom_theme(self, theme_name):
        theme_dir = os.path.join(klipperscreendir, "styles", theme_name)
        theme_css_path = os.path.join(theme_dir, "style.css")
        theme_conf_path = os.path.join(theme_dir, "style.conf")

        theme_css = ""
        theme_options = {}

        if os.path.exists(theme_css_path):
            theme_css = pathlib.Path(theme_css_path).read_text()

        if os.path.exists(theme_conf_path):
            try:
                with open(theme_conf_path) as f:
                    theme_options = json.load(f)
            except Exception as e:
                logging.error(
                    f"Unable to parse custom template conf file:\n"
                    f"{e}\n\n"
                    f"{traceback.format_exc()}"
                )

        return theme_css, theme_options

    def customize_graph_colors(self, css_data):
        for category, category_data in self.style_options['graph_colors'].items():
            for i, color in enumerate(category_data['colors'], start=0):
                if category == "extruder":
                    class_name = f".graph_label_{category}{i}" if i > 0 else f".graph_label_{category}"
                elif category == "bed":
                    class_name = f".graph_label_heater_{category}"
                else:
                    class_name = f".graph_label_{category}_{i + 1}"
                css_data += f"\n{class_name} {{ border-left-color: #{color} }}"
        return css_data

    def update_style_provider(self, theme_css):
        css_data = self.customize_graph_colors(theme_css)
        css_data = self.base_css + css_data
        screen = Gdk.Screen.get_default()
        if self.style_provider:
            Gtk.StyleContext.remove_provider_for_screen(screen, self.style_provider)
        self.style_provider = Gtk.CssProvider()
        self.style_provider.load_from_data(css_data.encode())
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            self.style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def change_theme(self, theme_name=None):
        if not theme_name:
            theme_name = self._config.get_main_config().get('theme')
        self.gtk.update_themedir(theme_name)
        theme_css, theme_options = self.load_custom_theme(theme_name)
        self.style_options.update(theme_options)
        self.gtk.color_list = self.style_options['graph_colors']
        self.update_style_provider(theme_css)
        self.reload_icon_theme()

    def reload_icon_theme(self):
        self.panels_reinit = list(self.panels)
        self.base_panel.reload_icons()

    def _go_to_submenu(self, widget, name):
        logging.info(f"#### Go to submenu {name}")
        # Find current menu item
        if "main_menu" in self._cur_panels:
            menu = "__main"
        elif "splash_screen" in self._cur_panels:
            menu = "__splashscreen"
        else:
            menu = "__print"

        logging.info(f"#### Menu {menu}")
        disname = self._config.get_menu_name(menu, name)
        menuitems = self._config.get_menu_items(menu, name)
        if len(menuitems) != 0:
            self.show_panel("menu", disname, panel_name=name, items=menuitems)
            logging.info(f"menu, {disname}, panel_name={name}, items={menuitems}")
        else:
            logging.info("No items in menu")

    def _remove_all_panels(self):
        logging.debug("Removing all panels")
        while len(self._cur_panels) > 0:
            self._remove_current_panel()
            del self._cur_panels[-1]
        self._cur_panels.clear()
        self.screensaver.close()
        gc.collect()

    def _remove_current_panel(self):
        if not self._cur_panels:
            return
        if hasattr(self.panels[self._cur_panels[-1]], "deactivate"):
            self.panels[self._cur_panels[-1]].deactivate()
        self.base_panel.remove(self.panels[self._cur_panels[-1]].content)

    def _menu_go_back(self, widget=None, home=False):
        logging.info(f"#### Menu go {'home' if home else 'back'}")
        self.remove_keyboard()
        while len(self._cur_panels) > 1:
            self._remove_current_panel()
            del self._cur_panels[-1]
            if not home:
                break
        self.attach_panel(self._cur_panels[-1])

    def check_dpms_state(self):
        if not self.use_dpms:
            return False
        state = functions.get_DPMS_state()
        if state == functions.DPMS_State.Fail:
            logging.info("DPMS State FAIL: Stopping DPMS Check")
            self.set_dpms(False)
            return False
        elif state != functions.DPMS_State.On:
            if not self.screensaver.is_showing():
                self.screensaver.show()
        return True

    def wake_screen(self):
        # Wake the screen (it will go to standby as configured)
        if self._config.get_main_config().get('screen_blanking') != "off":
            logging.debug("Screen wake up")
            if not self.wayland:
                os.system(f"xset -display {self.display_number} dpms force on")

    def set_dpms(self, use_dpms):
        if not use_dpms:
            GLib.source_remove(self.check_dpms_timeout)
            self.check_dpms_timeout = None
        self.use_dpms = use_dpms
        logging.info(f"DPMS set to: {self.use_dpms}")
        if self.printer.state in ("printing", "paused"):
            self.set_screenblanking_timeout(self._config.get_main_config().get('screen_blanking_printing'))
        else:
            self.set_screenblanking_timeout(self._config.get_main_config().get('screen_blanking'))

    def set_screenblanking_printing_timeout(self, time):
        if self.printer.state in ("printing", "paused"):
            self.set_screenblanking_timeout(time)

    def set_screenblanking_timeout(self, time):
        if not self.wayland:
            os.system(f"xset -display {self.display_number} s off")
        self.use_dpms = self._config.get_main_config().getboolean("use_dpms", fallback=True)

        if time == "off":
            logging.debug(f"Screen blanking: {time}")
            self.blanking_time = 0
            if not self.wayland:
                os.system(f"xset -display {self.display_number} dpms 0 0 0")
            return

        self.blanking_time = abs(int(time))
        logging.debug(f"Changing screen blanking to: {self.blanking_time}")
        if self.use_dpms and functions.dpms_loaded is True:
            if not self.wayland:
                os.system(f"xset -display {self.display_number} +dpms")
            if functions.get_DPMS_state() == functions.DPMS_State.Fail:
                logging.info("DPMS State FAIL")
                self.show_popup_message(_("DPMS has failed to load and has been disabled"))
                self._config.set("main", "use_dpms", "False")
                self._config.save_user_config_options()
            else:
                logging.debug("Using DPMS")
                if not self.wayland:
                    os.system(f"xset -display {self.display_number} dpms 0 {self.blanking_time} 0")
                if self.check_dpms_timeout is None:
                    self.check_dpms_timeout = GLib.timeout_add_seconds(1, self.check_dpms_state)
                return
        # Without dpms just blank the screen
        logging.debug("Not using DPMS")
        if not self.wayland:
            os.system(f"xset -display {self.display_number} dpms 0 0 0")
        self.screensaver.reset_timeout()
        return

    def show_printer_select(self, widget=None):
        self.base_panel.show_heaters(False)
        self.show_panel("printer_select", remove_all=True)

    def websocket_connection_cancel(self):
        self.printer_initializing(
            _("Cannot connect to Moonraker") + '\n\n'
            + f'{self.apiclient.status}'
        )

    def websocket_connected(self):
        logging.debug("### websocket_connected")
        self._ws.klippy.identify_client(functions.get_software_version(), self._ws.api_key)
        self.reinit_count = 0
        self.connecting = False
        self.connected_printer = self.connecting_to_printer
        self.base_panel.set_ks_printer_cfg(self.connected_printer)
        self.init_moonraker_components()
        self.init_klipper()

    def websocket_disconnected(self):
        logging.debug("### websocket_disconnected")
        self.printer.state = "disconnected"
        self.connecting = True
        self.connected_printer = None
        self.initialized = False
        if 'printer_select' not in self._cur_panels:
            self.printer_initializing(_("Lost Connection to Moonraker"), go_to_splash=True)
            self.connect_printer(self.connecting_to_printer)
        else:
            self.panels['printer_select'].disconnected_callback()

    def state_disconnected(self):
        logging.debug("### Going to disconnected")
        self.printer.stop_tempstore_updates()
        self.initialized = False
        self.reinit_count = 0
        self._init_printer(_("Klipper has disconnected"), go_to_splash=True)

    def state_error(self):
        msg = _("Klipper has encountered an error.") + "\n"
        state = self.printer.get_stat("webhooks", "state_message")
        if "FIRMWARE_RESTART" in state:
            msg += _("A FIRMWARE_RESTART may fix the issue.") + "\n"
        elif "micro-controller" in state:
            msg += _("Please recompile and flash the micro-controller.") + "\n"
        self.printer_initializing(msg + "\n" + state, go_to_splash=True)

    def state_paused(self):
        self.state_printing()
        if self._config.get_main_config().getboolean("auto_open_extrude", fallback=True):
            self.show_panel("extrude")

    def state_printing(self):
        self.show_panel("job_status", remove_all=True)

    def state_ready(self, wait=True):
        # Do not return to main menu if completing a job, timeouts/user input will return
        if "job_status" in self._cur_panels and wait:
            return
        if not self.initialized:
            logging.debug("Printer not initialized yet")
            self.printer.state = "not ready"
            return
        self.files.refresh_files()
        self.show_panel("main_menu", remove_all=True, items=self._config.get_menu_items("__main"))

    def state_startup(self):
        self.printer_initializing(_("Klipper is attempting to start"))

    def state_shutdown(self):
        self.printer.stop_tempstore_updates()
        msg = self.printer.get_stat("webhooks", "state_message")
        self.printer_initializing(_("Klipper has shutdown") + "\n\n" + msg, go_to_splash=True)

    def toggle_shortcut(self, show):
        if show and not self.printer.get_printer_status_data()["printer"]["gcode_macros"]["count"] > 0:
            self.show_popup_message(
                _("No elegible macros:") + "\n"
                + _("macros with a name starting with '_' are hidden") + "\n"
                + _("macros that use 'rename_existing' are hidden") + "\n"
                + _("LOAD_FILAMENT/UNLOAD_FILAMENT are hidden and should be used from extrude") + "\n"
            )
        self.base_panel.show_shortcut(show)

    def change_language(self, widget, lang):
        self._config.install_language(lang)
        self.lang_ltr = set_text_direction(lang)
        self.env.install_gettext_translations(self._config.get_lang())
        self._config._create_configurable_options(self)
        self._config.set('main', 'language', lang)
        self._config.save_user_config_options()
        self.reload_panels()

    def reload_panels(self, *args):
        if "printer_select" in self._cur_panels:
            self.show_printer_select()
            return
        home = self._cur_panels[0]
        self.panels_reinit = list(self.panels)
        self._remove_all_panels()
        if home == "main_menu":
            self.show_panel(home, items=self._config.get_menu_items("__main"))
        else:
            self.show_panel(home)

    def _websocket_callback(self, action, data):
        if self.connecting:
            logging.debug("Not connected")
            return
        if action == "notify_klippy_disconnected":
            self.printer.process_update({'webhooks': {'state': "disconnected"}})
            return
        elif action == "notify_klippy_shutdown":
            self.printer.process_update({'webhooks': {'state': "shutdown"}})
            return
        elif action == "notify_klippy_ready":
            if not self.initialized:
                self.reinit_count = 0
                self.init_klipper()
                return
            self.printer.process_update({'webhooks': {'state': "ready"}})
            return
        elif action == "notify_status_update" and self.printer.state != "shutdown":
            self.printer.process_update(data)
            if 'manual_probe' in data and data['manual_probe']['is_active'] and 'zcalibrate' not in self._cur_panels:
                self.show_panel("zcalibrate")
            if "screws_tilt_adjust" in data and 'bed_level' not in self._cur_panels:
                self.show_panel("bed_level")
        elif action == "notify_filelist_changed":
            if self.files is not None:
                self.files.process_update(data)
            return
        elif action == "notify_metadata_update":
            self.files.request_metadata(data['filename'])
            return
        elif action == "notify_update_response":
            if 'message' in data and 'Error' in data['message']:
                logging.error(f"{action}:{data['message']}")
                self.show_popup_message(data['message'], 3, from_ws=True)
                if "KlipperScreen" in data['message']:
                    self.restart_ks()
        elif action == "notify_power_changed":
            logging.debug("Power status changed: %s", data)
            self.printer.process_power_update(data)
            self.panels['splash_screen'].check_power_status()
        elif action == "notify_gcode_response" and self.printer.state not in ["error", "shutdown"]:
            if re.match('^(?:ok\\s+)?(B|C|T\\d*):', data):
                return
            if data.startswith("// action:"):
                self.process_action(data[10:])
                return
            elif data.startswith("echo: "):
                self.show_popup_message(data[6:], 1, from_ws=True)
            elif "!! Extrude below minimum temp" in data:
                if self._cur_panels[-1] != "temperature":
                    self.show_panel("temperature", extra=self.printer.get_stat("toolhead", "extruder"))
                self.show_popup_message(_("Temperature too low to extrude"))
                return
            elif data.startswith("!! "):
                self.show_popup_message(data[3:], 3, from_ws=True)
            elif (
                "unknown" in data.lower()
                and "TESTZ" not in data
                and "MEASURE_AXES_NOISE" not in data
                and "ACCELEROMETER_QUERY" not in data
            ):
                self.show_popup_message(data, from_ws=True)
            elif "SAVE_CONFIG" in data and self.printer.state == "ready":
                script = {"script": "SAVE_CONFIG"}
                self._confirm_send_action(
                    None,
                    _("Save configuration?") + "\n\n" + _("Klipper will reboot"),
                    "printer.gcode.script",
                    script
                )
        self.process_update(action, data)

    def process_action(self, action):
        if action.startswith("prompt"):
            if action.startswith("prompt_begin"):
                if self.prompt is not None:
                    self.prompt.end()
                self.prompt = Prompt(self)
            if self.prompt is None:
                return
            self.prompt.decode(action)
        if action.startswith("ks_show"):
            self.parse_ks_action(action[8:].strip())

    def parse_ks_action(self, action):
        action = action.split(" ", 1)
        if len(action) == 2:
            panel, params = action
            key, value = params.split("=", 1)
            key = key.strip()
            value = value.strip()
            params = {key: ast.literal_eval(value)}
            self.show_panel(panel, **params)
        else:
            self.show_panel(*action)

    def process_update(self, *args):
        self.base_panel.process_update(*args)
        if self._cur_panels and hasattr(self.panels[self._cur_panels[-1]], "process_update"):
            self.panels[self._cur_panels[-1]].process_update(*args)

    def _confirm_send_action(self, widget, text, method, params=None):
        buttons = [
            {"name": _("Accept"), "response": Gtk.ResponseType.OK, "style": 'dialog-info'},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'}
        ]

        try:
            j2_temp = self.env.from_string(text)
            text = j2_temp.render()
        except Exception as e:
            logging.debug(f"Error parsing jinja for confirm_send_action\n{e}\n\n{traceback.format_exc()}")

        label = Gtk.Label(hexpand=True, vexpand=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                          wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        label.set_markup(text)

        if self.confirm is not None:
            self.gtk.remove_dialog(self.confirm)
        self.confirm = self.gtk.Dialog(
            "KlipperScreen", buttons, label, self._confirm_send_action_response, method, params
        )

    def _confirm_send_action_response(self, dialog, response_id, method, params):
        self.gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            self._send_action(None, method, params)

    def _send_action(self, widget, method, params):
        logging.info(f"{method}: {params}")
        if isinstance(widget, Gtk.Button):
            self.gtk.Button_busy(widget, True)
            self._ws.send_method(method, params, self.enable_widget, widget)
        else:
            self._ws.send_method(method, params)

    def enable_widget(self, *args):
        for x in args:
            if isinstance(x, Gtk.Button):
                GLib.timeout_add(150, self.gtk.Button_busy, x, False)

    def printer_initializing(self, msg, go_to_splash=False):
        if 'splash_screen' not in self.panels or go_to_splash:
            self.show_panel("splash_screen", remove_all=True)
        self.panels['splash_screen'].update_text(msg)
        self.log_notification(msg, 0)

    def search_power_devices(self, devices):
        found_devices = []
        if self.connected_printer is None or not devices:
            return found_devices
        devices = [str(i.strip()) for i in devices.split(',')]
        power_devices = self.printer.get_power_devices()
        if power_devices:
            found_devices = [dev for dev in devices if dev in power_devices]
            logging.info(f"Found {found_devices}", )
        return found_devices

    def power_devices(self, widget=None, devices=None, on=False):
        devs = self.search_power_devices(devices)
        for dev in devs:
            if on:
                self._ws.klippy.power_device_on(dev)
            else:
                self._ws.klippy.power_device_off(dev)

    def _init_printer(self, msg, go_to_splash=False):
        self.printer_initializing(msg, go_to_splash)
        self.initializing = False
        if self._ws.connected and not self._ws.closing:
            GLib.timeout_add_seconds(4, self.init_klipper)
        else:
            GLib.timeout_add_seconds(4, self.connect_to_moonraker)

    def connect_to_moonraker(self):
        if self.initializing:
            logging.info("Already Initializing")
            return False
        if self._ws.closing:
            logging.info("Cancelling attempt")
            return False
        self.initializing = True
        if self.reinit_count > self.max_retries or 'printer_select' in self._cur_panels:
            logging.info("Stopping Retries")
            self.printer_initializing(_("Cannot connect to Moonraker") + "\n\n"
                                      + f'{self.apiclient.status}')
            self.initializing = False
            return False
        self.server_info = self.apiclient.get_server_info()
        if not self.server_info:
            logging.info("Cannot get server info")
            if self.reinit_count > 0:
                self._init_printer(_("Cannot connect to Moonraker") + "\n\n"
                                   + _("Retrying") + f" #{self.reinit_count}")
            else:
                self._init_printer(_("Connecting to %s") % self.connecting_to_printer)
            self.initializing = False
            self.reinit_count += 1
            return False
        self._ws.initial_connect()
        return False

    def init_moonraker_components(self):
        popup = ''
        level = 2
        if self.server_info["warnings"]:
            popup += '\nMoonraker warnings:\n'
            for warning in self.server_info["warnings"]:
                warning = warning.replace('<br>', '').replace('<br/>', '\n').replace('</br>', '\n').replace(':', ':\n')
                popup += f"{warning}\n"
        if self.server_info["failed_components"]:
            popup += '\nMoonraker failed components:\n'
            for failed in self.server_info["failed_components"]:
                popup += f'[{failed}]\n'
        if self.server_info["missing_klippy_requirements"]:
            popup += '\nMissing Klipper configuration:\n'
            for missing in self.server_info["missing_klippy_requirements"]:
                popup += f'[{missing}]\n'
                level = 3
        if popup:
            self.show_popup_message(popup, level)
        if "power" in self.server_info["components"]:
            powerdevs = self.apiclient.send_request("machine/device_power/devices")
            if powerdevs is not False:
                self.printer.configure_power_devices(powerdevs)
        if "webcam" in self.server_info["components"]:
            cameras = self.apiclient.send_request("server/webcams/list")
            if cameras is not False:
                self.printer.configure_cameras(cameras['webcams'])
        if "spoolman" in self.server_info["components"]:
            self.printer.enable_spoolman()

    def init_klipper(self):
        if self.reinit_count > self.max_retries or 'printer_select' in self._cur_panels:
            logging.info("Stopping Retries")
            return False
        self.reinit_count += 1
        self.server_info = self.apiclient.get_server_info()
        logging.info(f"Moonraker info {self.server_info}")
        if self.server_info['klippy_connected'] is False:
            msg = _("Moonraker: connected") + "\n\n"
            msg += f"Klipper: {self.server_info['klippy_state']}" + "\n\n"
            if self.reinit_count <= self.max_retries:
                msg += _("Retrying") + f' #{self.reinit_count}'
            self.printer_initializing(msg)
            GLib.timeout_add_seconds(3, self.init_klipper)
            return False
        printer_info = self.apiclient.get_printer_info()
        if printer_info is False:
            self._init_printer("Unable to get printer info from moonraker")
            return False
        config = self.apiclient.send_request("printer/objects/query?configfile")
        if config is False:
            self._init_printer("Error getting printer configuration")
            return False
        self.printer.reinit(printer_info, config['status'])
        self.printer.available_commands = self.apiclient.get_gcode_help()
        info = self.apiclient.send_request("machine/system_info")
        if info and 'system_info' in info:
            self.printer.system_info = info['system_info']

        items = (
            'bed_mesh',
            'configfile',
            'display_status',
            'extruder',
            'fan',
            'gcode_move',
            'heater_bed',
            'idle_timeout',
            'pause_resume',
            'print_stats',
            'toolhead',
            'virtual_sdcard',
            'webhooks',
            'motion_report',
            'firmware_retraction',
            'exclude_object',
            'manual_probe',
            *self.printer.get_tools(),
            *self.printer.get_heaters(),
            *self.printer.get_temp_sensors(),
            *self.printer.get_fans(),
            *self.printer.get_temp_fans(),
            *self.printer.get_filament_sensors(),
            *self.printer.get_output_pins(),
            *self.printer.get_leds(),
        )

        data = self.apiclient.send_request("printer/objects/query?" + "&".join(items))
        if data is False:
            self._init_printer("Error getting printer object data")
            return False
        self.ws_subscribe()

        self.files.set_gcodes_path()

        logging.info("Printer initialized")
        self.initialized = True
        self.reinit_count = 0
        self.initializing = False
        self.printer.process_update(data['status'])
        self.log_notification("Printer Initialized", 1)
        return False

    def init_tempstore(self):
        if len(self.printer.get_temp_devices()) == 0:
            return False
        tempstore = self.apiclient.send_request("server/temperature_store")
        if tempstore:
            self.printer.init_temp_store(tempstore)
            if hasattr(self.panels[self._cur_panels[-1]], "update_graph_visibility"):
                self.panels[self._cur_panels[-1]].update_graph_visibility()
            if self.tempstore_timeout:
                self.remove_tempstore_timeout()
        else:
            logging.error(f'Tempstore not ready: {tempstore} Retrying in 5 seconds')
            if self.tempstore_timeout:
                return False
            if self.reinit_count < self.max_retries:
                self.reinit_count += 1
                self.tempstore_timeout = GLib.timeout_add_seconds(5, self.retry_init_tempstore)
            else:
                logging.error("Max retries reached. Stopping attempts to initialize tempstore.")
                self.remove_tempstore_timeout()
            return False

        server_config = self.apiclient.send_request("server/config")
        if server_config:
            try:
                self.printer.tempstore_size = server_config["config"]["data_store"]["temperature_store_size"]
                logging.info(f"Temperature store size: {self.printer.tempstore_size}")
            except KeyError:
                logging.error("Couldn't get the temperature store size")
        return False

    def remove_tempstore_timeout(self):
        GLib.source_remove(self.tempstore_timeout)
        self.tempstore_timeout = None
        self.reinit_count = 0

    def retry_init_tempstore(self):
        self.remove_tempstore_timeout()
        return self.init_tempstore()

    def show_keyboard(self, entry=None, event=None, box=None, close_cb=None):
        if entry is None:
            logging.debug("Error: no entry provided for keyboard")
            return
        if box is None:
            box = self.base_panel.content
        if close_cb is None:
            close_cb = self.remove_keyboard
        if self.keyboard is not None:
            self.remove_keyboard(box=box)
            entry.grab_focus()
        kbd_grid = Gtk.Grid()
        kbd_grid.set_size_request(self.gtk.content_width, self.gtk.keyboard_height)
        kbd_grid.set_vexpand(False)

        if self._config.get_main_config().getboolean("use-matchbox-keyboard", False):
            return self._show_matchbox_keyboard(kbd_grid)
        purpose = entry.get_input_purpose()
        kbd_width = 1
        if not self.vertical_mode and purpose in (Gtk.InputPurpose.DIGITS, Gtk.InputPurpose.NUMBER):
            kbd_grid.set_column_homogeneous(True)
            kbd_width = 2 if purpose == Gtk.InputPurpose.DIGITS else 3
        kbd_grid.attach(Gtk.Box(), 0, 0, 1, 1)
        kbd = Keyboard(self, close_cb, entry=entry, box=box)
        kbd_grid.attach(kbd, 1, 0, kbd_width, 1)
        kbd_grid.attach(Gtk.Box(), kbd_width + 1, 0, 1, 1)
        self.keyboard = {"box": kbd_grid}
        box.pack_end(kbd_grid, False, False, 0)
        box.show_all()

    def _show_matchbox_keyboard(self, kbd_grid):
        env = os.environ.copy()
        usrkbd = os.path.expanduser("~/.matchbox/keyboard.xml")
        if os.path.isfile(usrkbd):
            env["MB_KBD_CONFIG"] = usrkbd
        else:
            env["MB_KBD_CONFIG"] = "ks_includes/locales/keyboard.xml"
        p = subprocess.Popen(["matchbox-keyboard", "--xid"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=env)
        xid = int(p.stdout.readline())
        logging.debug(f"XID {xid}")
        logging.debug(f"PID {p.pid}")

        keyboard = Gtk.Socket()
        kbd_grid.get_style_context().add_class("keyboard_matchbox")
        kbd_grid.attach(keyboard, 0, 0, 1, 1)
        self.base_panel.content.pack_end(kbd_grid, False, False, 0)

        self.show_all()
        keyboard.add_id(xid)

        self.keyboard = {
            "box": kbd_grid,
            "process": p,
            "socket": keyboard
        }
        return

    def remove_keyboard(self, entry=None, event=None, box=None):
        if self.keyboard is None:
            return
        if box is None:
            box = self.base_panel.content
        if 'process' in self.keyboard:
            os.kill(self.keyboard['process'].pid, SIGTERM)
        box.remove(self.keyboard['box'])
        self.keyboard = None
        if entry:
            entry.set_sensitive(False)  # Move the focus
            entry.set_sensitive(True)

    def _key_press_event(self, widget, event):
        keyval_name = Gdk.keyval_name(event.keyval)
        if keyval_name == "Escape":
            self._menu_go_back(home=True)
        elif keyval_name == "BackSpace" and len(self._cur_panels) > 1 and self.keyboard is None:
            self.base_panel.back()

    def update_size(self, *args):
        width, height = self.get_size()
        if width != self.width or height != self.height:
            logging.info(f"Size changed: {width}x{height}")
        self.width, self.height = width, height
        new_ratio = self.width / self.height
        new_mode = new_ratio < 1.0
        ratio_delta = abs(self.aspect_ratio - new_ratio)
        if ratio_delta > 0.1 and self.vertical_mode != new_mode:
            self.reload_panels()
            self.vertical_mode = new_mode
            self.aspect_ratio = new_ratio
            logging.info(f"Vertical mode: {self.vertical_mode}")


def main():
    parser = argparse.ArgumentParser(description="KlipperScreen - A GUI for Klipper")
    homedir = os.path.expanduser("~")

    parser.add_argument(
        "-c", "--configfile",
        default="", metavar='<configfile>',
        help="Location of KlipperScreen configuration file"
    )
    logdir = os.path.join(homedir, "printer_data", "logs")
    if not os.path.exists(logdir):
        logdir = "/tmp"
    parser.add_argument(
        "-l", "--logfile", default=os.path.join(logdir, "KlipperScreen.log"), metavar='<logfile>',
        help="Location of KlipperScreen logfile output"
    )
    parser.add_argument(
        "-m", "--monitor", default="0", metavar='<monitor>',
        help="Number of the monitor, that will show Klipperscreen (default: 0)"
    )
    args = parser.parse_args()

    functions.setup_logging(os.path.normpath(os.path.expanduser(args.logfile)))
    functions.patch_threading_excepthook()
    if not Gtk.init_check():
        logging.critical("Failed to initialize Gtk")
        raise RuntimeError
    try:
        win = KlipperScreen(args)
    except Exception as e:
        logging.exception(f"Failed to initialize window\n{e}\n\n{traceback.format_exc()}")
        raise RuntimeError from e
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        logging.exception(f"Fatal error in main loop:\n{ex}\n\n{traceback.format_exc()}")
        os._exit(1)
