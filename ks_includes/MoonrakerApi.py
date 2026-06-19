# SPDX-FileCopyrightText: 2024 KlipperScreen contributors
# SPDX-License-Identifier: MIT

import logging

import gi

gi.require_version("Gtk", "3.0")

from ks_includes.KlippyGcodes import KlippyGcodes


class MoonrakerApi:
    def __init__(self, ws):
        self._ws = ws

    def emergency_stop(self):
        logging.info("Sending printer.emergency_stop")
        return self._ws.send_method("printer.emergency_stop")

    def gcode_script(self, script, callback=None, *args):
        logging.debug(f"Sending printer.gcode.script: {script}")
        return self._ws.send_method("printer.gcode.script", {"script": script}, callback, *args)

    def get_file_dir(self, path="gcodes", callback=None, *args):
        logging.debug(f"Sending server.files.directory {path}")
        return self._ws.send_method("server.files.list", {"path": path}, callback, *args)

    def get_file_list(self, callback=None, *args):
        logging.debug("Sending server.files.list")
        return self._ws.send_method("server.files.list", {}, callback, *args)

    def get_dir_info(self, callback=None, directory="gcodes", *args):
        logging.debug(f"Sending server.files.get_directory  {directory}")
        return self._ws.send_method(
            "server.files.get_directory", {"path": directory}, callback, *args
        )

    def get_file_roots(self, callback=None, *args):
        logging.debug("Sending server.files.roots")
        return self._ws.send_method("server.files.roots", {}, callback, *args)

    def get_file_metadata(self, filename, callback=None, *args):
        return self._ws.send_method(
            "server.files.metadata", {"filename": filename}, callback, *args
        )

    def object_subscription(self, updates):
        logging.debug("Sending printer.objects.subscribe")
        return self._ws.send_method("printer.objects.subscribe", updates)

    def power_device_off(self, devices, callback=None, *args):
        result = {item: None for item in devices}
        logging.debug(f"Sending machine.device_power.off: {result}")
        return self._ws.send_method("machine.device_power.off", result, callback, *args)

    def power_device_on(self, devices, callback=None, *args):
        result = {item: None for item in devices}
        logging.debug(f"Sending machine.device_power.on: {result}")
        return self._ws.send_method("machine.device_power.on", result, callback, *args)

    def print_cancel(self, callback=None, *args):
        logging.debug("Sending printer.print.cancel")
        return self._ws.send_method("printer.print.cancel", {}, callback, *args)

    def print_pause(self, callback=None, *args):
        logging.debug("Sending printer.print.pause")
        return self._ws.send_method("printer.print.pause", {}, callback, *args)

    def print_resume(self, callback=None, *args):
        logging.debug("Sending printer.print.resume")
        return self._ws.send_method("printer.print.resume", {}, callback, *args)

    def print_start(self, filename, callback=None, *args):
        logging.debug("Sending printer.print.start")
        return self._ws.send_method("printer.print.start", {"filename": filename}, callback, *args)

    def set_bed_temp(self, target, callback=None, *args):
        logging.debug(f"Sending set_bed_temp: {KlippyGcodes.set_bed_temp(target)}")
        return self._ws.send_method(
            "printer.gcode.script", {"script": KlippyGcodes.set_bed_temp(target)}, callback, *args
        )

    def set_heater_temp(self, heater, target, callback=None, *args):
        logging.debug(f"Sending heater {heater} to temp: {target}")
        return self._ws.send_method(
            "printer.gcode.script",
            {"script": KlippyGcodes.set_heater_temp(heater, target)},
            callback,
            *args,
        )

    def set_temp_fan_temp(self, temp_fan, target, callback=None, *args):
        logging.debug(f"Sending temperature fan {temp_fan} to temp: {target}")
        return self._ws.send_method(
            "printer.gcode.script",
            {"script": KlippyGcodes.set_temp_fan_temp(temp_fan, target)},
            callback,
            *args,
        )

    def set_tool_temp(self, tool, target, callback=None, *args):
        logging.debug(f"Sending set_tool_temp: {KlippyGcodes.set_ext_temp(target, tool)}")
        return self._ws.send_method(
            "printer.gcode.script",
            {"script": KlippyGcodes.set_ext_temp(target, tool)},
            callback,
            *args,
        )

    def restart(self):
        logging.debug("Sending printer.restart")
        return self._ws.send_method("printer.restart")

    def restart_firmware(self):
        logging.debug("Sending printer.firmware_restart")
        return self._ws.send_method("printer.firmware_restart")

    def identify_client(self, version, api_key):
        logging.debug("Sending server.connection.identify")
        params = {
            "client_name": "KlipperScreen",
            "version": f"{version}",
            "type": "display",
            "url": "https://github.com/KlipperScreen/KlipperScreen",
        }
        if api_key:
            params["api_key"] = api_key
        return self._ws.send_method("server.connection.identify", params)

    def query_server_info(self, callback=None, *args):
        return self._ws.send_method("server.info", {}, callback, *args)

    def list_webcams(self, callback=None, *args):
        return self._ws.send_method("server.webcams.list", {}, callback, *args)

    def get_power_devices(self, callback=None, *args):
        return self._ws.send_method("machine.device_power.devices", {}, callback, *args)

    def get_printer_info(self, callback=None, *args):
        return self._ws.send_method("printer.info", {}, callback, *args)

    def query_configfile(self, callback=None, *args):
        return self._ws.send_method(
            "printer.objects.query", {"objects": {"configfile": None}}, callback, *args
        )

    def query_objects(self, objects, callback=None, *args):
        return self._ws.send_method("printer.objects.query", {"objects": objects}, callback, *args)

    def get_printer_objects(self, callback=None, *args):
        return self._ws.send_method("printer.objects.list", {}, callback, *args)

    def get_available_commands(self, callback=None, *args):
        return self._ws.send_method("printer.gcode.help", {}, callback, *args)

    def get_system_info(self, callback=None, *args):
        return self._ws.send_method("machine.system_info", {}, callback, *args)

    def get_single_job_history(self, uid, callback=None, *args):
        return self._ws.send_method("server.history.get_job", {"uid": uid}, callback, *args)

    def get_temperature_store(self, callback=None, *args):
        return self._ws.send_method("server.temperature_store", {}, callback, *args)

    def get_server_config(self, callback=None, *args):
        return self._ws.send_method("server.config", {}, callback, *args)
