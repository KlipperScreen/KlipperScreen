#!/usr/bin/python

import threading
import json
import logging

import gi
import websocket

gi.require_version("Gtk", "3.0")
from gi.repository import GLib
from ks_includes.KlippyGcodes import KlippyGcodes


class KlippyWebsocket(threading.Thread):
    _req_id = 0
    connected = False
    connecting = True
    callback_table = {}
    reconnect_count = 0
    max_retries = 4

    def __init__(self, screen, callback, host, port):
        threading.Thread.__init__(self)
        self._wst = None
        self.ws_url = None
        self._screen = screen
        self._callback = callback
        self.klippy = MoonrakerApi(self)
        self.ws = None
        self.closing = False
        self.host = host
        self.port = port

    @property
    def _url(self):
        return f"{self.host}:{self.port}"

    @property
    def ws_proto(self):
        if int(self.port) in {443, 7130}:
            return "wss"
        return "ws"

    def retry(self):
        self.reconnect_count = 0
        self.connecting = True
        self.initial_connect()

    def initial_connect(self):
        # Enable a timeout so that way if moonraker is not running, it will attempt to reconnect
        self.connect()
        if self.connecting:
            GLib.timeout_add_seconds(10, self.reconnect)

    def connect(self):
        if self.connected:
            return
        self.reconnect_count += 1
        try:
            state = self._screen.apiclient.get_server_info()
            if state is False:
                if self.reconnect_count > 2:
                    self._screen.printer_initializing(
                        _("Cannot connect to Moonraker") + '\n\n'
                        + _("Retrying") + f' #{self.reconnect_count}'
                    )
                return False
            token = self._screen.apiclient.get_oneshot_token()
        except Exception as e:
            logging.critical(e, exc_info=True)
            logging.debug("Unable to get oneshot token")
            return False

        self.ws_url = f"{self.ws_proto}://{self._url}/websocket?token={token}"
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_close=self.on_close, on_error=self.on_error, on_message=self.on_message, on_open=self.on_open
        )
        self._wst = threading.Thread(target=self.ws.run_forever, daemon=True)
        try:
            logging.debug("Starting websocket thread")
            self._wst.start()
        except Exception as e:
            logging.critical(e, exc_info=True)
            logging.debug("Error starting web socket")

    def close(self):
        self.closing = True
        self.connecting = False
        if self.ws is not None:
            self.ws.close()

    def on_message(self, *args):
        message = args[1] if len(args) == 2 else args[0]
        response = json.loads(message)
        if "id" in response and response['id'] in self.callback_table:
            args = (response,
                    self.callback_table[response['id']][1],
                    self.callback_table[response['id']][2],
                    *self.callback_table[response['id']][3])
            GLib.idle_add(self.callback_table[response['id']][0], *args)
            self.callback_table.pop(response['id'])
            return

        if "method" in response and "on_message" in self._callback:
            args = response['method'], response['params'][0] if "params" in response else {}
            GLib.idle_add(self._callback['on_message'], *args)
        return

    def send_method(self, method, params=None, callback=None, *args):
        if not self.connected:
            return False
        if params is None:
            params = {}

        self._req_id += 1
        if callback is not None:
            self.callback_table[self._req_id] = [callback, method, params, [*args]]

        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._req_id
        }
        self.ws.send(json.dumps(data))
        return True

    def on_open(self, *args):
        logging.info("Moonraker Websocket Open")
        self.connected = True
        self._screen.reinit_count = 0
        self.reconnect_count = 0
        if "on_connect" in self._callback:
            GLib.idle_add(self._callback['on_connect'])

    def on_close(self, *args):
        # args: ws, status, message
        # sometimes ws is not passed due to bugs
        message = args[2] if len(args) == 3 else args[1]
        if message is not None:
            logging.info(f"{message}")
        if not self.connected:
            logging.debug("Connection already closed")
            return
        if self.closing:
            logging.debug("Closing websocket")
            self.ws.keep_running = False
            self.close()
            self.closing = False
            return
        if "on_close" in self._callback:
            GLib.idle_add(self._callback['on_close'], "Lost Connection to Moonraker")
        logging.info("Moonraker Websocket Closed")
        self.connected = False

    def reconnect(self):
        if self.connected:
            return False
        if self.reconnect_count > self.max_retries:
            logging.debug("Stopping reconnections")
            self.connecting = False
            self._screen.printer_initializing(
                _("Cannot connect to Moonraker")
                + f'\n\n{self._screen.apiclient.status}')
            return False
        logging.debug("Attempting to reconnect")
        self.connect()
        return True

    @staticmethod
    def on_error(*args):
        error = args[1] if len(args) == 2 else args[0]
        logging.debug(f"Websocket error: {error}")


