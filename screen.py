#!/usr/bin/python

import argparse
import gi

import json
import importlib
import logging
import os
import re
import signal
import subprocess
import pathlib
import traceback  # noqa

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from jinja2 import Environment

from ks_includes import functions
from ks_includes.KlippyWebsocket import KlippyWebsocket
from ks_includes.KlippyRest import KlippyRest
from ks_includes.files import KlippyFiles
from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.printer import Printer

from ks_includes.config import KlipperScreenConfig
from panels.base_panel import BasePanel

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)
# This is here to avoid performance issues opening bed_mesh
import matplotlib.pyplot  # noqa

PRINTER_BASE_STATUS_OBJECTS = [
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
    'webhooks'
]

klipperscreendir = pathlib.Path(__file__).parent.resolve()

class KlipperScreen(Gtk.Window):
    """ Class for creating a screen for Klipper via HDMI """
    _cur_panels = []
    bed_temp_label = None
    connecting = False
    connecting_to_printer = None
    connected_printer = None
    currentPanel = None
    files = None
    filename = ""
    keyboard = None
    keyboard_height = 200
    last_update = {}
    load_panel = {}
    number_tools = 1
    panels = {}
    popup_message = None
    screensaver = None
    printer = None
    printer_select_callbacks = []
    printer_select_prepanel = None
    rtl_languages = ['he_il']
    subscriptions = []
    shutdown = True
    updating = False
    update_queue = []
    _ws = None

    def __init__(self, args, version):
        self.dpms_timeout = None
        self.version = version

        configfile = os.path.normpath(os.path.expanduser(args.configfile))

        self._config = KlipperScreenConfig(configfile, self)
        self.lang = self._config.get_lang()

        logging.debug("OS Language: %s" % os.getenv('LANG'))

        settings = Gtk.Settings.get_default()
        logging.info("Font settings: %s" % settings.get_property('gtk-font-name'))

        self.lang_ltr = True
        for lang in self.rtl_languages:
            if os.getenv('LANG').lower().startswith(lang):
                self.lang_ltr = False
                Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
                logging.debug("Enabling RTL mode")
                break

        _ = self.lang.gettext

        Gtk.Window.__init__(self)
        monitor = Gdk.Display.get_default().get_primary_monitor()
        self.width = self._config.get_main_config().getint("width", monitor.get_geometry().width)
        self.height = self._config.get_main_config().getint("height", monitor.get_geometry().height)
        self.set_default_size(self.width, self.height)
        self.set_resizable(False)
        if self.width < self.height:
            self.vertical_mode = True
        else:
            self.vertical_mode = False
        logging.info("Screen resolution: %sx%s" % (self.width, self.height))
        self.theme = self._config.get_main_config_option('theme')
        self.show_cursor = self._config.get_main_config().getboolean("show_cursor", fallback=False)
        self.gtk = KlippyGtk(self, self.width, self.height, self.theme, self.show_cursor,
                             self._config.get_main_config_option("font_size", "medium"))
        self.keyboard_height = self.gtk.get_keyboard_height()
        self.init_style()

        self.base_panel = BasePanel(self, "Base Panel", False)
        self.add(self.base_panel.get())
        self.show_all()
        self.base_panel.activate()

        self.printer_initializing(_("Initializing"))

        self.set_screenblanking_timeout(self._config.get_main_config_option('screen_blanking'))

        # Move mouse to 0,0
        os.system("/usr/bin/xdotool mousemove 0 0")
        self.change_cursor()
        self.initial_connection()

    def initial_connection(self):
        printers = self._config.get_printers()
        default_printer = self._config.get_main_config().get('default_printer')
        logging.debug("Default printer: %s" % default_printer)
        if [True for p in printers if default_printer in p]:
            self.connect_printer(default_printer)
        elif len(printers) == 1:
            pname = list(printers[0])[0]
            self.connect_printer(pname)
        else:
            self.show_panel("printer_select", "printer_select", "Printer Select", 2)

    def connect_printer_widget(self, widget, name):
        self.connect_printer(name)

    def connect_printer(self, name):
        _ = self.lang.gettext
        self.connecting_to_printer = name

        if self.connected_printer == name:
            if self.printer_select_prepanel is not None:
                self.show_panel(self.printer_select_prepanel, "", "", 2)
                self.printer_select_prepanel = None
            while len(self.printer_select_callbacks) > 0:
                i = self.printer_select_callbacks.pop(0)
                i()
            if self.printer.get_state() not in ["disconnected", "error", "startup", "shutdown"]:
                self.base_panel.show_heaters(True)
            self.base_panel.show_printer_select(True)
            self.base_panel.show_macro_shortcut(self._config.get_main_config_option('side_macro_shortcut'))
            return

        # Cleanup
        self.printer_select_callbacks = []
        self.printer_select_prepanel = None
        if self.files is not None:
            self.files.reset()
            self.files = None
        if self.printer is not None:
            self.printer.reset()
            self.printer = None

        for printer in self._config.get_printers():
            pname = list(printer)[0]

            if pname != name:
                continue
            data = printer[pname]
            break

        if self._ws is not None:
            self._ws.close()
        self.connecting = True

        logging.info("Connecting to printer: %s" % name)
        self.apiclient = KlippyRest(data["moonraker_host"], data["moonraker_port"], data["moonraker_api_key"])

        self.printer = Printer({
            "software_version": "Unknown"
        }, {
            'configfile': {
                'config': {}
            },
            'print_stats': {
                'state': 'disconnected'
            },
            'virtual_sdcard': {
                'is_active': False
            }
        }, self.state_execute)

        self._remove_all_panels()
        self.subscriptions = []
        for panel in list(self.panels):
            if panel not in ["printer_select", "splash_screen"]:
                del self.panels[panel]
        self.base_panel.show_printer_select(True)
        self.printer_initializing(_("Connecting to %s") % name)

        self.printer.set_callbacks({
            "disconnected": self.state_disconnected,
            "error": self.state_error,
            "paused": self.state_paused,
            "printing": self.state_printing,
            "ready": self.state_ready,
            "startup": self.state_startup,
            "shutdown": self.state_shutdown
        })

        self._ws = KlippyWebsocket(self,
                                   {
                                       "on_connect": self.init_printer,
                                       "on_message": self._websocket_callback,
                                       "on_close": self.printer_initializing
                                   },
                                   data["moonraker_host"],
                                   data["moonraker_port"]
                                   )

        powerdevs = self.apiclient.send_request("machine/device_power/devices")
        if powerdevs is not False:
            self.printer.configure_power_devices(powerdevs['result'])
            self.panels['splash_screen'].show_restart_buttons()

        self.files = KlippyFiles(self)
        self._ws.initial_connect()
        self.connecting = False

        self.connected_printer = name
        logging.debug("Connected to printer: %s" % name)

    def ws_subscribe(self):
        requested_updates = {
            "objects": {
                "bed_mesh": ["profile_name", "mesh_max", "mesh_min", "probed_matrix"],
                "configfile": ["config"],
                "display_status": ["progress", "message"],
                "fan": ["speed"],
                "gcode_move": ["extrude_factor", "gcode_position", "homing_origin", "speed_factor"],
                "idle_timeout": ["state"],
                "pause_resume": ["is_paused"],
                "print_stats": ["print_duration", "total_duration", "filament_used", "filename", "state", "message"],
                "toolhead": ["homed_axes", "estimated_print_time", "print_time", "position", "extruder",
                             "max_accel", "max_accel_to_decel", "max_velocity", "square_corner_velocity"],
                "virtual_sdcard": ["file_position", "is_active", "progress"],
                "webhooks": ["state", "state_message"]
            }
        }
        for extruder in self.printer.get_tools():
            requested_updates['objects'][extruder] = ["target", "temperature", "pressure_advance", "smooth_time"]
        for h in self.printer.get_heaters():
            requested_updates['objects'][h] = ["target", "temperature"]
        for f in self.printer.get_fans():
            requested_updates['objects'][f] = ["speed"]

        self._ws.klippy.object_subscription(requested_updates)

    def _load_panel(self, panel, *args):
        if panel not in self.load_panel:
            logging.debug("Loading panel: %s" % panel)
            panel_path = os.path.join(os.path.dirname(__file__), 'panels', "%s.py" % panel)
            logging.info("Panel path: %s" % panel_path)
            if not os.path.exists(panel_path):
                msg = f"Panel {panel} does not exist"
                logging.info(msg)
                raise Exception(msg)

            module = importlib.import_module("panels.%s" % panel)
            if not hasattr(module, "create_panel"):
                msg = f"Cannot locate create_panel function for {panel}"
                logging.info(msg)
                raise Exception(msg)
            self.load_panel[panel] = getattr(module, "create_panel")

        try:
            return self.load_panel[panel](*args)
        except Exception:
            msg = f"Unable to create panel {panel}"
            logging.exception(msg)
            raise Exception(msg)

    def show_panel(self, panel_name, type, title, remove=None, pop=True, **kwargs):
        if panel_name not in self.panels:
            try:
                self.panels[panel_name] = self._load_panel(type, self, title)

                if kwargs != {}:
                    self.panels[panel_name].initialize(panel_name, **kwargs)
                else:
                    self.panels[panel_name].initialize(panel_name)
            except Exception:
                if panel_name in self.panels:
                    del self.panels[panel_name]
                logging.exception("Unable to load panel %s" % type)
                self.show_error_modal("Unable to load panel %s" % type)
                return

            if hasattr(self.panels[panel_name], "process_update"):
                self.panels[panel_name].process_update("notify_status_update", self.printer.get_data())

        try:
            if remove == 2:
                self._remove_all_panels()
            elif remove == 1:
                self._remove_current_panel(pop)

            logging.debug("Attaching panel %s" % panel_name)
            self.base_panel.add_content(self.panels[panel_name])

            logging.debug("Showing back. count: %s" % len(self._cur_panels))
            if len(self._cur_panels) == 0:
                self.base_panel.show_back(False)
            else:
                self.base_panel.show_back(True)
            self.show_all()

            if hasattr(self.panels[panel_name], "process_update"):
                self.panels[panel_name].process_update("notify_status_update", self.printer.get_updates())
                self.add_subscription(panel_name)
            if hasattr(self.panels[panel_name], "activate"):
                self.panels[panel_name].activate()
                self.show_all()
        except Exception:
            logging.exception("Error attaching panel")

        self._cur_panels.append(panel_name)
        logging.debug("Current panel hierarchy: %s", str(self._cur_panels))

    def show_popup_message(self, message, level=2):
        if self.popup_message is not None:
            self.close_popup_message()

        box = Gtk.Box()
        box.get_style_context().add_class("message_popup")

        if level == 1:
            box.get_style_context().add_class("message_popup_echo")
        else:
            box.get_style_context().add_class("message_popup_error")

        box.set_size_request(self.width, self.gtk.get_header_size())
        label = Gtk.Label()
        if "must home axis first" in message.lower():
            message = "Must home all axis first."
        label.set_text(message)

        close = Gtk.Button.new_with_label("X")
        close.set_can_focus(False)
        close.props.relief = Gtk.ReliefStyle.NONE
        close.connect("clicked", self.close_popup_message)

        box.pack_start(label, True, True, 0)
        box.pack_end(close, False, False, 0)
        box.set_halign(Gtk.Align.CENTER)

        self.base_panel.get().put(box, 0, 0)

        self.show_all()
        self.popup_message = box

        GLib.timeout_add_seconds(10, self.close_popup_message)

        return False

    def close_popup_message(self, widget=None):
        if self.popup_message is None:
            return

        self.base_panel.get().remove(self.popup_message)
        self.popup_message = None
        self.show_all()

    def show_error_modal(self, err):
        _ = self.lang.gettext
        logging.exception("Showing error modal: %s", err)

        buttons = [
            {"name": _("Go Back"), "response": Gtk.ResponseType.CANCEL}
        ]

        label = Gtk.Label()
        label.set_markup(
            ("%s \n\n" % err) +
            _("Check /tmp/KlipperScreen.log for more information.\nPlease submit an issue on GitHub for help."))
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self.gtk.Dialog(self, buttons, label, self.error_modal_response)

    def error_modal_response(self, widget, response_id):
        widget.destroy()

    def restart_warning(self, value):
        _ = self.lang.gettext
        logging.debug("Showing restart warning because: %s" % value)

        buttons = [
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL},
            {"name": _("Restart"), "response": Gtk.ResponseType.OK}
        ]

        label = Gtk.Label()
        label.set_markup(_("To apply %s KlipperScreen needs to be restarted") % value)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self.gtk.Dialog(self, buttons, label, self.restart_ks)

    def restart_ks(self, widget, response_id):
        if response_id == Gtk.ResponseType.OK:
            logging.debug("Restarting")
            os.system("sudo systemctl restart %s" % self._config.get_main_config_option('service'))
        widget.destroy()

    def init_style(self):
        style_provider = Gtk.CssProvider()
        css = open(os.path.join(klipperscreendir, "styles", "base.css"))
        css_base_data = css.read()
        css.close()
        css = open(os.path.join(klipperscreendir, "styles", self.theme, "style.css"))
        css_data = css_base_data + css.read()
        css.close()

        f = open(os.path.join(klipperscreendir, "styles", "base.conf"))
        style_options = json.load(f)
        f.close()

        theme_style_conf = os.path.join(klipperscreendir, "styles", self.theme, "style.conf")
        if os.path.exists(theme_style_conf):
            try:
                f = open(theme_style_conf)
                style_options.update(json.load(f))
                f.close()
            except Exception:
                logging.error("Unable to parse custom template conf file.")

        self.gtk.color_list = style_options['graph_colors']

        for i in range(len(style_options['graph_colors']['extruder']['colors'])):
            num = "" if i == 0 else i
            css_data += "\n.graph_label_extruder%s {border-left-color: #%s}" % (
                num,
                style_options['graph_colors']['extruder']['colors'][i]
            )
        for i in range(len(style_options['graph_colors']['bed']['colors'])):
            css_data += "\n.graph_label_heater_bed%s {border-left-color: #%s}" % (
                "" if i+1 == 1 else i+1,
                style_options['graph_colors']['bed']['colors'][i]
            )
        for i in range(len(style_options['graph_colors']['fan']['colors'])):
            css_data += "\n.graph_label_fan_%s {border-left-color: #%s}" % (
                i+1,
                style_options['graph_colors']['fan']['colors'][i]
            )
        for i in range(len(style_options['graph_colors']['sensor']['colors'])):
            css_data += "\n.graph_label_sensor_%s {border-left-color: #%s}" % (
                i+1,
                style_options['graph_colors']['sensor']['colors'][i]
            )

        css_data = css_data.replace("KS_FONT_SIZE", str(self.gtk.get_font_size()))

        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css_data.encode())

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def is_keyboard_showing(self):
        if self.keyboard is None:
            return False
        return True

    def is_printing(self):
        return self.printer.get_state() == "printing"

    def is_updating(self):
        return self.updating

    def _go_to_submenu(self, widget, name):
        logging.info("#### Go to submenu " + str(name))
        # self._remove_current_panel(False)

        # Find current menu item
        if "main_panel" in self._cur_panels:
            menu = "__main"
        elif "splash_screen" in self._cur_panels:
            menu = "__splashscreen"
        else:
            menu = "__print"

        logging.info("#### Menu " + str(menu))
        disname = self._config.get_menu_name(menu, name)
        menuitems = self._config.get_menu_items(menu, name)
        if len(menuitems) == 0:
            logging.info("No items in menu, returning.")
            return

        self.show_panel(self._cur_panels[-1] + '_' + name, "menu", disname, 1, False, display_name=disname,
                        items=menuitems)

    def _remove_all_panels(self):
        while len(self._cur_panels) > 0:
            self._remove_current_panel(True, False)
        self.show_all()

    def _remove_current_panel(self, pop=True, show=True):
        if len(self._cur_panels) > 0:
            self.base_panel.remove(self.panels[self._cur_panels[-1]].get_content())
            if hasattr(self.panels[self._cur_panels[-1]], "deactivate"):
                self.panels[self._cur_panels[-1]].deactivate()
            self.remove_subscription(self._cur_panels[-1])
            if pop is True:
                self._cur_panels.pop()
                if len(self._cur_panels) > 0:
                    self.base_panel.add_content(self.panels[self._cur_panels[-1]])
                    self.base_panel.show_back(False if len(self._cur_panels) == 1 else True)
                    if hasattr(self.panels[self._cur_panels[-1]], "activate"):
                        self.panels[self._cur_panels[-1]].activate()
                    if hasattr(self.panels[self._cur_panels[-1]], "process_update"):
                        self.panels[self._cur_panels[-1]].process_update("notify_status_update",
                                                                         self.printer.get_updates())
                        self.add_subscription(self._cur_panels[-1])
                    if show is True:
                        self.show_all()

    def _menu_go_back(self, widget=None):
        logging.info("#### Menu go back")
        self.remove_keyboard()
        self.close_popup_message()
        self._remove_current_panel()

    def _menu_go_home(self):
        logging.info("#### Menu go home")
        self.remove_keyboard()
        self.close_popup_message()
        while len(self._cur_panels) > 1:
            self._remove_current_panel()

    def add_subscription(self, panel_name):
        for sub in self.subscriptions:
            if sub == panel_name:
                return

        self.subscriptions.append(panel_name)

    def remove_subscription(self, panel_name):
        for i in range(len(self.subscriptions)):
            if self.subscriptions[i] == panel_name:
                self.subscriptions.pop(i)
                return

    def show_screensaver(self):
        logging.debug("Showing Screensaver")
        if self.screensaver is not None:
            self.close_screensaver()

        close = Gtk.Button()
        close.connect("clicked", self.close_screensaver)

        box = Gtk.Box()
        box.set_size_request(self.width, self.height)
        box.pack_start(close, True, True, 0)
        box.set_halign(Gtk.Align.CENTER)
        box.get_style_context().add_class("screensaver")

        self.base_panel.get().put(box, 0, 0)
        self.show_all()
        self.screensaver = box

    def close_screensaver(self, widget=None):
        if self.screensaver is None:
            return False
        logging.debug("Closing Screensaver")
        self.base_panel.get().remove(self.screensaver)
        self.screensaver = None
        if self.use_dpms:
            self.wake_screen()
        self.show_all()
        return False

    def check_dpms_state(self):
        state = functions.get_DPMS_state()

        if state == functions.DPMS_State.Fail:
            logging.info("DPMS State FAIL: Stopping DPMS Check")
            os.system("xset -display :0 s %s" % self.blanking_time)
            return False
        elif state != functions.DPMS_State.On:
            if self.screensaver is None:
                self.show_screensaver()
        return True

    def wake_screen(self):
        # Wake the screen (it will go to standby as configured)
        if self._config.get_main_config_option('screen_blanking') != "off":
            logging.debug("Screen wake up")
            os.system("xset -display :0 dpms force on")
            self.close_screensaver()

    def set_dpms(self, use_dpms):
        self.use_dpms = use_dpms
        logging.info("DPMS set to: %s" % self.use_dpms)
        self.set_screenblanking_timeout(self._config.get_main_config_option('screen_blanking'))

    def set_screenblanking_timeout(self, time):
        # The 'blank' flag sets the preference to blank the video
        # rather than display a background pattern
        os.system("xset -display :0 s blank")
        self.use_dpms = self._config.get_main_config().getboolean("use_dpms", fallback=True)

        if time == "off":
            logging.debug("Screen blanking: %s" % time)
            if self.dpms_timeout is not None:
                GLib.source_remove(self.dpms_timeout)
                self.dpms_timeout = None
            os.system("xset -display :0 dpms 0 0 0")
            os.system("xset -display :0 s off")
            return

        self.blanking_time = abs(int(time))
        logging.debug("Changing screen blanking to: %d" % self.blanking_time)
        if self.use_dpms and functions.dpms_loaded is True:
            os.system("xset -display :0 +dpms")
            if functions.get_DPMS_state() == functions.DPMS_State.Fail:
                logging.info("DPMS State FAIL")
            else:
                logging.debug("Using DPMS")
                os.system("xset -display :0 s off")
                os.system("xset -display :0 dpms 0 %s 0" % self.blanking_time)
                if self.dpms_timeout is None:
                    self.dpms_timeout = GLib.timeout_add_seconds(1, self.check_dpms_state)
                return
        # Without dpms just blank the screen
        logging.debug("Not using DPMS")
        os.system("xset -display :0 dpms 0 0 0")
        os.system("xset -display :0 s %s" % self.blanking_time)

    def set_updating(self, updating=False):
        if self.updating is True and updating is False:
            if len(self.update_queue) > 0:
                i = self.update_queue.pop()
                self.update_queue = []
                i[0](i[1])

        self.updating = updating

    def show_printer_select(self, widget=None):
        logging.debug("Saving panel: %s" % self._cur_panels[0])
        self.printer_select_prepanel = self._cur_panels[0]
        self.base_panel.show_heaters(False)
        self.base_panel.show_macro_shortcut(False)
        self.base_panel.show_printer_select(False)
        self.show_panel("printer_select", "printer_select", "Printer Select", 2)
        self.show_all()

    def state_execute(self, callback, prev_state):
        if self.is_updating():
            self.update_queue.append([callback, prev_state])
        else:
            callback(prev_state)

    def state_disconnected(self, prev_state):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_disconnected]
            return

        _ = self.lang.gettext
        logging.debug("### Going to disconnected")
        self.base_panel.show_macro_shortcut(False)
        self.wake_screen()
        self.printer_initializing(_("Klipper has disconnected"))
        if self.connected_printer is not None:
            self.connected_printer = None
            # Try to reconnect
            self.connect_printer(self.connecting_to_printer)
        else:
            self.initial_connection()

    def state_error(self, prev_state):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_error]
            return

        _ = self.lang.gettext
        self.base_panel.show_macro_shortcut(False)
        self.wake_screen()
        msg = self.printer.get_stat("webhooks", "state_message")
        if "FIRMWARE_RESTART" in msg:
            self.printer_initializing("<b>" + _("Klipper has encountered an error.") + "\n" +
                                      _("A FIRMWARE_RESTART may fix the issue.") +
                                      "</b>" + "\n\n" + msg)
        elif "micro-controller" in msg:
            self.printer_initializing("<b>" + _("Klipper has encountered an error.") +
                                      _("Please recompile and flash the micro-controller.") +
                                      "</b>" + "\n\n" + msg)
        else:
            self.printer_initializing("<b>" + _("Klipper has encountered an error.") +
                                      "</b>" + "\n\n" + msg)

        for panel in list(self.panels):
            if panel not in ["printer_select", "splash_screen"]:
                del self.panels[panel]

    def state_paused(self, prev_state):
        if "job_status" not in self._cur_panels:
            self.printer_printing()

    def state_printing(self, prev_state):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_printing]
            return

        if "job_status" not in self._cur_panels:
            self.printer_printing()
        else:
            self.panels["job_status"].new_print()

    def state_ready(self, prev_state):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_ready]
            return

        # Do not return to main menu if completing a job, timeouts/user input will return
        if "job_status" in self._cur_panels or "main_menu" in self._cur_panels:
            return

        self.base_panel.show_macro_shortcut(self._config.get_main_config_option('side_macro_shortcut'))
        if prev_state not in ['paused', 'printing']:
            self.init_printer()
            self.base_panel._printer = self.printer
            self.base_panel.show_heaters()

        self.printer_ready()

    def state_startup(self, prev_state):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_startup]
            return

        _ = self.lang.gettext
        self.printer_initializing(_("Klipper is attempting to start"))

    def state_shutdown(self, prev_state):
        if "printer_select" in self._cur_panels:
            self.printer_select_callbacks = [self.state_shutdown]
            return

        _ = self.lang.gettext
        self.base_panel.show_macro_shortcut(False)
        self.wake_screen()
        msg = self.printer.get_stat("webhooks", "state_message")
        self.printer_initializing("<b>" + _("Klipper has shutdown") +
                                  "</b>" + "\n\n" + msg)

    def toggle_macro_shortcut(self, value):
        if value is True:
            self.base_panel.show_macro_shortcut(True, True)
        else:
            self.base_panel.show_macro_shortcut(False, True)

    def _websocket_callback(self, action, data):
        _ = self.lang.gettext

        if self.connecting is True:
            return

        if action == "notify_klippy_disconnected":
            logging.debug("Received notify_klippy_disconnected")
            self.printer.change_state("disconnected")
            return
        elif action == "notify_klippy_ready":
            self.printer.change_state("ready")
        elif action == "notify_status_update" and self.printer.get_state() != "shutdown":
            self.printer.process_update(data)
        elif action == "notify_filelist_changed":
            logging.debug("Filelist changed: %s", json.dumps(data, indent=2))
            if self.files is not None:
                self.files.process_update(data)
        elif action == "notify_metadata_update":
            self.files.request_metadata(data['filename'])
        elif action == "notify_update_response":
            logging.info("%s: %s" % (action, data))
        elif action == "notify_power_changed":
            logging.debug("Power status changed: %s", data)
            self.printer.process_power_update(data)
        elif self.printer.get_state() not in ["error", "shutdown"] and action == "notify_gcode_response":
            if "Klipper state: Shutdown" in data:
                logging.debug("Shutdown in gcode response, changing state to shutdown")
                self.printer.change_state("shutdown")

            if not (data.startswith("B:") and
                    re.search(r'B:[0-9\.]+\s/[0-9\.]+\sT[0-9]+:[0-9\.]+', data)):
                if data.startswith("echo: "):
                    self.show_popup_message(data[6:], 1)
                if data.startswith("!! "):
                    self.show_popup_message(data[3:], 2)
                logging.debug(json.dumps([action, data], indent=2))

        self.base_panel.process_update(action, data)
        if self._cur_panels[-1] in self.subscriptions:
            self.panels[self._cur_panels[-1]].process_update(action, data)

    def _confirm_send_action(self, widget, text, method, params={}):
        _ = self.lang.gettext

        buttons = [
            {"name": _("Continue"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(text)
            text = j2_temp.render()
        except Exception:
            logging.debug("Error parsing jinja for confirm_send_action")

        label = Gtk.Label()
        label.set_markup(text)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self.gtk.Dialog(self, buttons, label, self._confirm_send_action_response, method, params)

    def _confirm_send_action_response(self, widget, response_id, method, params):
        if response_id == Gtk.ResponseType.OK:
            self._send_action(widget, method, params)

        widget.destroy()

    def _send_action(self, widget, method, params):
        self._ws.send_method(method, params)

    def printer_initializing(self, text=None, disconnect=False):
        self.shutdown = True
        self.close_popup_message()
        self.show_panel('splash_screen', "splash_screen", "Splash Screen", 2)
        if disconnect is True and self.printer is not None:
            self.printer.state = "disconnected"
        if text is not None:
            self.panels['splash_screen'].update_text(text)
            self.panels['splash_screen'].show_restart_buttons()

    def init_printer(self):
        _ = self.lang.gettext

        printer_info = self.apiclient.get_printer_info()
        if printer_info is False:
            logging.info("Unable to get printer info from moonraker")
            return False
        data = self.apiclient.send_request("printer/objects/query?" + "&".join(PRINTER_BASE_STATUS_OBJECTS))
        if data is False:
            logging.info("Error getting printer object data")
            return False
        powerdevs = self.apiclient.send_request("machine/device_power/devices")
        data = data['result']['status']

        config = self.apiclient.send_request("printer/objects/query?configfile")
        if config is False:
            logging.info("Error getting printer config data")
            return False

        # Reinitialize printer, in case the printer was shut down and anything has changed.
        self.printer.reinit(printer_info['result'], config['result']['status'])

        self.ws_subscribe()
        extra_items = []
        for extruder in self.printer.get_tools():
            extra_items.append(extruder)
        for h in self.printer.get_heaters():
            extra_items.append(h)
        for f in self.printer.get_fans():
            extra_items.append(f)

        data = self.apiclient.send_request("printer/objects/query?" + "&".join(PRINTER_BASE_STATUS_OBJECTS +
                                           extra_items))
        if data is False:
            logging.info("Error getting printer object data")
            return False

        tempstore = self.apiclient.send_request("server/temperature_store")
        if tempstore is not False:
            self.printer.init_temp_store(tempstore['result'])
        self.printer.process_update(data['result']['status'])

        self.files.initialize()
        self.files.refresh_files()

        if powerdevs is not False:
            self.printer.configure_power_devices(powerdevs['result'])
            self.panels['splash_screen'].show_restart_buttons()

    def printer_ready(self):
        _ = self.lang.gettext
        self.close_popup_message()
        # Force update to printer webhooks state in case the update is missed due to websocket subscribe not yet sent
        self.printer.process_update({"webhooks": {"state": "ready", "state_message": "Printer is ready"}})
        self.show_panel('main_panel', "main_menu", _("Home"), 2,
                        items=self._config.get_menu_items("__main"), extrudercount=self.printer.get_extruder_count())
        self.ws_subscribe()
        if "job_status" in self.panels:
            self.remove_subscription("job_status")
            del self.panels["job_status"]

    def printer_printing(self):
        self.close_popup_message()
        self.show_panel('job_status', "job_status", "Print Status", 2)

    def show_keyboard(self, widget=None):
        if self.keyboard is not None:
            return

        env = os.environ.copy()
        usrkbd = "/home/pi/.matchbox/keyboard.xml"
        if os.path.isfile(usrkbd):
            env["MB_KBD_CONFIG"] = usrkbd
        else:
            env["MB_KBD_CONFIG"] = "ks_includes/locales/keyboard.xml"
        p = subprocess.Popen(["matchbox-keyboard", "--xid"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=env)

        xid = int(p.stdout.readline())
        logging.debug("XID %s" % xid)
        logging.debug("PID %s" % p.pid)
        keyboard = Gtk.Socket()

        action_bar_width = self.gtk.get_action_bar_width()

        box = Gtk.VBox()
        box.set_vexpand(False)
        box.set_size_request(self.width - action_bar_width, self.keyboard_height)
        box.add(keyboard)

        self.base_panel.get_content().pack_end(box, False, 0, 0)

        self.show_all()
        keyboard.add_id(xid)
        keyboard.show()

        self.keyboard = {
            "box": box,
            # "panel": cur_panel.get(),
            "process": p,
            "socket": keyboard
        }

    def remove_keyboard(self, widget=None):
        if self.keyboard is None:
            return

        self.base_panel.get_content().remove(self.keyboard['box'])
        os.kill(self.keyboard['process'].pid, signal.SIGTERM)
        self.keyboard = None

    def change_cursor(self, cursortype=None):
        if cursortype == "watch":
            os.system("xsetroot  -cursor_name  watch")
        elif self.show_cursor:
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.ARROW))
            os.system("xsetroot  -cursor_name  arrow")
        else:
            self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.BLANK_CURSOR))
            os.system("xsetroot  -cursor ks_includes/emptyCursor.xbm ks_includes/emptyCursor.xbm")
        return

def main():

    version = functions.get_software_version()
    parser = argparse.ArgumentParser(description="KlipperScreen - A GUI for Klipper")
    parser.add_argument(
        "-c", "--configfile", default="~/KlipperScreen.conf", metavar='<configfile>',
        help="Location of KlipperScreen configuration file"
    )
    parser.add_argument(
        "-l", "--logfile", default="/tmp/KlipperScreen.log", metavar='<logfile>',
        help="Location of KlipperScreen logfile output"
    )
    args = parser.parse_args()

    functions.setup_logging(
        os.path.normpath(os.path.expanduser(args.logfile)),
        version
    )

    functions.patch_threading_excepthook()

    logging.info("KlipperScreen version: %s" % version)


    win = KlipperScreen(args, version)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Fatal error in main loop")
