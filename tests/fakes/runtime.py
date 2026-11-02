"""In-memory fakes that mirror the real KlipperScreen runtime data shapes.

These are deliberately *thin*: they do not stub behavior, they reproduce the
exact data structures the real objects expose, populated from a representative
printer.  The panel code under test then runs the real construction path against
reality-equivalent input.

Representative printer (per user spec): single extruder + heater_bed + chamber
heater, nothing else.  The ``data``/``config`` dicts are the same structures Klippy/Moonraker
push through ``Printer.reinit(printer_info, data)``.
"""

import configparser
import json
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# KlipperScreen config (the app config, i.e. KlipperScreen.conf)
# ---------------------------------------------------------------------------


def build_config(width=800, height=480, font_size="medium", theme="material-dark"):
    """Return a representative KlipperScreen.conf as text."""
    return f"""
[main]
width = {width}
height = {height}
font_size = {font_size}
theme = {theme}
show_heater_power = False
24htime = True
keyboard_navigation = False
side_shortcut_target = notifications
print_sort_dir = name_asc
print_view = thumbs

[spoolman]
host = 127.0.0.1
port = 7282
hide_archived = True

[preheat PLA]
bed = 60.0
extruder = 195.0
gcode = M140 S{int(60)}

[preheat ABS]
bed = 90.0
extruder = 220.0
gcode = M140 S{int(90)}

[preheat PETG]
bed = 80.0
extruder = 240.0
gcode = M140 S{int(80)}
"""


class FakeConfig:
    """Wraps a real ``configparser`` -- same interface the panels call."""

    def __init__(
        self,
        config_text=None,
        *,
        width=800,
        height=480,
        font_size="medium",
        theme="material-dark",
        lang=None,
    ):
        self._parser = configparser.ConfigParser()
        self._parser.read_string(
            config_text
            if config_text is not None
            else build_config(width, height, font_size, theme)
        )
        self.lang = lang
        self.errors = []
        self.printers = ["main"]
        self.lang_list = [
            "ar",
            "bg",
            "cs",
            "da",
            "de",
            "de_formal",
            "en",
            "es",
            "et",
            "fa",
            "fr",
            "he",
            "hr",
            "hu",
            "it",
            "jp",
            "ko",
            "lt",
            "nl",
            "pl",
            "pt",
            "pt_BR",
            "rs",
            "ru",
            "sk",
            "sl",
            "sv",
            "tr",
            "uk",
            "vi",
            "zh_CN",
            "zh_TW",
        ]

    def get_printer_config(self, printer):
        # Real config.get_printer_config() reads the printer-specific Klipper
        # config section.  The single-extruder fake has no separate printer
        # config file, so return None -> BasePanel falls back to its defaults
        # (no hidden sensors, no titlebar items, spoolman low limit 20).
        return None

    def get_main_config(self):
        return self._parser["main"]

    def get_config(self):
        return self._parser

    def get_lang(self):
        return self.lang

    def get_printers(self):
        return self.printers

    def get_configurable_options(self):
        # Mirrors KlipperScreenConfig.get_configurable_options(): a list of
        # single-key option dicts.  Empty is valid -- settings then shows only
        # the language and printer menus.
        return []

    def get_language_name(self, lang):
        names = {
            "ar": "العربية",
            "bg": "Български",
            "cs": "Čeština",
            "da": "Dansk",
            "de": "Deutsch",
            "de_formal": "Deutsch (höflich)",
            "en": "English",
            "es": "Español",
            "et": "Eesti",
            "fa": "فارسی",
            "fr": "Français",
            "he": "עברית",
            "hr": "Hrvatski",
            "hu": "Magyar",
            "it": "Italiano",
            "jp": "日本語",
            "ko": "한국어",
            "lt": "Lietuvių",
            "nl": "Nederlands",
            "pl": "Polski",
            "pt": "Português",
            "pt_BR": "Português (Brasil)",
            "rs": "Srpski",
            "ru": "Русский",
            "sk": "Slovenčina",
            "sl": "Slovenščina",
            "sv": "Svenska",
            "tr": "Türkçe",
            "uk": "Українська",
            "vi": "Tiếng Việt",
            "zh_CN": "简体中文",
            "zh_TW": "繁體中文",
        }
        return names.get(lang, lang)

    def get_menu_name(self, menu="__main", subsection=""):
        return False

    def get_menu_items(self, menu="__main", subsection=""):
        return []

    def get_preheat_options(self):
        # Mirrors KlipperScreenConfig._build_preheat_item exactly.
        result = {}
        for section in self._parser.sections():
            if section.startswith("preheat "):
                name = section[len("preheat ") :]
                cfg = self._parser[section]
                result[name] = {
                    opt: cfg.get("gcode", None) if opt == "gcode" else cfg.getfloat(opt, None)
                    for opt in cfg
                }
        return result

    def set(self, section, name, value):
        if not self._parser.has_section(section):
            self._parser.add_section(section)
        self._parser.set(section, name, value)

    def save_user_config_options(self):
        pass


