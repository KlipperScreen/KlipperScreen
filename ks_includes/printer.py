import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib


class Printer:
    def __init__(self, printer_info, data, state_execute_cb):
        self.klipper = {"version": printer_info['software_version']}
        self.tempstore = None
        self.config = None
        self.state = "disconnected"
        self.state_cb = state_execute_cb
        self.power_devices = {}
        self.store_timeout = False
        self.data = data
        self.devices = {}
        self.power_devices = {}
        self.state_callbacks = {
            "disconnected": None,
            "error": None,
            "paused": None,
            "printing": None,
            "ready": None,
            "startup": None,
            "shutdown": None
        }
        self.tools = []
        self.extrudercount = 0
        self.tempdevcount = 0
        self.fancount = 0
        self.output_pin_count = 0

    def reset(self):
        GLib.source_remove(self.store_timeout)
        self.store_timeout = None
        self.state = None
        self.state_cb = None
        self.data = None
        self.devices = None
        self.power_devices = None
        self.state_callbacks = None
        self.tools = None
        self.extrudercount = None
        self.tempdevcount = None
        self.fancount = None
        self.config = None
        self.klipper = None
        self.tempstore = None
        self.output_pin_count = None

    def reinit(self, printer_info, data):
        logging.debug(f"Moonraker object status: {data}")
        self.config = data['configfile']['config']
        self.extrudercount = 0
        self.tempdevcount = 0
        self.fancount = 0
        self.output_pin_count = 0
        self.tools = []
        self.devices = {}
        self.data = data
        self.klipper = {}
        self.tempstore = {}
        if not self.store_timeout:
            self.store_timeout = GLib.timeout_add_seconds(1, self._update_temp_store)

        self.klipper = {
            "version": printer_info['software_version']
        }

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
                self.devices[x] = {
                    "temperature": 0,
                    "target": 0
                }
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
            if x.startswith('output_pin '):
                # Support for hiding devices by name
                if not x.split()[1].startswith("_"):
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

        logging.info(f"Klipper version: {self.klipper['version']}")
        logging.info(f"# Extruders: {self.extrudercount}")
        logging.info(f"# Temperature devices: {self.tempdevcount}")
        logging.info(f"# Fans: {self.fancount}")
        logging.info(f"# Output pins: {self.output_pin_count}")

    def process_update(self, data):
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

        if "webhooks" in data or "print_stats" in data:
            self.process_status_update()

    def get_updates(self):
        updates = self.data.copy()
        updates.update(self.devices)
        return updates

    def evaluate_state(self):
        # webhooks states: startup, ready, shutdown, error
        if self.data['webhooks']['state'] == "ready":
            if self.data['print_stats']:  # standby, printing, paused, error, complete
                if self.data['print_stats']['state'] == 'paused' or self.data.get('pause_resume').get('is_paused'):
                    return "paused"
                if self.data['print_stats']['state'] == 'printing':
                    return "printing"
        return self.data['webhooks']['state']

    def process_status_update(self):
        state = self.evaluate_state()
        if state != self.state:
            self.change_state(state)

    def process_power_update(self, data):
        if data['device'] in self.power_devices:
            self.power_devices[data['device']]['status'] = data['status']

    def change_state(self, state):
        if state not in list(self.state_callbacks):  # disconnected, startup, ready, shutdown, error, paused, printing
            return
        logging.debug(f"Changing state from '{self.state}' to '{state}'")
        prev_state = self.state
        self.state = state
        if self.state_callbacks[state] is not None:
            logging.debug(f"Adding callback for state: {state}")
            Gdk.threads_add_idle(
                GLib.PRIORITY_HIGH_IDLE,
                self.state_cb,
                self.state_callbacks[state],
                prev_state
            )

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

    def get_data(self):
        return self.data

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
        logging.debug(f"{output_pins}")
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

    def get_klipper_version(self):
        return self.klipper['version']

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

    def get_state(self):
        return self.state

    def set_dev_temps(self, dev, temp, target=None, power=None):
        if dev in self.devices:
            self.devices[dev]['temperature'] = temp
            if target is not None:
                self.devices[dev]['target'] = target
            if power is not None:
                self.devices[dev]['power'] = power

    def get_dev_stats(self, dev):
        return self.devices[dev] if dev in self.devices else None

    def get_dev_stat(self, dev, stat):
        if dev in self.devices and stat in self.devices[dev]:
            return self.devices[dev][stat]
        return None

    def get_fan_speed(self, fan="fan", speed=None):
        if fan not in self.config or fan not in self.data:
            logging.debug(f"Error getting {fan} config")
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

    def get_pin_value(self, pin):
        if pin in self.data:
            return self.data[pin]["value"]
        elif pin in self.config and 'value' in self.config[pin]:
            return self.config[pin]["value"]
        return 0

    def get_extruder_count(self):
        return self.extrudercount

    def get_temp_store_devices(self):
        if self.tempstore is not None:
            return list(self.tempstore)

    def get_temp_store_device_has_target(self, device):
        return device in self.tempstore and "targets" in self.tempstore[device]

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
        logging.info(f"Temp store: {list(self.tempstore)}")

    def config_section_exists(self, section):
        return section in self.get_config_section_list()

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