class MoonrakerApi:
    def __init__(self, ws):
        self._ws = ws

    def emergency_stop(self):
        logging.info("Sending printer.emergency_stop")
        return self._ws.send_method(
            "printer.emergency_stop"
        )

    def gcode_script(self, script, callback=None, *args):
        logging.debug(f"Sending printer.gcode.script: {script}")
        return self._ws.send_method(
            "printer.gcode.script",
            {"script": script},
            callback,
            *args
        )

    def get_file_dir(self, path='gcodes', callback=None, *args):
        logging.debug("Sending server.files.directory")
        return self._ws.send_method(
            "server.files.list",
            {"path": path},
            callback,
            *args
        )

    def get_file_list(self, callback=None, *args):
        logging.debug("Sending server.files.list")
        return self._ws.send_method(
            "server.files.list",
            {},
            callback,
            *args
        )

    def get_file_metadata(self, filename, callback=None, *args):
        return self._ws.send_method(
            "server.files.metadata",
            {"filename": filename},
            callback,
            *args
        )

    def object_subscription(self, updates):
        logging.debug("Sending printer.objects.subscribe")
        return self._ws.send_method(
            "printer.objects.subscribe",
            updates
        )

    def power_device_off(self, device, callback=None, *args):
        logging.debug(f"Sending machine.device_power.off: {device}")
        return self._ws.send_method(
            "machine.device_power.off",
            {device: False},
            callback,
            *args
        )

    def power_device_on(self, device, callback=None, *args):
        logging.debug("Sending machine.device_power.on {device}")
        return self._ws.send_method(
            "machine.device_power.on",
            {device: False},
            callback,
            *args
        )

    def print_cancel(self, callback=None, *args):
        logging.debug("Sending printer.print.cancel")
        return self._ws.send_method(
            "printer.print.cancel",
            {},
            callback,
            *args
        )

    def print_pause(self, callback=None, *args):
        logging.debug("Sending printer.print.pause")
        return self._ws.send_method(
            "printer.print.pause",
            {},
            callback,
            *args
        )

    def print_resume(self, callback=None, *args):
        logging.debug("Sending printer.print.resume")
        return self._ws.send_method(
            "printer.print.resume",
            {},
            callback,
            *args
        )

    def print_start(self, filename, callback=None, *args):
        logging.debug("Sending printer.print.start")
        return self._ws.send_method(
            "printer.print.start",
            {
                "filename": filename
            },
            callback,
            *args
        )

    def set_bed_temp(self, target, callback=None, *args):
        logging.debug(f"Sending set_bed_temp: {KlippyGcodes.set_bed_temp(target)}")
        return self._ws.send_method(
            "printer.gcode.script",
            {
                "script": KlippyGcodes.set_bed_temp(target)
            },
            callback,
            *args
        )

    def set_heater_temp(self, heater, target, callback=None, *args):
        logging.debug(f"Sending heater {heater} to temp: {target}")
        return self._ws.send_method(
            "printer.gcode.script",
            {
                "script": KlippyGcodes.set_heater_temp(heater, target)
            },
            callback,
            *args
        )

    def set_temp_fan_temp(self, temp_fan, target, callback=None, *args):
        logging.debug(f"Sending temperature fan {temp_fan} to temp: {target}")
        return self._ws.send_method(
            "printer.gcode.script",
            {
                "script": KlippyGcodes.set_temp_fan_temp(temp_fan, target)
            },
            callback,
            *args
        )

    def set_tool_temp(self, tool, target, callback=None, *args):
        logging.debug(f"Sending set_tool_temp: {KlippyGcodes.set_ext_temp(target, tool)}")
        return self._ws.send_method(
            "printer.gcode.script",
            {
                "script": KlippyGcodes.set_ext_temp(target, tool)
            },
            callback,
            *args
        )

    def restart(self):
        logging.debug("Sending printer.restart")
        return self._ws.send_method(
            "printer.restart"
        )

    def restart_firmware(self):
        logging.debug("Sending printer.firmware_restart")
        return self._ws.send_method(
            "printer.firmware_restart"
        )