# ---------------------------------------------------------------------------
# Printer state (Klipper/Moonraker status) -- same dicts as Printer.reinit
# ---------------------------------------------------------------------------


def build_printer(state="idle"):
    """Return (config, data) dicts for extruder + heater_bed + chamber printer."""
    config = {
        "printer": {
            "max_accel": "3000",
            "max_velocity": "500",
            "square_corner_velocity": "5.0",
            "kinematics": "cartesian",
        },
        "extruder": {
            "max_temp": "260",
            "sensor_type": "PT1000",
            "acceleration": "3000",
            "max_accel": "3000",
            "max_velocity": "20",
            "filament_diameter": "1.75",
            "pressure_advance": "0.05",
            "smooth_time": "1.0",
            "min_extrude_temp": "170",
        },
        "heater_bed": {"max_temp": "120", "sensor_type": "PT1000"},
        "heater_generic chamber": {"max_temp": "60", "sensor_type": "PT1000"},
        "fan": {"max_power": "1.0", "off_below": "0.0"},
        "output_pin extruder_led": {"pin": "PC0"},
        "led extruder": {"pin": "PC1", "color_order": "RGBW"},
        # Bed-leveling the bed_level panel renders.  Faithful to the real Klipper
        # [screws_tilt_adjust] shape (see docs/extra/klipper/Manual_Level.md):
        # screw *values* are "x, y" (which the panel's _get_screws regex consumes),
        # while screwN_name / screw_thread are separate keys the regex ignores.  A
        # 3x3 grid exercises the full layout the panel supports.
        "screws_tilt_adjust": {
            "screw1": "25.0, 215.0",
            "screw1_name": "rear left",
            "screw2": "120.0, 215.0",
            "screw2_name": "rear center",
            "screw3": "215.0, 215.0",
            "screw3_name": "rear right",
            "screw4": "25.0, 120.0",
            "screw4_name": "center left",
            "screw5": "120.0, 120.0",
            "screw5_name": "center",
            "screw6": "215.0, 120.0",
            "screw6_name": "center right",
            "screw7": "25.0, 25.0",
            "screw7_name": "front left",
            "screw8": "120.0, 25.0",
            "screw8_name": "front center",
            "screw9": "215.0, 25.0",
            "screw9_name": "front right",
            "horizontal_move_z": "10.0",
            "speed": "50.0",
            "screw_thread": "CW-M3",
        },
        "probe": {"x_offset": "-40.0", "y_offset": "-20.0", "z_offset": "-0.5"},
    }
    data = {
        "extruder0": {"temperature": 23.5, "target": 0},
        "extruder": {"temperature": 23.5, "target": 0},
        "heater_bed": {"temperature": 22.0, "target": 0},
        "heater_generic chamber": {"temperature": 24.0, "target": 0},
        "fan": {"speed": 0},
        "toolhead": {"extruder": "extruder", "homed_axes": "xyz"},
        "gcode_move": {"absolute_coordinates": True, "homing_origin": [0, 0, 0, 0]},
        "virtual_sdcard": {"progress": 100, "file_position": 0.0},
        "exclude_object": {"objects": [], "excluded_objects": []},
        "manual_probe": {"is_active": False},
        "webhooks": {"state": "ready"},
        "print_stats": {"state": "standby", "filament_used": 0},
        "idle_timeout": {"state": "ready"},
    }
    return config, data


