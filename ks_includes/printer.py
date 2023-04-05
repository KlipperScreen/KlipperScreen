import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


class Printer:
    def __init__(self, state_cb, state_callbacks, busy_cb):
        self.config = {}
        self.data = {}
        self.state = "disconnected"
        self.state_cb = state_cb
        self.state_callbacks = state_callbacks
        self.devices = {}
        self.power_devices = {}
        self.tools = []
        self.extrudercount = 0
        self.tempdevcount = 0
        self.fancount = 0
        self.output_pin_count = 0
        self.store_timeout = None
        self.tempstore = {}
        self.busy_cb = busy_cb
        self.busy = False
        self.tempstore_size = 1200

    def reinit(self, printer_info, data):
        self.config = data['configfile']['config']
        self.data = data
        self.devices = {}
        self.tools = []
        self.extrudercount = 0
        self.tempdevcount = 0
        self.fancount = 0
        self.output_pin_count = 0
        self.tempstore = {}
        self.busy = False
        if not self.store_timeout:
            self.store_timeout = GLib.timeout_add_seconds(1, self._update_temp_store)
        self.tempstore_size = 1200

        for x in self.config.keys():
            if x[:8] == "extruder":
                self.tools.append(x)
                self.tools = sorted(self.tools)
                self.extrudercount += 1
                if x.startswith('extruder_stepper'):
                    continue
                self.devices[x] = {
                    "temperature": 0,
                    "target": 0
                }
            if x == 'heater_bed' \
                    or x.startswith('heater_generic ') \
                    or x.startswith('temperature_sensor ') \
                    or x.startswith('temperature_fan '):
                self.devices[x] = {"temperature": 0}
                if not x.startswith('temperature_sensor '):
                    self.devices[x]["target"] = 0
                # Support for hiding devices by name
                name = x.split()[1] if len(x.split()) > 1 else x
                if not name.startswith("_"):
                    self.tempdevcount += 1
            if x == 'fan' \
                    or x.startswith('controller_fan ') \
                    or x.startswith('heater_fan ') \
                    or x.startswith('fan_generic '):
                # Support for hiding devices by name
                name = x.split()[1] if len(x.split()) > 1 else x
                if not name.startswith("_"):
                    self.fancount += 1
            if x.startswith('output_pin ') and not x.split()[1].startswith("_"):
                self.output_pin_count += 1
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

        logging.info(f"Klipper version: {printer_info['software_version']}")
        logging.info(f"# Extruders: {self.extrudercount}")
        logging.info(f"# Temperature devices: {self.tempdevcount}")
        logging.info(f"# Fans: {self.fancount}")
        logging.info(f"# Output pins: {self.output_pin_count}")

    def process_update(self, data):
        if self.data is None:
            return
        for x in (self.get_tools() + self.get_heaters() + self.get_filament_sensors()):
            if x in data:
                for i in data[x]:
                    self.set_dev_stat(x, i, data[x][i])

        for x in data:
            if x == "configfile":
                continue
            if x not in self.data:
                self.data[x] = {}
            self.data[x].update(data[x])

        if "webhooks" in data or "print_stats" in data or "idle_timeout" in data:
            self.process_status_update()

    def evaluate_state(self):
        # webhooks states: startup, ready, shutdown, error
        # print_stats: standby, printing, paused, error, complete
        # idle_timeout: Idle, Printing, Ready
        if self.data['webhooks']['state'] == "ready" and self.data['print_stats']:
            if self.data['print_stats']['state'] == 'paused':
                return "paused"
            if self.data['print_stats']['state'] == 'printing':
                return "printing"
            if self.data['idle_timeout'] and self.data['idle_timeout']['state'].lower() == "printing":
                return "busy"
        return self.data['webhooks']['state']

    def process_status_update(self):
        state = self.evaluate_state()
        if state == "busy":
            self.busy = True
            return GLib.idle_add(self.busy_cb, True)
        if self.busy:
            self.busy = False
            GLib.idle_add(self.busy_cb, False)
        if state != self.state:
            self.change_state(state)

    def process_power_update(self, data):
        if data['device'] in self.power_devices:
            self.power_devices[data['device']]['status'] = data['status']

    def change_state(self, state):
        if state not in list(self.state_callbacks):
            return  # disconnected, startup, ready, shutdown, error, paused, printing
        if state != self.state:
            logging.debug(f"Changing state from '{self.state}' to '{state}'")
            self.state = state
        if self.state_callbacks[state] is not None:
            logging.debug(f"Adding callback for state: {state}")
            GLib.idle_add(self.state_cb, self.state_callbacks[state])

    def configure_power_devices(self, data):
        self.power_devices = {}

        logging.debug(f"Processing power devices: {data}")
        for x in data['devices']:
            self.power_devices[x['device']] = {
                "status": "on" if x['status'] == "on" else "off"
            }
        logging.debug(f"Power devices: {self.power_devices}")

    def get_config_section_list(self, search=""):
        if self.config is not None:
            return [i for i in list(self.config) if i.startswith(search)] if hasattr(self, "config") else []
        return []

    def get_config_section(self, section):
        return self.config[section] if section in self.config else False

    def get_macro(self, macro):
        return next(
            (
                self.config[key]
                for key in self.config.keys()
                if key.find(macro) > -1
            ),
            False,
        )

    def get_fans(self):
        fans = []
        if self.config_section_exists("fan"):
            fans.append("fan")
        fan_types = ["controller_fan", "fan_generic", "heater_fan"]
        for fan_type in fan_types:
            fans.extend(iter(self.get_config_section_list(f"{fan_type} ")))
        return fans

    def get_output_pins(self):
        output_pins = []
        output_pins.extend(iter(self.get_config_section_list("output_pin ")))
        return output_pins

    def get_gcode_macros(self):
        return self.get_config_section_list("gcode_macro ")

    def get_heaters(self):
        heaters = []
        if self.has_heated_bed():
            heaters.append("heater_bed")
        heaters.extend(iter(self.get_config_section_list("heater_generic ")))
        heaters.extend(iter(self.get_config_section_list("temperature_sensor ")))
        heaters.extend(iter(self.get_config_section_list("temperature_fan ")))
        return heaters

    def get_filament_sensors(self):
        sensors = list(self.get_config_section_list("filament_switch_sensor "))
        sensors.extend(iter(self.get_config_section_list("filament_motion_sensor ")))
        return sensors

    def get_probe(self):
        probe_types = ["probe", "bltouch", "smart_effector", "dockable_probe"]
        for probe_type in probe_types:
            if self.config_section_exists(probe_type):
                logging.info(f"Probe type: {probe_type}")
                return self.get_config_section(probe_type)
        return None

    def get_printer_status_data(self):
        data = {
            "printer": {
                "extruders": {"count": self.extrudercount},
                "temperature_devices": {"count": self.tempdevcount},
                "fans": {"count": self.fancount},
                "output_pins": {"count": self.output_pin_count},
                "gcode_macros": {"count": len(self.get_gcode_macros())},
                "idle_timeout": self.get_stat("idle_timeout").copy(),
                "pause_resume": {"is_paused": self.state == "paused"},
                "power_devices": {"count": len(self.get_power_devices())},
            }
        }

        sections = ["bed_mesh", "bltouch", "probe", "quad_gantry_level", "z_tilt"]
        for section in sections:
            if self.config_section_exists(section):
                data["printer"][section] = self.get_config_section(section).copy()

        sections = ["firmware_retraction", "input_shaper", "bed_screws", "screws_tilt_adjust"]
        for section in sections:
            data["printer"][section] = self.config_section_exists(section)

        return data

    def get_power_devices(self):
        return list(self.power_devices)

    def get_power_device_status(self, device):
        if device not in self.power_devices:
            return
        return self.power_devices[device]['status']

    def get_stat(self, stat, substat=None):
        if self.data is None or stat not in self.data:
            return {}
        if substat is not None:
            return self.data[stat][substat] if substat in self.data[stat] else {}
        return self.data[stat]

    def get_dev_stat(self, dev, stat):
        if dev in self.devices and stat in self.devices[dev]:
            return self.devices[dev][stat]
        return None

    def get_fan_speed(self, fan="fan"):
        speed = 0
        if fan not in self.config or fan not in self.data:
            logging.debug(f"Error getting {fan} config")
            return speed
        if "speed" in self.data[fan]:
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

    def get_pin_value(self, pin):
        if pin in self.data:
            return self.data[pin]["value"]
        elif pin in self.config and 'value' in self.config[pin]:
            return self.config[pin]["value"]
        return 0

    def get_temp_store_devices(self):
        if self.tempstore is not None:
            return list(self.tempstore)

    def device_has_target(self, device):
        return "target" in self.devices[device] or (device in self.tempstore and "targets" in self.tempstore[device])

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

    def init_temp_store(self, tempstore):
        if tempstore and 'result' in tempstore:
            if self.tempstore and list(self.tempstore) != list(tempstore['result']):
                logging.debug("Tempstore has changed")
                self.tempstore = tempstore['result']
                self.change_state(self.state)
            else:
                self.tempstore = tempstore['result']
            for device in self.tempstore:
                for x in self.tempstore[device]:
                    length = len(self.tempstore[device][x])
                    if length < self.tempstore_size:
                        for i in range(1, self.tempstore_size - length):
                            self.tempstore[device][x].insert(0, 0)
            logging.info(f"Temp store: {list(self.tempstore)}")

    def config_section_exists(self, section):
        return section in self.get_config_section_list()

    def set_dev_stat(self, dev, stat, value):
        if dev not in self.devices:
            return

        self.devices[dev][stat] = value

    def _update_temp_store(self):
        if self.tempstore is None:
            return False
        for device in self.tempstore:
            for x in self.tempstore[device]:
                self.tempstore[device][x].pop(0)
                temp = self.get_dev_stat(device, x[:-1])
                if temp is None:
                    temp = 0
                self.tempstore[device][x].append(temp)
        return True
