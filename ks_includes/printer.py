import logging

logger = logging.getLogger("KlipperScreen.Printer")

class Printer:

    def __init__(self, printer_info, data):
        self.config = data['configfile']['config']

        logging.info("### Reading printer config")
        self.toolcount = 0
        self.extrudercount = 0
        self.tools = []
        self.devices = {}
        self.state = data['print_stats']['state']
        self.data = data
        self.klipper = {}
        self.power_devices = {}

        self.klipper = {
            "version": printer_info['software_version']
        }

        for x in self.config.keys():
            if x.startswith('extruder'):
                if x.startswith('extruder_stepper'):
                    continue

                self.devices[x] = {
                    "temperature": 0,
                    "target": 0
                }
                self.tools.append(x)
                if "shared_heater" in self.config[x]:
                    self.toolcount += 1
                    continue
                self.extrudercount += 1
            if x.startswith('heater_bed'):
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

        logger.info("Klipper version: %s", self.klipper['version'])
        logger.info("### Toolcount: " + str(self.toolcount) + " Heaters: " + str(self.extrudercount))

    def configure_power_devices(self, data):
        self.power_devices = {}

        logger.debug("Processing power devices: %s" % data)
        for x in data['devices']:
            logger.debug(x)
            self.power_devices[x['device']] = {
                "status": "on" if x['status'] == "on" else "off"
            }
        logger.debug("Power devices: %s" % self.power_devices)

    def process_update(self, data):
        keys = [
            'bed_mesh',
            'fan',
            'gcode_move',
            'idle_timeout',
            'pause_resume',
            'print_stats',
            'toolhead',
            'virtual_sdcard'
        ]
        for x in keys:
            if x in data:
                if x not in self.data:
                    self.data[x] = {}

                for y in data[x]:
                    self.data[x][y] = data[x][y]

        if "heater_bed" in data:
            d = data["heater_bed"]
            if "target" in d:
                self.set_dev_stat("heater_bed", "target", d["target"])
            if "temperature" in d:
                self.set_dev_stat("heater_bed", "temperature", d["temperature"])
        for x in self.get_tools():
            if x in data:
                d = data[x]
                if "target" in d:
                    self.set_dev_stat(x, "target", d["target"])
                if "temperature" in d:
                    self.set_dev_stat(x, "temperature", d["temperature"])

    def process_power_update(self, data):
        if data['device'] in self.power_devices:
            self.power_devices[data['device']]['status'] = data['status']

    def config_section_exists(self, section):
        return section in list(self.config)

    def get_config_section_list(self, search=""):
        return [i for i in list(self.config) if i.startswith(search)]

    def get_config_section(self, section):
        if section not in self.config:
            return False
        return self.config[section]

    def get_data(self):
        return self.data

    def get_gcode_macros(self):
        return self.get_config_section_list("gcode_macro ")

    def get_printer_status_data(self):
        data = {
            "printer": {
                "gcode_macros": {
                    "count": len(self.get_gcode_macros())
                },
                "idle_timeout": self.get_stat("idle_timeout").copy(),
                "pause_resume": self.get_stat("pause_resume").copy(),
                "power_devices": {
                    "count": len(self.get_power_devices())
                }
            }
        }

        sections = ["bed_mesh","bltouch","probe"]
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

    def set_dev_stat(self, dev, stat, value):
        if dev not in self.devices:
            return

        self.devices[dev][stat] = value
