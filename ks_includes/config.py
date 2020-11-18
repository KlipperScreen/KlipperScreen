import configparser
import os
import logging
import json

from io import StringIO

from os import path

logger = logging.getLogger("KlipperScreen.config")

class ConfigError(Exception):
    pass

class KlipperScreenConfig:
    config = None

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_path = self.get_config_file_location()

        try:
            self.config.read(self.config_path)
        except KeyError:
            raise ConfigError(f"Error reading config: {self.config_path}")

        self.log_config(self.config)

        self.get_menu_items("__main")
        #self.build_main_menu(self.config)


    def get_config_file_location(self):
        conf_name = "KlipperScreen.conf"

        file = "%s/%s" % (os.getenv("HOME"), conf_name)
        if not path.exists(file):
            file = "%s/%s" % (os.getcwd(), conf_name)
            if not path.exists(file):
                file = "%s/ks_includes/%s" % (os.getcwd(), conf_name)

        logger.info("Found configuration file at: %s" % file)
        return file

    def get_menu_items(self, menu="__main", subsection=""):
        if subsection != "":
            subsection = subsection + " "
        index = "menu %s %s" % (menu, subsection)
        logger.debug("Getting menu items for: %s" % index)
        items = [i[len(index):] for i in self.config.sections() if i.startswith(index)]
        menu_items = []
        for item in items:
            split = item.split()
            if len(split) == 1:
                menu_items.append(self._build_menu_item(menu, index + item))

        return menu_items

    def get_preheat_options(self):
        index = "preheat "
        items = [i[len(index):] for i in self.config.sections() if i.startswith(index)]
        logger.debug("Items: %s" % items)

        preheat_options = {}
        for item in items:
            preheat_options[item] = self._build_preheat_item(index + item)

        return preheat_options


    def log_config(self, config):
        lines = [
            " "
            "===== Config File =====",
            self._build_config_string(config),
            "======================="
        ]
        logger.info("\n".join(lines))

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
            "confirm": cfg.get("confirm", False)
        }

        try:
            item["params"] = json.loads(cfg.get("params", "{}"))
        except:
            logger.debug("Unable to parse parameters for [%s]" % name)
            item["params"] = {}

        return {name[(len(menu) + 6):]: item}

    def _build_preheat_item(self, name):
        if name not in self.config:
            return False
        cfg = self.config[name]
        item = {
            "extruder": cfg.getint("extruder", 0),
            "bed": cfg.getint("bed", 0)
        }
        return item
