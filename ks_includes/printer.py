import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


class Printer:
    def __init__(self, state_cb, state_callbacks):
        self.config = {}
        self.data = {}
        self.state = "disconnected"
        self.state_cb = state_cb
        self.state_callbacks = state_callbacks
        self.power_devices = {}
        self.tools = []
        self.extrudercount = 0
        self.tempdevcount = 0
        self.fancount = 0
        self.ledcount = 0
        self.pwm_tools_count = 0
        self.output_pin_count = 0
        self.store_timeout = None
        self.tempstore = {}
        self.tempstore_size = 1200
        self.cameras = []
        self.available_commands = {}
        self.spoolman = False
        self.temp_devices = self.sensors = None
        self.system_info = {}
        self.warnings = []

    def reinit(self, printer_info, data):
        self.config = data['configfile']['config']
        self.data = data
        self.tools.clear()
        self.extrudercount = 0
        self.tempdevcount = 0
        self.fancount = 0
        self.ledcount = 0
        self.output_pin_count = 0
        self.pwm_tools_count = 0
        self.tempstore.clear()
        self.tempstore_size = 1200
        self.available_commands.clear()
        self.temp_devices = self.sensors = None
        self.stop_tempstore_updates()
        self.system_info.clear()
        self.warnings = []

        for x in self.config.keys():
            # Support for hiding devices by name
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
                "temperature_fan"
            ):
                self.data[x] = {"temperature": 0}
                if section != "temperature_sensor":
                    self.data[x]["target"] = 0
                self.tempdevcount += 1
            elif section in (
                "fan",
                "controller_fan",
                "heater_fan",
                "fan_generic"
            ):
                self.fancount += 1
            elif section == "output_pin":
                self.output_pin_count += 1
            elif section == "pwm_tool":
                self.pwm_tools_count += 1
            elif section in (
                "led",
                "neopixel",
                "dotstar",
                "pca9533",
                "pca9632"
            ):
                self.ledcount += 1

        self.tools = sorted(self.tools)
        self.log_counts(printer_info)
        self.process_update(data)

    def log_counts(self, printer_info):
        logging.info(f"Klipper version: {printer_info['software_version']}")
        logging.info(f"# Extruders: {self.extrudercount}")
        logging.info(f"# Temperature devices: {self.tempdevcount}")
        logging.info(f"# Fans: {self.fancount}")
        logging.info(f"# Output pins: {self.output_pin_count}")
        logging.info(f"# PWM tools: {self.pwm_tools_count}")
        logging.info(f"# Leds: {self.ledcount}")

    def stop_tempstore_updates(self):
        if self.store_timeout is not None:
            GLib.source_remove(self.store_timeout)
            self.store_timeout = None

    def process_update(self, data):
        if self.data is None:
            return

        for x in data:
            if x == "configfile":
                if 'config' in data[x]:
                    self.config.update(data[x]['config'])
                if 'warnings' in data[x]:
                    self.warnings = data[x]['warnings']
            if x not in self.data:
                self.data[x] = {}
            self.data[x].update(data[x])

        if "webhooks" in data or "print_stats" in data or "idle_timeout" in data:
            self.process_status_update()

    def evaluate_state(self):
        # webhooks states: startup, ready, shutdown, error
        # print_stats: standby, printing, paused, error, complete
        # idle_timeout: Idle, Printing, Ready
        if self.data['webhooks']['state'] == "ready" and (
                'print_stats' in self.data and 'state' in self.data['print_stats']):
            if self.data['print_stats']['state'] == 'paused':
                return "paused"
            if self.data['print_stats']['state'] == 'printing':
                return "printing"
        return self.data['webhooks']['state']

    def process_status_update(self):
        state = self.evaluate_state()
        if state != self.state:
            self.change_state(state)
        return False

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
            GLib.idle_add(self.state_cb, state, self.state_callbacks[state])

    def configure_power_devices(self, data):
        self.power_devices = {}

        logging.debug(f"Processing power devices: {data}")
        for x in data['devices']:
            self.power_devices[x['device']] = {
                "status": "on" if x['status'] == "on" else "off"
            }
        logging.debug(f"Power devices: {self.power_devices}")

    def configure_cameras(self, data):
        self.cameras = data
        logging.debug(f"Cameras: {self.cameras}")

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
            if macro.startswith("_") or macro.upper() in ('LOAD_FILAMENT', 'UNLOAD_FILAMENT'):
                continue
            if self.get_macro(macro) and "rename_existing" in self.get_macro(macro):
                continue
            macros.append(macro)
        return macros

    def get_heaters(self):
        heaters = self.get_config_section_list("heater_generic ")
        if "heater_bed" in self.config:
            heaters.insert(0, "heater_bed")
        return heaters

    def get_temp_fans(self):
        return self.get_config_section_list("temperature_fan")

    def get_temp_sensors(self):
        return self.get_config_section_list("temperature_sensor")

    def get_filament_sensors(self):
        if self.sensors is None:
            self.sensors = list(self.get_config_section_list("filament_switch_sensor "))
            self.sensors.extend(iter(self.get_config_section_list("filament_motion_sensor ")))
        return self.sensors

    def get_probe(self):
        probe_types = ["probe", "bltouch", "smart_effector", "probe_eddy_current"]
        for probe_type in probe_types:
            if self.config_section_exists(probe_type):
                logging.info(f"Probe type: {probe_type}")
                return self.get_config_section(probe_type)
        return None

    def get_printer_status_data(self):
        return {
            "moonraker": {
                "power_devices": {"count": len(self.get_power_devices())},
                "cameras": {"count": len(self.cameras)},
                "spoolman": self.spoolman,
            },
            "printer": {
                "pause_resume": {"is_paused": self.state == "paused"},
                "extruders": {"count": self.extrudercount},
                "temperature_devices": {"count": self.tempdevcount},
                "fans": {"count": self.fancount},
                "output_pins": {"count": self.output_pin_count},
                "pwm_tools": {"count": self.pwm_tools_count},
                "gcode_macros": {"count": len(self.get_gcode_macros()), "list": self.get_gcode_macros()},
                "leds": {"count": self.ledcount},
                "config_sections": list(self.config.keys()),
                "available_commands": self.available_commands,
            }
        }

    def get_leds(self):
        return [
            led
            for led_type in ["dotstar", "led", "neopixel", "pca9533", "pca9632"]
            for led in self.get_config_section_list(f"{led_type} ")
            if not led.split()[1].startswith("_")
        ]

    def get_led_color_order(self, led):
        if led not in self.config or led not in self.data:
            logging.debug(f"Error getting {led} config")
            return None
        elif "color_order" in self.config[led]:
            return self.config[led]["color_order"]
        colors = ''
        for option in self.config[led]:
            if option in ("red_pin", 'initial_RED') and 'R' not in colors:
                colors += 'R'
            elif option in ("green_pin", 'initial_GREEN') and 'G' not in colors:
                colors += 'G'
            elif option in ("blue_pin", 'initial_BLUE') and 'B' not in colors:
                colors += 'B'
            elif option in ("white_pin", 'initial_WHITE') and 'W' not in colors:
                colors += 'W'
        logging.debug(f"Colors in led: {colors}")
        return colors

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
            return self.data.get(stat, {}).get(substat, {})
        else:
            return self.data.get(stat, {})

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
        return list(self.tempstore)

    def device_has_target(self, device):
        return device in self.data and "target" in self.data[device]

    def device_has_power(self, device):
        return device in self.data and "power" in self.data[device]

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

    def get_tempstore_size(self):
        return self.tempstore_size

    def get_temp_devices(self):
        if self.temp_devices is None:
            devices = [
                device
                for device in self.tools
                if not device.startswith('extruder_stepper')
            ]
            self.temp_devices = devices + self.get_heaters() + self.get_temp_sensors() + self.get_temp_fans()
        return self.temp_devices

    def get_tools(self):
        return self.tools

    def get_tool_number(self, tool):
        return self.tools.index(tool)

    def init_temp_store(self, tempstore):
        if self.tempstore and set(self.tempstore) != set(tempstore):
            logging.debug("Tempstore has changed")
            self.tempstore = tempstore
            self.change_state(self.state)
        else:
            self.tempstore = tempstore
        for device in self.tempstore:
            for x in self.tempstore[device]:
                length = len(self.tempstore[device][x])
                if length < self.tempstore_size:
                    for _ in range(1, self.tempstore_size - length):
                        self.tempstore[device][x].insert(0, 0)
        logging.info(f"Temp store: {list(self.tempstore)}")
        if not self.store_timeout:
            self.store_timeout = GLib.timeout_add_seconds(1, self._update_temp_store)

    def config_section_exists(self, section):
        return section in self.get_config_section_list()

    def _update_temp_store(self):
        if self.tempstore is None:
            return False
        for device in self.tempstore:
            for x in self.tempstore[device]:
                self.tempstore[device][x].pop(0)
                temp = self.get_stat(device, x[:-1])
                if not temp:
                    # If the temperature is not available, set it to 0.
                    temp = 0
                self.tempstore[device][x].append(temp)
        return True

    def enable_spoolman(self):
        logging.info("Enabling Spoolman")
        self.spoolman = True