class FakePrinter:
    """Reproduces the real ``Printer`` query methods from config/data dicts."""

    def __init__(self, config=None, data=None, *, state="idle"):
        self.config = dict(config) if config is not None else {}
        self.data = {k: dict(v) for k, v in (data or {}).items()}
        self.state = state
        self.extrudercount = 0
        self.tools = []
        self.temp_devices = None
        self.active_spool = None
        self.spoolman = False
        # Time-series store the HeaterGraph draws from.  Mirrors Printer.
        self.tempstore = {}
        self.tempstore_size = 1200
        # Mirror the other real-Printer attributes panels read directly.
        self.available_commands = {
            "G28",
            "Z_TILT_ADJUST",
            "QUAD_GANTRY_LEVEL",
            "BED_MESH_CALIBRATE",
            "BED_MESH_CLEAR",
            "QUERY_PROBE",
            "Z_OFFSET_APPLY_PROBE",
            "SAVE_CONFIG",
            "TESTZ",
            "ACCEPT",
            "T1",
        }
        self.system_info = {
            "available_services": {"klipper": {}, "moonraker": {}},
            "distribution": {"name": "Debian", "id": "debian"},
            "software_version": "v1.1.0+dfsg1",
        }
        self.cameras = []
        self.sensors = None
        self.active_spool_id = None
        self._build()

    def _build(self):
        # Mirror Printer.reinit's tool/device enumeration.
        self.tools = []
        self.extrudercount = 0
        for x in self.config.keys():
            section, _, name = x.partition(" ")
            if name.startswith("_"):
                continue
            if section.startswith("extruder"):
                self.tools.append(x)
                self.extrudercount += 1
                if name.startswith("extruder_stepper"):
                    continue
                self.data[x] = {"temperature": 0, "target": 0}
            elif section in (
                "heater_bed",
                "heater_generic",
                "temperature_sensor",
                "temperature_fan",
            ):
                self.data[x] = {"temperature": 0}
                if section != "temperature_sensor":
                    self.data[x]["target"] = 0
        self.tools = sorted(self.tools)

    # --- device queries used by panels ---
    def get_temp_devices(self):
        if self.temp_devices is None:
            devices = [d for d in self.tools if not d.startswith("extruder_stepper")]
            self.temp_devices = (
                devices + self.get_heaters() + self.get_temp_sensors() + self.get_temp_fans()
            )
        return self.temp_devices

    def get_temp_store_devices(self):
        return list(self.tempstore)

    def get_temp_store(self, device, section=False, results=0):
        if device not in self.tempstore:
            return False
        if section is not False:
            if section not in self.tempstore[device]:
                return False
            if results == 0 or results >= len(self.tempstore[device][section]):
                return self.tempstore[device][section]
            return self.tempstore[device][section][-results:]
        temp = {}
        for section in self.tempstore[device]:
            if results == 0 or results >= len(self.tempstore[device][section]):
                temp[section] = self.tempstore[device][section]
            else:
                temp[section] = self.tempstore[device][section][-results:]
        return temp

    def get_tempstore_size(self):
        return self.tempstore_size

    def get_heaters(self):
        heaters = self.get_config_section_list("heater_generic ")
        if "heater_bed" in self.config:
            heaters.insert(0, "heater_bed")
        return heaters

    def get_temp_sensors(self):
        return self.get_config_section_list("temperature_sensor")

    def get_temp_fans(self):
        return self.get_config_section_list("temperature_fan")

    def get_config_section(self, section):
        return self.config.get(section, {})

    def get_config_section_list(self, search=""):
        return [s for s in self.config if s.startswith(search)]

    def device_has_target(self, device):
        return device in self.data and "target" in self.data[device]

    def device_has_power(self, device):
        return device in self.data and "power" in self.data[device]

    def get_stat(self, stat, substat=None):
        if substat is None:
            return self.data.get(stat, {})
        return self.data.get(stat, {}).get(substat, {})

    def set_stat(self, stat, d):
        self.data.setdefault(stat, {}).update(d)

    def get_heater_tool_number(self, tool):
        heated = [t for t in self.tools if not t.startswith("extruder_stepper")]
        if len(heated) == 1:
            return None
        return heated.index(tool)

    def get_power_devices(self):
        return []

    def get_power_device_status(self, device):
        return "off"

    def get_macro(self, macro):
        return next(
            (self.config[key] for key in self.config.keys() if key.find(macro) > -1),
            False,
        )

    def get_fans(self):
        fans = []
        if self.config_section_exists("fan"):
            fans.append("fan")
        for fan_type in ["controller_fan", "fan_generic", "heater_fan"]:
            fans.extend(iter(self.get_config_section_list(f"{fan_type} ")))
        return fans

    def get_pwm_tools(self):
        return self.get_config_section_list("pwm_tool ")

    def get_output_pins(self):
        return self.get_config_section_list("output_pin ")

    def get_gcode_macros(self):
        macros = []
        for macro in self.get_config_section_list("gcode_macro "):
            macro = macro[12:].strip()
            if macro.startswith("_") or macro.upper() in ("LOAD_FILAMENT", "UNLOAD_FILAMENT"):
                continue
            if self.get_macro(macro) and "rename_existing" in self.get_macro(macro):
                continue
            macros.append(macro)
        return macros

    def get_filament_sensors(self):
        if self.sensors is None:
            self.sensors = list(self.get_config_section_list("filament_switch_sensor "))
            self.sensors.extend(iter(self.get_config_section_list("filament_motion_sensor ")))
        return self.sensors

    def get_probe(self):
        probe_types = ["probe", "bltouch", "smart_effector", "probe_eddy_current"]
        for probe_type in probe_types:
            if self.config_section_exists(probe_type):
                return self.get_config_section(probe_type)
        return None

    def get_leds(self):
        return [
            led
            for led_type in ["dotstar", "led", "neopixel", "pca9533", "pca9632"]
            for led in self.get_config_section_list(f"{led_type} ")
            if not led.split()[1].startswith("_")
        ]

    def get_led_color_order(self, led):
        if led not in self.config or led not in self.data:
            return None
        elif "color_order" in self.config[led]:
            return self.config[led]["color_order"]
        colors = ""
        for option in self.config[led]:
            if option in ("red_pin", "initial_red") and "R" not in colors:
                colors += "R"
            elif option in ("green_pin", "initial_green") and "G" not in colors:
                colors += "G"
            elif option in ("blue_pin", "initial_blue") and "B" not in colors:
                colors += "B"
            elif option in ("white_pin", "initial_white") and "W" not in colors:
                colors += "W"
        return colors

    def get_fan_speed(self, fan="fan"):
        speed = 0
        if fan not in self.config or fan not in self.data:
            return speed
        if "speed" in self.data[fan]:
            speed = self.data[fan]["speed"]
        if "max_power" in self.config[fan]:
            max_power = float(self.config[fan]["max_power"])
            if max_power > 0:
                speed = speed / max_power
        if "off_below" in self.config[fan]:
            off_below = float(self.config[fan]["off_below"])
            if speed < off_below:
                speed = 0
        return speed

    def get_pin_value(self, pin):
        if pin in self.data:
            return self.data[pin]["value"]
        elif pin in self.config and "value" in self.config[pin]:
            return self.config[pin]["value"]
        return 0

    def get_tools(self):
        return self.tools

    def get_tool_number(self, tool):
        return self.tools.index(tool)

    def config_section_exists(self, section):
        return section in self.config or section + " " in self.config


