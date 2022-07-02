import configparser
import gettext
import os
import logging
import json
import re
import copy
import pathlib

from io import StringIO

from os import path

SCREEN_BLANKING_OPTIONS = [
    "300",  # 5 Minutes
    "900",  # 15 Minutes
    "1800",  # 30 Minutes
    "3600",  # 1 Hour
    "7200",  # 2 Hours
    "14400",  # 4 Hours
]

klipperscreendir = pathlib.Path(__file__).parent.resolve().parent


class ConfigError(Exception):
    pass


class KlipperScreenConfig:
    config = None
    configfile_name = "KlipperScreen.conf"
    do_not_edit_line = "#~# --- Do not edit below this line. This section is auto generated --- #~#"
    do_not_edit_prefix = "#~#"

    def __init__(self, configfile, screen=None):
        self.default_config_path = os.path.join(klipperscreendir, "ks_includes", "defaults.conf")
        self.config = configparser.ConfigParser()
        self.config_path = self.get_config_file_location(configfile)
        logging.debug("Config path location: %s" % self.config_path)
        self.defined_config = None

        try:
            self.config.read(self.default_config_path)
            if self.config_path != self.default_config_path:
                user_def, saved_def = self.separate_saved_config(self.config_path)
                self.defined_config = configparser.ConfigParser()
                self.defined_config.read_string(user_def)

                includes = [i[8:] for i in self.defined_config.sections() if i.startswith("include ")]
                for include in includes:
                    self._include_config("/".join(self.config_path.split("/")[:-1]), include)

                self.exclude_from_config(self.defined_config)

                self.log_config(self.defined_config)
                self.config.read_string(user_def)
                if saved_def is not None:
                    self.config.read_string(saved_def)
                    logging.info("====== Saved Def ======\n%s\n=======================" % saved_def)
                # This is the final config
                # self.log_config(self.config)
        except KeyError:
            raise ConfigError(f"Error reading config: {self.config_path}")
        except Exception:
            logging.exception("Unknown error with config")

        printers = sorted([i for i in self.config.sections() if i.startswith("printer ")])
        self.printers = []
        for printer in printers:
            self.printers.append({
                printer[8:]: {
                    "moonraker_host": self.config.get(printer, "moonraker_host", fallback="127.0.0.1"),
                    "moonraker_port": self.config.get(printer, "moonraker_port", fallback="7125"),
                    "moonraker_api_key": self.config.get(printer, "moonraker_api_key", fallback=False)
                }
            })
        if len(printers) <= 0:
            self.printers.append({
                "Printer": {
                    "moonraker_host": self.config.get("main", "moonraker_host", fallback="127.0.0.1"),
                    "moonraker_port": self.config.get("main", "moonraker_port", fallback="7125"),
                    "moonraker_api_key": self.config.get("main", "moonraker_api_key", fallback="")
                }
            })

        conf_printers_debug = copy.deepcopy(self.printers)
        for printer in conf_printers_debug:
            name = list(printer)[0]
            item = conf_printers_debug[conf_printers_debug.index(printer)]
            if item[name]['moonraker_api_key'] != "":
                item[name]['moonraker_api_key'] = "redacted"
        logging.debug("Configured printers: %s" % json.dumps(conf_printers_debug, indent=2))

        lang = self.get_main_config().get("language", None)
        lang = [lang] if lang is not None and lang != "default" else None
        logging.info("Detected language: %s" % lang)
        self.lang = gettext.translation('KlipperScreen', localedir='ks_includes/locales', languages=lang,
                                        fallback=True)
        self.lang.install(names=['gettext', 'ngettext'])

        self._create_configurable_options(screen)

    def _create_configurable_options(self, screen):

        self.configurable_options = [
            {"language": {
                "section": "main", "name": _("Language"), "type": "dropdown", "value": "system_lang",
                "callback": screen.restart_warning, "options": [
                    {"name": _("System") + " " + _("(default)"), "value": "system_lang"}]}},
            {"theme": {
                "section": "main", "name": _("Icon Theme"), "type": "dropdown",
                "value": "z-bolt", "callback": screen.restart_warning, "options": [
                    {"name": "Z-bolt" + " " + _("(default)"), "value": "z-bolt"}]}},
            {"print_estimate_method": {
                "section": "main", "name": _("Estimated Time Method"), "type": "dropdown",
                "value": "auto", "options": [
                    {"name": _("Auto") + " " + _("(default)"), "value": "auto"},
                    {"name": _("File"), "value": "file"},
                    {"name": _("Filament Used"), "value": "filament"},
                    {"name": _("Slicer"), "value": "slicer"}]}},
            {"screen_blanking": {
                "section": "main", "name": _("Screen Power Off Time"), "type": "dropdown",
                "value": "3600", "callback": screen.set_screenblanking_timeout, "options": [
                    {"name": _("Off"), "value": "off"}]
            }},
            {"24htime": {"section": "main", "name": _("24 Hour Time"), "type": "binary", "value": "True"}},
            {"side_macro_shortcut": {
                "section": "main", "name": _("Macro shortcut on sidebar"), "type": "binary",
                "value": "True", "callback": screen.toggle_macro_shortcut}},
            {"font_size": {
                "section": "main", "name": _("Font Size"), "type": "dropdown",
                "value": "medium", "callback": screen.restart_warning, "options": [
                    {"name": _("Small"), "value": "small"},
                    {"name": _("Medium") + " " + _("(default)"), "value": "medium"},
                    {"name": _("Large"), "value": "large"}]}},
            {"confirm_estop": {"section": "main", "name": _("Confirm Emergency Stop"), "type": "binary",
                               "value": "False"}},
            {"only_heaters": {"section": "main", "name": _("Hide sensors in Temp."), "type": "binary",
                              "value": "False", "callback": screen.restart_warning}},
            {"use_dpms": {"section": "main", "name": _("Screen DPMS"), "type": "binary",
                          "value": "True", "callback": screen.set_dpms}},
            {"print_estimate_compensation": {
                "section": "main", "name": _("Slicer Time correction (%)"), "type": "scale", "value": "100",
                "range": [50, 150], "step": 1}},

            # {"": {"section": "main", "name": _(""), "type": ""}}
        ]

        # Options that are in panels and shouldn't be added to the main settings
        panel_options = [
            {"invert_x": {"section": "main", "name": _("Invert X"), "type": None, "value": "False"}},
            {"invert_y": {"section": "main", "name": _("Invert Y"), "type": None, "value": "False"}},
            {"invert_z": {"section": "main", "name": _("Invert Z"), "type": None, "value": "False"}},
            {"move_speed_xy": {"section": "main", "name": _("XY Move Speed (mm/s)"), "type": None, "value": "50"}},
            {"move_speed_z": {"section": "main", "name": _("Z Move Speed (mm/s)"), "type": None, "value": "10"}},
            {"print_sort_dir": {"section": "main", "type": None, "value": "name_asc"}},
        ]

        self.configurable_options.extend(panel_options)

        lang_path = os.path.join(klipperscreendir, "ks_includes", "locales")
        langs = [d for d in os.listdir(lang_path) if not os.path.isfile(os.path.join(lang_path, d))]
        langs.sort()
        lang_opt = self.configurable_options[0]['language']['options']

        for lang in langs:
            lang_opt.append({"name": lang, "value": lang})

        t_path = os.path.join(klipperscreendir, 'styles')
        themes = [d for d in os.listdir(t_path) if (not os.path.isfile(os.path.join(t_path, d)) and d != "z-bolt")]
        themes.sort()
        theme_opt = self.configurable_options[1]['theme']['options']

        for theme in themes:
            theme_opt.append({"name": theme, "value": theme})

        index = self.configurable_options.index(
            [i for i in self.configurable_options if list(i)[0] == "screen_blanking"][0])
        for num in SCREEN_BLANKING_OPTIONS:
            hour = int(int(num) / 3600)
            if hour > 0:
                name = str(hour) + " " + ngettext("hour", "hours", hour)
            else:
                name = str(int(int(num) / 60)) + " " + _("minutes")
            self.configurable_options[index]['screen_blanking']['options'].append({
                "name": name,
                "value": num
            })

        for item in self.configurable_options:
            name = list(item)[0]
            vals = item[name]
            if vals['section'] not in self.config.sections():
                self.config.add_section(vals['section'])
            if name not in list(self.config[vals['section']]):
                self.config.set(vals['section'], name, vals['value'])

    def exclude_from_config(self, config):
        exclude_list = ['preheat']
        if not self.defined_config.getboolean('main', "use_default_menu", fallback=True):
            logging.info("Using custom menu, removing default menu entries.")
            exclude_list.append('menu __main')
            exclude_list.append('menu __print')
            exclude_list.append('menu __splashscreen')
        for i in exclude_list:
            for j in config.sections():
                if j.startswith(i):
                    for k in list(self.config.sections()):
                        if k.startswith(i):
                            del self.config[k]

    def _include_config(self, dir, path):
        full_path = path if path[0] == "/" else "%s/%s" % (dir, path)
        parse_files = []

        if "*" in full_path:
            parent_dir = "/".join(full_path.split("/")[:-1])
            file = full_path.split("/")[-1]
            if not os.path.exists(parent_dir):
                logging.info("Config Error: Directory %s does not exist" % parent_dir)
                return
            files = os.listdir(parent_dir)
            regex = "^%s$" % file.replace('*', '.*')
            for file in files:
                if re.match(regex, file):
                    parse_files.append(os.path.join(parent_dir, file))
        else:
            if not os.path.exists(os.path.join(full_path)):
                logging.info("Config Error: %s does not exist" % full_path)
                return
            parse_files.append(full_path)

        logging.info("Parsing files: %s" % parse_files)
        for file in parse_files:
            config = configparser.ConfigParser()
            config.read(file)
            includes = [i[8:] for i in config.sections() if i.startswith("include ")]
            for include in includes:
                self._include_config("/".join(full_path.split("/")[:-1]), include)
            self.exclude_from_config(config)
            self.log_config(config)
            self.config.read(file)

    def separate_saved_config(self, config_path):
        user_def = []
        saved_def = None
        found_saved = False
        if not path.exists(config_path):
            return [None, None]
        with open(config_path) as file:
            for line in file:
                line = line.replace('\n', '')
                if line == self.do_not_edit_line:
                    found_saved = True
                    saved_def = []
                    continue
                if found_saved is False:
                    user_def.append(line.replace('\n', ''))
                else:
                    if line.startswith(self.do_not_edit_prefix):
                        saved_def.append(line[(len(self.do_not_edit_prefix) + 1):])
        return ["\n".join(user_def), None if saved_def is None else "\n".join(saved_def)]

    def get_config_file_location(self, file):
        logging.info("Passed config file: %s" % file)
        if not path.exists(file):
            file = os.path.join(klipperscreendir, self.configfile_name)
            if not path.exists(file):
                file = self.configfile_name.lower()
                if not path.exists(file):
                    klipper_config = os.path.join(os.path.expanduser("~/"), "klipper_config")
                    file = os.path.join(klipper_config, self.configfile_name)
                    if not path.exists(file):
                        file = os.path.join(klipper_config, self.configfile_name.lower())
                        if not path.exists(file):
                            file = self.default_config_path

        logging.info("Found configuration file at: %s" % file)
        return file

    def get_config(self):
        return self.config

    def get_configurable_options(self):
        return self.configurable_options

    def get_lang(self):
        return self.lang

    def get_main_config(self):
        return self.config['main']

    def get_menu_items(self, menu="__main", subsection=""):
        if subsection != "":
            subsection = subsection + " "
        index = "menu %s %s" % (menu, subsection)
        items = [i[len(index):] for i in self.config.sections() if i.startswith(index)]
        menu_items = []
        for item in items:
            split = item.split()
            if len(split) == 1:
                menu_items.append(self._build_menu_item(menu, index + item))

        return menu_items

    def get_menu_name(self, menu="__main", subsection=""):
        name = ("menu %s %s" % (menu, subsection)) if subsection != "" else ("menu %s" % menu)
        if name not in self.config:
            return False
        return self.config[name].get('name')

    def get_preheat_options(self):
        index = "preheat "
        items = [i[len(index):] for i in self.config.sections() if i.startswith(index)]

        preheat_options = {}
        for item in items:
            preheat_options[item] = self._build_preheat_item(index + item)

        return preheat_options

    def get_printer_config(self, name):
        if not name.startswith("printer "):
            name = "printer %s" % name

        if name not in self.config:
            return None
        return self.config[name]

    def get_printer_power_name(self):
        return self.config['settings'].get("printer_power_name", "printer")

    def get_printers(self):
        return self.printers

    def get_user_saved_config(self):
        if self.config_path != self.default_config_path:
            print("Get")

    def save_user_config_options(self):
        save_config = configparser.ConfigParser()
        for item in self.configurable_options:
            name = list(item)[0]
            opt = item[name]
            curval = self.config[opt['section']].get(name)
            if curval != opt["value"] or (
                    self.defined_config is not None and opt['section'] in self.defined_config.sections() and
                    self.defined_config[opt['section']].get(name, None) not in (None, curval)):
                if opt['section'] not in save_config.sections():
                    save_config.add_section(opt['section'])
                save_config.set(opt['section'], name, str(curval))

        macro_sections = [i for i in self.config.sections() if i.startswith("displayed_macros")]
        for macro_sec in macro_sections:
            for item in self.config.options(macro_sec):
                value = self.config[macro_sec].getboolean(item, fallback=True)
                if value is False or (self.defined_config is not None and
                                      macro_sec in self.defined_config.sections() and
                                      self.defined_config[macro_sec].getboolean(item, fallback=True) is False and
                                      self.defined_config[macro_sec].getboolean(item, fallback=True) != value):
                    if macro_sec not in save_config.sections():
                        save_config.add_section(macro_sec)
                    save_config.set(macro_sec, item, str(value))

        save_output = self._build_config_string(save_config).split("\n")
        for i in range(len(save_output)):
            save_output[i] = "%s %s" % (self.do_not_edit_prefix, save_output[i])

        if self.config_path == self.default_config_path:
            user_def = ""
            saved_def = None
        else:
            user_def, saved_def = self.separate_saved_config(self.config_path)

        extra_lb = "\n" if saved_def is not None else ""
        contents = "%s\n%s%s\n%s\n%s\n%s\n" % (
            user_def, self.do_not_edit_line, extra_lb, self.do_not_edit_prefix, "\n".join(save_output),
            self.do_not_edit_prefix)

        if self.config_path != self.default_config_path:
            path = self.config_path
        else:
            path = os.path.expanduser("~/")
            klipper_config = os.path.join(path, "klipper_config")
            if os.path.exists(klipper_config):
                path = os.path.join(klipper_config, "KlipperScreen.conf")
            else:
                path = os.path.join(path, "KlipperScreen.conf")

        try:
            file = open(path, 'w')
            file.write(contents)
            file.close()
        except Exception:
            logging.error("Error writing configuration file in %s" % path)

    def set(self, section, name, value):
        self.config.set(section, name, value)

    def log_config(self, config):
        lines = [
            " "
            "===== Config File =====",
            re.sub(
                r'(moonraker_api_key\s*=\s*\S+)',
                'moonraker_api_key = [redacted]',
                self._build_config_string(config)
            ),
            "======================="
        ]
        logging.info("\n".join(lines))

    def _build_config_string(self, config):
        sfile = StringIO()
        config.write(sfile)
        sfile.seek(0)
        return sfile.read().strip()

    def _build_menu_item(self, menu, name):
        if name not in self.config:
            return False
        cfg = self.config[name]
        item = {
            "name": cfg.get("name"),
            "icon": cfg.get("icon"),
            "panel": cfg.get("panel", False),
            "method": cfg.get("method", False),
            "confirm": cfg.get("confirm", False),
            "enable": cfg.get("enable", True)
        }

        try:
            item["params"] = json.loads(cfg.get("params", "{}"))
        except Exception:
            logging.debug("Unable to parse parameters for [%s]" % name)
            item["params"] = {}

        return {name[(len(menu) + 6):]: item}

    def _build_preheat_item(self, name):
        if name not in self.config:
            return False
        cfg = self.config[name]
        item = {
            "extruder": cfg.getint("extruder", None),
            "bed": cfg.getint("bed", None),
            "heater_generic": cfg.getint("heater_generic", None),
            "temperature_fan": cfg.getint("temperature_fan", None),
            "gcode": cfg.get("gcode", None)
        }
        return item
