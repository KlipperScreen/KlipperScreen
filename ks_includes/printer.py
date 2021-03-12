import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import  Gdk, GLib
from ks_includes.KlippyGcodes import KlippyGcodes


class Printer:
    data = {}
    devices = {}
    power_devices = {}
    state_callbacks = {
        "disconnected": None,
        "error": None,
        "paused": None,
        "printing": None,
        "ready": None,
        "startup": None,
        "shutdown": None
    }
    tools = []

    def __init__(self, printer_info, data):
        self.state = "disconnected"
        self.power_devices = {}

    def reinit(self, printer_info, data):
        logging.debug("Moonraker object status: %s" % data)
        self.config = data['configfile']['config']
        self.toolcount = 0
        self.extrudercount = 0
        self.tools = []
        self.devices = {}
        self.data = data
        self.klipper = {}

        self.klipper = {
            "version": printer_info['software_version']
        }

        for x in self.config.keys():
            if x[0:8] == "extruder":
                if x.startswith('extruder_stepper'):
                    continue

                self.devices[x] = {
                    "temperature": 0,
                    "target": 0
                }
                self.tools.append(x)
                self.tools = sorted(self.tools)
                self.toolcount += 1
                if "shared_heater" in self.config[x]:
                    continue
                self.extrudercount += 1
            if x.startswith('heater_bed') or x.startswith('heater_generic '):
                self.devices[x] = {
                    "temperature": 0,
                    "target": 0
                }
            if x.startswith('bed_mesh '):
                r = self.config[x]
                r['x_count'] = int(r['x_count'])
                r['y_count'] = int(r['y_count'])
                r['max_x'] = float(r['max_x'])
                r['min_x'] = float(r['min_x'])
                r['max_y'] = float(r['max_y'])
                r['min_y'] = float(r['min_y'])
                r['points']  = [[float(j.strip()) for j in i.split(",")] for i in r['points'].strip().split("\n")]
        self.process_update(data)

        logging.info("Klipper version: %s", self.klipper['version'])
        logging.info("### Toolcount: " + str(self.toolcount) + " Heaters: " + str(self.extrudercount))

    def process_update(self, data):
        keys = [
            'bed_mesh',
            'fan',
            'gcode_move',
            'idle_timeout',
            'pause_resume',
            'print_stats',
            'toolhead',
            'virtual_sdcard',
            'webhooks'
        ]
        for x in keys:
            if x in data:
                if x not in self.data:
                    self.data[x] = {}

                for y in data[x]:
                    self.data[x][y] = data[x][y]

        for x in (self.get_tools() + self.get_heaters()):
            if x in data:
                d = data[x]
                for i in d:
                    self.set_dev_stat(x, i, d[i])

        if "webhooks" in data or "idle_timeout" in data or "print_stats" in data:
            self.evaluate_state()

    def evaluate_state(self):
        wh_state = self.data['webhooks']['state'].lower() # possible values: startup, ready, shutdown, error
        idle_state = self.data['idle_timeout']['state'].lower() # possible values: Idle, printing, ready
        print_state = self.data['print_stats']['state'].lower() # possible values: complete, paused, printing, standby

        if wh_state == "ready":
            new_state = "ready"
            if print_state == "paused":
                new_state = "paused"
            elif idle_state == "printing":
                if print_state == "complete":
                    new_state = "ready"
                elif print_state != "printing": # Not printing a file, toolhead moving
                    new_state = "busy"
                else:
                    new_state = "printing"

            if new_state != "busy":
                self.change_state(new_state)
        else:
            self.change_state(wh_state)

    def process_power_update(self, data):
        if data['device'] in self.power_devices:
            self.power_devices[data['device']]['status'] = data['status']

    def change_state(self, state):
        if state == self.state or state not in list(self.state_callbacks):
            return

        logging.debug("Changing state from '%s' to '%s'" % (self.state, state))
        self.state = state
        if self.state_callbacks[state] != None:
            logging.debug("Adding callback for state: %s" % state)
            Gdk.threads_add_idle(
                GLib.PRIORITY_HIGH_IDLE,
                self.state_callbacks[state]
            )

    def configure_power_devices(self, data):
        self.power_devices = {}

        logging.debug("Processing power devices: %s" % data)
        for x in data['devices']:
            self.power_devices[x['device']] = {
                "status": "on" if x['status'] == "on" else "off"
            }
        logging.debug("Power devices: %s" % self.power_devices)

    def config_section_exists(self, section):
        return section in list(self.config)

    def get_config_section_list(self, search=""):
        if not hasattr(self, "config"):
            return []
        return [i for i in list(self.config) if i.startswith(search)]

    def get_config_section(self, section):
        if section not in self.config:
            return False
        return self.config[section]

    def get_data(self):
        return self.data

    def get_gcode_macros(self):
        return self.get_config_section_list("gcode_macro ")

    def get_heaters(self):
        heaters = []
        if self.has_heated_bed():
            heaters.append("heater_bed")
        for h in self.get_config_section_list("heater_generic "):
            heaters.append(h)
        return heaters

    def get_printer_status_data(self):
        data = {
            "printer": {
                "bltouch": self.section_exists("bltouch"),
                "gcode_macros": {
                    "count": len(self.get_gcode_macros())
                },
                "idle_timeout": self.get_stat("idle_timeout").copy(),
                "pause_resume": self.get_stat("pause_resume").copy(),
                "power_devices": {
                    "count": len(self.get_power_devices())
                },
                "probe": self.section_exists("probe")
            }
        }

        sections = ["bed_mesh","bltouch","probe","quad_gantry_level","z_tilt"]
        for section in sections:
            if self.config_section_exists(section):
                data["printer"][section] = self.get_config_section(section).copy()

        return data

    def get_klipper_version(self):
        return self.klipper['version']

    def get_power_devices(self):
        return list(self.power_devices)

    def get_power_device_status(self, device):
        if device not in self.power_devices:
            return
        return self.power_devices[device]['status']

    def get_stat(self, stat, substat = None):
        if stat not in self.data:
            return None
        if substat != None:
            if substat in self.data[stat]:
                return self.data[stat][substat]
            return None
        return self.data[stat]

    def get_state(self):
        return self.state

    def set_dev_temps(self, dev, temp, target=None):
        if dev in self.devices:
            self.devices[dev]['temperature'] = temp
            if target != None:
                self.devices[dev]['target'] = target

    def get_dev_stats(self, dev):
        if dev in self.devices:
            return self.devices[dev]
        return None

    def get_dev_stat(self, dev, stat):
        if dev in self.devices and stat in self.devices[dev]:
            return self.devices[dev][stat]
        return None

    def get_extruder_count(self):
        return self.extrudercount

    def get_tools(self):
        return self.tools

    def get_tool_number(self, tool):
        return self.tools.index(tool)

    def has_heated_bed(self):
        if "heater_bed" in self.devices:
            return True

    def section_exists(self, section):
        if section in self.get_config_section_list():
            return True
        return False

    def set_callbacks(self, callbacks):
        for name, cb in callbacks.items():
            if name in list(self.state_callbacks):
                self.state_callbacks[name] = cb

    def set_dev_stat(self, dev, stat, value):
        if dev not in self.devices:
            return

        self.devices[dev][stat] = value