# ---------------------------------------------------------------------------
# Screen -- wires the above together with the *real* KlippyGtk.
# ---------------------------------------------------------------------------


class _ResetTimeout:
    """KlippyGtk.Button and HeaterGraph connect clicked/press events to
    ``screensaver.reset_timeout`` / ``lock_screen.reset_timeout``; provide a
    no-op that mirrors the real methods."""

    def reset_timeout(self, *args, **kwargs):
        return True

    def close(self, *args, **kwargs):
        return True

    def lock(self, *args, **kwargs):
        return True


class _FakeWs:
    """Interaction-only; construction never touches it. Present so attribute
    access does not surprise later milestones."""

    class _Api:
        def __getattr__(self, name):
            def _(*a, **k):
                return None

            return _

    api = _Api()

    def send_method(self, *args, **kwargs):
        return None


class _FakeFiles:
    def has_thumbnail(self, filename):
        return False

    def get_thumbnail_location(self, filename, small=False):
        return None

    def add_callback(self, callback):
        return None

    def remove_callback(self, callback):
        return None

    def get_file_info(self, filename):
        return {}

    def request_metadata(self, filename):
        return None

    def file_metadata_exists(self, filename):
        return False


class _FakeSpoolmanAPI:
    """Mirror of SpoolmanAPI's surface used by the spoolman/spool_editor panels.
    Construction is the only path exercised here."""

    def load_all_spools(self, allow_archived=False, callback=None):
        return []

    def clear_active_spool(self, callback):
        return None

    def set_active_spool_id(self, spool_id, callback):
        return None


