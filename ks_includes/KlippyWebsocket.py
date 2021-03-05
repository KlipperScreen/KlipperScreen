#!/usr/bin/python

import gi
import time
import threading

import json
import requests
import websocket
import asyncio
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from ks_includes.KlippyGcodes import KlippyGcodes

#f = open("/home/pi/.moonraker_api_key", "r")
api_key = "" #f.readline()
#f.close()

api = {
     "printer_info": {
        "url": "/printer/info",
        "method": "get_printer_info"
    },
    "apikey": {
        "url": "/access/api_key"
    },
    "oneshot_token": {
        "url": "/access/oneshot_token"
    }
}

class KlippyWebsocket(threading.Thread):
    _req_id = 0
    connected = False
    callback_table = {}
    timeout = None

    def __init__(self, screen, callback, host, port):
        threading.Thread.__init__(self)
        self._screen = screen
        self._callback = callback
        self.klippy = MoonrakerApi(self)
        self.closing = False

        self._url = "%s:%s" % (host, port)

    def initial_connect(self):
        # Enable a timeout so that way if moonraker is not running, it will attempt to reconnect
        if self.timeout == None:
            self.timeout = GLib.timeout_add(500, self.reconnect)

    def connect (self):
        try:
            token = self._screen.apiclient.get_oneshot_token()
        except:
            logging.debug("Unable to get oneshot token")
            return False

        self.ws_url = "ws://%s/websocket?token=%s" % (self._url, token)
        self.ws = websocket.WebSocketApp(self.ws_url,
            on_message  = lambda ws,msg:    self.on_message(ws, msg),
            on_error    = lambda ws,msg:    self.on_error(ws, msg),
            on_close    = lambda ws:        self.on_close(ws),
            on_open     = lambda ws:        self.on_open(ws)
        )

        self._wst = threading.Thread(target=self.ws.run_forever)
        self._wst.daemon = True
        try:
            self._wst.start()
        except Exception:
            logging.debug("Error starting web socket")

    def close(self):
        self.closing = True
        self.ws.close()

    def is_connected(self):
        return self.connected

    def on_message(self, ws, message):
        response = json.loads(message)
        if "id" in response:
            if response['id'] in self.callback_table:
                Gdk.threads_add_idle(
                    GLib.PRIORITY_HIGH_IDLE,
                    self.callback_table[response['id']][0],
                    response,
                    self.callback_table[response['id']][1],
                    self.callback_table[response['id']][2],
                    *self.callback_table[response['id']][3]
                )
                self.callback_table.pop(response['id'])
                return

        if "method" in response and "on_message" in self._callback:
            Gdk.threads_add_idle(
                GLib.PRIORITY_HIGH_IDLE,
                self._callback['on_message'],
                response['method'],
                response['params'][0] if "params" in response else {}
            )
        return

    def send_method(self, method, params={}, callback=None, *args):
        if self.is_connected() == False:
            return False

        self._req_id += 1
        if callback != None:
            self.callback_table[self._req_id] = [callback, method, params, [*args]]

        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._req_id
        }
        self.ws.send(json.dumps(data))
        return True

    def on_open(self, ws):
        logging.info("Moonraker Websocket Open")
        logging.info("Self.connected = %s" % self.is_connected())
        self.connected = True
        self.timeout = None
        if "on_connect" in self._callback:
            Gdk.threads_add_idle(
                GLib.PRIORITY_HIGH_IDLE,
                self._callback['on_connect']
            )

    def on_close(self, ws):
        if self.is_connected() == False:
            logging.debug("Connection already closed")
            return

        if self.closing == True:
            logging.debug("Closing websocket")
            self.ws.stop()
            return

        logging.info("Moonraker Websocket Closed")
        self.connected = False
        if self.timeout == None:
            self.timeout = GLib.timeout_add(500, self.reconnect)

        if "on_close" in self._callback:
            Gdk.threads_add_idle(
                GLib.PRIORITY_HIGH_IDLE,
                self._callback['on_close'],
                "Lost Connection to Moonraker"
            )

    def reconnect(self):
        logging.debug("Attempting to reconnect")
        if self.is_connected():
            logging.debug("Reconnected")
            return False

        self.connect()
        return True


    def on_error(self, ws, error):
        logging.debug("Websocket error: %s" % error)
        if error.status_code == 401:
            # Check for any pending reconnects and remove. No amount of trying will help
            if self.timeout != None:
                GLib.source_remove(self.timeout)
            Gdk.threads_add_idle(
                GLib.PRIORITY_HIGH_IDLE,
                self._callback['on_close'],
                "Unable to authenticate with moonraker.\nCheck the API key"
            )

class MoonrakerApi:
    def __init__ (self, ws):
        self._ws = ws

    def emergency_stop(self):
        logging.info("Sending printer.emergency_stop")
        return self._ws.send_method(
            "printer.emergency_stop"
        )

    def gcode_script(self, script, callback=None, *args):
        logging.debug("Sending printer.gcode.script: %s", script)
        return self._ws.send_method(
            "printer.gcode.script",
            {"script": script},
            callback,
            *args
        )

    def get_file_list(self, callback=None, *args):
        #Commenting this log for being too noisy
        #logging.debug("Sending server.files.list")
        return self._ws.send_method(
            "server.files.list",
            {},
            callback,
            *args
        )

    def get_file_metadata(self, filename, callback=None, *args):
        logging.debug("Sending server.files.metadata: %s", filename)
        return self._ws.send_method(
            "server.files.metadata",
            {"filename": filename},
            callback,
            *args
        )

    def object_subscription(self, updates):
        logging.debug("Sending printer.objects.subscribe: %s", str(updates))
        return self._ws.send_method(
            "printer.objects.subscribe",
            updates
        )

    def power_device_off(self, device, callback=None, *args):
        logging.debug("Sending machine.device_power.off: %s" % device)
        return self._ws.send_method(
            "machine.device_power.off",
            {device: False},
            callback,
            *args
        )

    def power_device_on(self, device, callback=None, *args):
        logging.debug("Sending machine.device_power.on %s" % device)
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

    def temperature_set(self, heater, target, callback=None, *args):
        if heater == "heater_bed":
            logging.debug("Sending printer.gcode.script: %s", KlippyGcodes.set_bed_temp(target))
            return self._ws.send_method(
                "printer.gcode.script",
                {
                    "script": KlippyGcodes.set_bed_temp(target)
                },
                callback,
                *args
            )
        else:
            logging.debug("Sending printer.gcode.script: %s",
                KlippyGcodes.set_ext_temp(target, heater.replace("tool","")))
            #TODO: Add max/min limits
            return self._ws.send_method(
                "printer.gcode.script",
                {
                    "script": KlippyGcodes.set_ext_temp(target, heater.replace("tool",""))
                },
                callback,
                *args
            )

    def set_bed_temp(self, target, callback=None, *args):
        logging.debug("Sending set_bed_temp: %s", KlippyGcodes.set_bed_temp(target))
        return self._ws.send_method(
            "printer.gcode.script",
            {
                "script": KlippyGcodes.set_bed_temp(target)
            },
            callback,
            *args
        )

    def set_heater_temp(self, heater, target, callback=None, *args):
        logging.debug("Sending heater %s to temp: %s", heater, target)
        return self._ws.send_method(
            "printer.gcode.script",
            {
                "script": KlippyGcodes.set_heater_temp(heater, target)
            },
            callback,
            *args
        )

    def set_tool_temp(self, tool, target, callback=None, *args):
        logging.debug("Sending set_tool_temp: %s", KlippyGcodes.set_ext_temp(target, tool))
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
