import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib


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
    toolcount = 0
    extrudercount = 0
    tempdevcount = 0
    fancount = 0

    def __init__(self, printer_info, data, state_execute_cb):
        self.state = "disconnected"
        self.state_cb = state_execute_cb
        self.power_devices = {}
        self.store_timeout = False

    def reset(self):
        self.state = None
        self.state_cb = None
        self.data = None
        self.devices = None
        self.power_devices = None
        self.state_callbacks = None
        self.tools = None
        self.toolcount = None
        self.extrudercount = None
        self.tempdevcount = None
        self.fancount = None
        GLib.source_remove(self.store_timeout)
        self.store_timeout = None
        self.config = None
        self.klipper = None
        self.tempstore = None

    def reinit(self, printer_info, data):
        logging.debug("Moonraker object status: %s" % data)
        self.config = data['configfile']['config']
        self.toolcount = 0
        self.extrudercount = 0
        self.tempdevcount = 0
        self.fancount = 0
        self.tools = []
        self.devices = {}
        self.data = data
        self.klipper = {}
        self.tempstore = {}
        if self.store_timeout is False:
            self.store_timeout = GLib.timeout_add_seconds(1, self._update_temp_store)

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
            if x == 'heater_bed' or x.startswith('heater_generic ') or x.startswith('temperature_sensor ') \
                    or x.startswith('temperature_fan '):
                self.devices[x] = {
                    "temperature": 0,
                    "target": 0
                }
                self.tempdevcount += 1
            if x == 'fan' or x.startswith('controller_fan ') or x.startswith('heater_fan ') \
                    or x.startswith('fan_generic '):
                self.fancount += 1
            if x.startswith('bed_mesh '):
                r = self.config[x]
                r['x_count'] = int(r['x_count'])
                r['y_count'] = int(r['y_count'])
                r['max_x'] = float(r['max_x'])
                r['min_x'] = float(r['min_x'])
                r['max_y'] = float(r['max_y'])
                r['min_y'] = float(r['min_y'])
                r['points'] = [[float(j.strip()) for j in i.split(",")] for i in r['points'].strip().split("\n")]
        self.process_update(data)

        logging.info("Klipper version: %s", self.klipper['version'])
        logging.info("# Toolcount: %s", str(self.toolcount))
        logging.info("# Extruders: %s", str(self.extrudercount))
        logging.info("# Temperature devices: %s", str(self.tempdevcount))
        logging.info("# Fans: %s", str(self.fancount))

    def process_update(self, data):
        keys = [
            'bed_mesh',
            'display_status',
            'fan',
            'gcode_move',
            'idle_timeout',
            'pause_resume',
            'print_stats',
            'toolhead',
            'virtual_sdcard',
            'webhooks',
            'fimware_retraction'
        ]

        for x in (self.get_tools() + self.get_heaters()):
            if x in data:
                for i in data[x]:
                    self.set_dev_stat(x, i, data[x][i])

        for x in data:
            if x == "configfile":
                continue
            if x not in self.data:
                self.data[x] = {}
            self.data[x].update(data[x])

        if "webhooks" in data or "idle_timeout" in data or "print_stats" in data:
            self.evaluate_state()

    def get_updates(self):
        updates = self.data.copy()
        updates.update(self.devices)
        return updates

    def evaluate_state(self):
        wh_state = self.data['webhooks']['state'].lower()  # possible values: startup, ready, shutdown, error

        if wh_state == "ready":
            new_state = "ready"
            if self.data['print_stats']:
                print_state = self.data['print_stats']['state'].lower()  # complete, error, paused, printing, standby
                if print_state == "paused":
                    new_state = "paused"
                if self.data['idle_timeout']:
                    idle_state = self.data['idle_timeout']['state'].lower()  # idle, printing, ready
                    if idle_state == "printing":
                        if print_state == "complete":
                            new_state = "ready"
                        elif print_state != "printing":  # Not printing a file, toolhead moving
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
        prev_state = self.state
        self.state = state
        if self.state_callbacks[state] is not None:
            logging.debug("Adding callback for state: %s" % state)
            Gdk.threads_add_idle(
                GLib.PRIORITY_HIGH_IDLE,
                self.state_cb,
                self.state_callbacks[state],
                prev_state
            )

    def configure_power_devices(self, data):
        self.power_devices = {}

        logging.debug("Processing power devices: %s" % data)
        for x in data['devices']:
            self.power_devices[x['device']] = {
                "status": "on" if x['status'] == "on" else "off"
            }
        logging.debug("Power devices: %s" % self.power_devices)

    def get_config_section_list(self, search=""):
        if not hasattr(self, "config"):
            return []
        return [i for i in list(self.config) if i.startswith(search)]

    def get_config_section(self, section):
        if section in self.config:
            return self.config[section]
        return False

    def get_config_section(self, section):
        if section not in self.config:
            return False
        return self.config[section]

    def get_data(self):
        return self.data

    def get_fans(self):
        fans = ["fan"] if len(self.get_config_section_list("fan")) > 0 else []
        fan_types = ["controller_fan", "fan_generic", "heater_fan"]
        for type in fan_types:
            for f in self.get_config_section_list("%s " % type):
                fans.append(f)
        return fans

    def get_gcode_macros(self):
        return self.get_config_section_list("gcode_macro ")

    def get_heaters(self):
        heaters = []
        if self.has_heated_bed():
            heaters.append("heater_bed")
        for h in self.get_config_section_list("heater_generic "):
            heaters.append(h)
        for h in self.get_config_section_list("temperature_sensor "):
            heaters.append(h)
        for h in self.get_config_section_list("temperature_fan "):
            heaters.append(h)
        return heaters

    def get_printer_status_data(self):
        data = {
            "printer": {
                "extruders": {
                    "count": self.extrudercount
                },
                "temperature_devices": {
                    "count": self.tempdevcount
                },
                "fans": {
                    "count": self.fancount
                },
                "bltouch": self.config_section_exists("bltouch"),
                "gcode_macros": {
                    "count": len(self.get_gcode_macros())
                },
                "idle_timeout": self.get_stat("idle_timeout").copy(),
                "pause_resume": self.get_stat("pause_resume").copy(),
                "power_devices": {
                    "count": len(self.get_power_devices())
                },
                "probe": self.config_section_exists("probe"),
                "firmware_retraction": self.config_section_exists("firmware_retraction")
            }
        }

        sections = ["bed_mesh", "bltouch", "probe", "quad_gantry_level", "z_tilt"]
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

    def get_stat(self, stat, substat=None):
        if stat not in self.data:
            return {}
        if substat is not None:
            if substat in self.data[stat]:
                return self.data[stat][substat]
            return {}
        return self.data[stat]

    def get_state(self):
        return self.state

    def set_dev_temps(self, dev, temp, target=None):
        if dev in self.devices:
            self.devices[dev]['temperature'] = temp
            if target is not None:
                self.devices[dev]['target'] = target

    def get_dev_stats(self, dev):
        if dev in self.devices:
            return self.devices[dev]
        return None

    def get_dev_stat(self, dev, stat):
        if dev in self.devices and stat in self.devices[dev]:
            return self.devices[dev][stat]
        return None

    def get_fan_speed(self, fan="fan", speed=None):
        if fan not in self.config:
            logging.debug("Error getting %s config", fan)
            return speed if speed is not None else 0
        if speed is None and "speed" in self.data[fan]:
            speed = self.data[fan]["speed"]
        if 'max_power' in self.config[fan]:
            max_power = float(self.config[fan]['max_power'])
            if max_power > 0:
                speed = speed / max_power
        if 'off_below' in self.config[fan]:
            off_below = float(self.config[fan]['off_below'])
            if speed < off_below:
                speed = 0
        return speed

    def get_extruder_count(self):
        return self.extrudercount

    def get_temp_store_devices(self):
        if self.tempstore is not None:
            return list(self.tempstore)

    def get_temp_store_device_has_target(self, device):
        if device in self.tempstore:
            if "targets" in self.tempstore[device]:
                return True
        return False

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
            temp[section] = self.tempstore[device][section][-results:]
        return temp

    def get_tools(self):
        return self.tools

    def get_tool_number(self, tool):
        return self.tools.index(tool)

    def has_heated_bed(self):
        if "heater_bed" in self.devices:
            return True

    def init_temp_store(self, result):
        for dev in result:
            self.tempstore[dev] = {}
            if "targets" in result[dev]:
                self.tempstore[dev]["targets"] = result[dev]["targets"]
            if "temperatures" in result[dev]:
                self.tempstore[dev]["temperatures"] = result[dev]["temperatures"]
        logging.info("Temp store: %s" % list(self.tempstore))

    def config_section_exists(self, section):
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

    def _update_temp_store(self):
        for device in self.tempstore:
            for x in self.tempstore[device]:
                if len(self.tempstore[device][x]) >= 1200:
                    self.tempstore[device][x].pop(0)
                temp = self.get_dev_stat(device, x[:-1])
                if temp is None:
                    temp = 0
                self.tempstore[device][x].append(round(temp, 2))
        return True
