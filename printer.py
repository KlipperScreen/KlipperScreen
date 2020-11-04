import logging

class Printer:

    def __init__(self, data):
        self.config = data['configfile']['config']

        logging.info("### Reading printer config")
        self.toolcount = 0
        self.extrudercount = 0
        self.tools = []
        self.devices = {}
        self.state = data['print_stats']['state']
        self.data = data

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

        logging.info("### Toolcount: " + str(self.toolcount) + " Heaters: " + str(self.extrudercount))

    def process_update(self, data):
        keys = ['virtual_sdcard','pause_resume','idle_timeoue','print_stats']
        for x in keys:
            if x in data:
                for y in data[x]:
                    self.data[x][y] = data[x][y]

    def get_config_section_list(self):
        return list(self.config)

    def get_config_section(self, section):
        if section not in self.config:
            return False
        return self.config[section]

    def get_stat(self, stat, substat = None):
        if substat != None:
            return self.data[stat][substat]
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