class _FakeNotificationHandler:
    def handle(self, action, data):
        return None


class FakeState:
    def __init__(self):
        self.printer_name = "main"
        self.printer_is_local = True
        self.connected = True
        self.connecting = False
        self.updating = False
        self.initialized = True
        self.notification_log = []


class FakeScreen:
    def __init__(
        self,
        width=800,
        height=480,
        font_size="medium",
        theme="material-dark",
        config=None,
        printer=None,
    ):
        self.width = width
        self.height = height
        self.aspect_ratio = self.width / self.height
        self.vertical_mode = self.aspect_ratio < 1.0
        self.theme = theme
        self.windowed = False
        self.state = FakeState()
        self._cur_panels = []
        self.panels = {}
        self._config = config or FakeConfig(
            width=width, height=height, font_size=font_size, theme=theme
        )
        self.printer = printer or FakePrinter(*build_printer())
        self.files = _FakeFiles()
        self.screensaver = _ResetTimeout()
        self.lock_screen = _ResetTimeout()
        self._ws = _FakeWs()
        # Production attributes panels read directly at construction time.
        self.wayland = True
        self.panels_reinit = []
        self.moonraker_endpoint = "http://127.0.0.1:7125"
        self.base_panel = None
        self.spoolman_api = _FakeSpoolmanAPI()
        self._notification_handler = _FakeNotificationHandler()

        # base_panel normally establishes this class attribute before panels
        # build; replicate its "no printer config" default so bare panels work.
        from ks_includes.screen_panel import ScreenPanel

        ScreenPanel.hidden_sensors = []

        # Real widget toolkit -- this is what actually builds the UI.
        from ks_includes.KlippyGtk import KlippyGtk

        self.gtk = KlippyGtk(self)

        # Production sets gtk.color_list from styles/base.conf graph_colors.
        # Without it, get_temp_color() returns (False, False) and the
        # HeaterGraph crashes when it draws.  Mirror it so the graph renders.
        with open(os.path.join(_REPO_ROOT, "styles", "base.conf")) as _cf:
            self.gtk.color_list = json.load(_cf).get("graph_colors", {})

        # Style/theme state.  These stay empty until the preview tool calls
        # load_base_styles() + change_theme() (see below); the base color_list
        # above is enough for panel construction, and tests that don't preview
        # never install a style provider so their layout is unchanged.
        self.style_options = {}
        self.base_css = ""
        from gi.repository import Gtk

        self.style_provider = Gtk.CssProvider()

    # --- theme / style: mirrors Screen.load_base_styles + change_theme so the
    # preview tool renders the panel with the real theme CSS instead of bare
    # Adwaita.  Not called from __init__ on purpose: installing a style provider
    # would change every existing test's layout, and only the preview tool needs
    # the theme applied. ---
    def load_base_styles(self):
        import pathlib

        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk

        base_conf_path = os.path.join(_REPO_ROOT, "styles", "base.conf")
        with open(base_conf_path) as _f:
            self.style_options = json.load(_f)
        self.gtk.color_list = self.style_options["graph_colors"]
        base_css_path = os.path.join(_REPO_ROOT, "styles", "base.css")
        self.base_css = pathlib.Path(base_css_path).read_text()
        self.base_css = self.base_css.replace("KS_FONT_SIZE", f"{self.gtk.font_size}")
        self.base_css = self.customize_graph_colors(self.base_css)
        self.style_provider.load_from_data(self.base_css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self.style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def load_custom_theme(self, theme_name):
        import pathlib

        theme_dir = os.path.join(_REPO_ROOT, "styles", theme_name)
        theme_css_path = os.path.join(theme_dir, "style.css")
        theme_conf_path = os.path.join(theme_dir, "style.conf")

        theme_css = ""
        theme_options = {}

        if os.path.exists(theme_css_path):
            theme_css = pathlib.Path(theme_css_path).read_text()
        if os.path.exists(theme_conf_path):
            with open(theme_conf_path) as _f:
                theme_options = json.load(_f)
        return theme_css, theme_options

    def customize_graph_colors(self, css_data):
        for category, category_data in self.style_options["graph_colors"].items():
            for i, color in enumerate(category_data["colors"], start=0):
                if category == "extruder":
                    class_name = (
                        f".graph_label_{category}{i}" if i > 0 else f".graph_label_{category}"
                    )
                elif category == "bed":
                    class_name = f".graph_label_heater_{category}"
                else:
                    class_name = f".graph_label_{category}_{i + 1}"
                css_data += f"\n{class_name} {{ border-left-color: #{color} }}"
        return css_data

    def update_style_provider(self, theme_css):
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk

        css_data = self.base_css + self.customize_graph_colors(theme_css)
        screen = Gdk.Screen.get_default()
        if self.style_provider:
            Gtk.StyleContext.remove_provider_for_screen(screen, self.style_provider)
        self.style_provider = Gtk.CssProvider()
        self.style_provider.load_from_data(css_data.encode())
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            self.style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def change_theme(self, theme_name=None):
        if not theme_name:
            theme_name = self._config.get_main_config().get("theme")
        self.gtk.update_themedir(theme_name)
        theme_css, theme_options = self.load_custom_theme(theme_name)
        self.style_options.update(theme_options)
        self.gtk.color_list = self.style_options["graph_colors"]
        self.update_style_provider(theme_css)
        self.reload_icon_theme()

    def reload_icon_theme(self):
        self.panels_reinit = list(self.panels)
        if self.base_panel is not None:
            self.base_panel.reload_icons()

    # --- used by panels; provided for completeness ---
    def show_popup_message(self, *args, **kwargs):
        return None

    # --- referenced by BasePanel via connect() (only invoked on user action,
    # but the attribute must exist at construction time) ---
    def _menu_go_back(self, *args, **kwargs):
        return False

    def show_printer_select(self, *args, **kwargs):
        return None

    def remove_keyboard(self, *args, **kwargs):
        return None

    # --- referenced by BasePanel methods during/after construction ---
    def log_notification(self, *args, **kwargs):
        return None

    # --- referenced by panels during/after construction ---
    def show_keyboard(self, *args, **kwargs):
        return None

    def close_connection(self, *args, **kwargs):
        return None

    def restart_ks(self, *args, **kwargs):
        return None

    def connect_printer(self, *args, **kwargs):
        return None

    def change_language(self, *args, **kwargs):
        return None

    def set_panel_title(self, *args, **kwargs):
        return None

    def show_all(self, *args, **kwargs):
        return None

    def state_ready(self, *args, **kwargs):
        return None

    def show_panel(self, *args, **kwargs):
        return None

    def _send_action(self, *args, **kwargs):
        return None

    def _confirm_send_action(self, *args, **kwargs):
        return None

    def _go_to_submenu(self, *args, **kwargs):
        return None

    def notification_log_clear(self, *args, **kwargs):
        return None

    def power_devices(self, *args, **kwargs):
        return None

    def get_active_spool(self, *args, **kwargs):
        return None

    def set_active_spool_details(self, *args, **kwargs):
        return None
