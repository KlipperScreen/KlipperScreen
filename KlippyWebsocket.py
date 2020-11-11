#!/usr/bin/python

import gi
import time
import threading

import json
import requests
import websocket
import asyncio
import logging
logger = logging.getLogger("KlipperScreen.KlipperWebsocket")

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from KlippyGcodes import KlippyGcodes

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

    def __init__(self, screen, callback):
        threading.Thread.__init__(self)
        self._screen = screen
        self._callback = callback
        self.klippy = MoonrakerApi(self)

        self._url = "127.0.0.1:7125"

    def connect (self):
        r = requests.get(
            "http://%s%s" % (self._url, api['oneshot_token']['url']),
            headers={"x-api-key":api_key}
        )
        if r.status_code != 200:
            logger.info("Failed to retrieve oneshot token")
            return

        token = json.loads(r.content)['result']
        self.ws_url = "ws://%s/websocket?token=%s" % (self._url, token)
        self.ws = websocket.WebSocketApp(self.ws_url,
            on_message  = lambda ws,msg:    self.on_message(ws, msg),
            on_error    = lambda ws,msg:    self.on_error(ws, msg),
            on_close    = lambda ws:        self.on_close(ws),
            on_open     = lambda ws:        self.on_open(ws)
        )

        self._wst = threading.Thread(target=self.ws.run_forever)
        self._wst.daemon = True
        self._wst.start()

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

        if "method" in response:
            Gdk.threads_add_idle(
                GLib.PRIORITY_HIGH_IDLE,
                self._callback,
                response['method'],
                response['params'][0] if "params" in response else {}
            )
        return

    def send_method(self, method, params={}, callback=None, *args):
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

    def on_open(self, ws):
        logger.info("### ws open ###")
        self.connected = True

    def on_close(self, ws):
        logger.info("### ws closed ###")
        self.connected = False

        # TODO: Make non-blocking
        Gdk.threads_add_idle(
            GLib.PRIORITY_HIGH_IDLE,
            self._screen.printer_initializing,
            "Connecting to Moonraker..."
        )

        while (True == True):
            try:
                info = self._screen.apiclient.get_info()
            except Exception:
                continue
            if info != False:
                self.connect()
                if self.is_connected():
                    break
            logger.info("### Waiting for websocket")
            time.sleep(.5)

        Gdk.threads_add_idle(
            GLib.PRIORITY_HIGH_IDLE,
            self._screen.printer_ready
        )


    def on_error(self, ws, error):
        print(error)

class MoonrakerApi:
    def __init__ (self, ws):
        self._ws = ws

    def emergency_stop(self):
        logger.info("Sending printer.emergency_stop")
        self._ws.send_method(
            "printer.emergency_stop"
        )

    def gcode_script(self, script, callback=None, *args):
        logger.debug("Sending printer.gcode.script: %s", script)
        self._ws.send_method(
            "printer.gcode.script",
            {"script": script},
            callback,
            *args
        )

    def get_file_list(self, callback=None, *args):
        #Commenting this log for being too noisy
        #logger.debug("Sending server.files.list")
        self._ws.send_method(
            "server.files.list",
            {},
            callback,
            *args
        )

    def get_file_metadata(self, filename, callback=None, *args):
        logger.debug("Sending server.files.metadata: %s", filename)
        self._ws.send_method(
            "server.files.metadata",
            {"filename": filename},
            callback,
            *args
        )

    def object_subscription(self, updates):
        logger.debug("Sending printer.objects.subscribe: %s", str(updates))
        self._ws.send_method(
            "printer.objects.subscribe",
            updates
        )

    def print_cancel(self, callback=None, *args):
        logger.debug("Sending printer.print.cancel")
        self._ws.send_method(
            "printer.print.cancel",
            {},
            callback,
            *args
        )

    def print_pause(self, callback=None, *args):
        logger.debug("Sending printer.print.pause")
        self._ws.send_method(
            "printer.print.pause",
            {},
            callback,
            *args
        )

    def print_resume(self, callback=None, *args):
        logger.debug("Sending printer.print.resume")
        self._ws.send_method(
            "printer.print.resume",
            {},
            callback,
            *args
        )

    def print_start(self, filename, callback=None, *args):
        logger.debug("Sending printer.print.start")
        self._ws.send_method(
            "printer.print.start",
            {
                "filename": filename
            },
            callback,
            *args
        )

    def temperature_set(self, heater, target, callback=None, *args):
        if heater == "heater_bed":
            logger.debug("Sending printer.gcode.script: %s", KlippyGcodes.set_bed_temp(target))
            self._ws.send_method(
                "printer.gcode.script",
                {
                    "script": KlippyGcodes.set_bed_temp(target)
                },
                callback,
                *args
            )
        else:
            logger.debug("Sending printer.gcode.script: %s",
                KlippyGcodes.set_ext_temp(target, heater.replace("tool","")))
            #TODO: Add max/min limits
            self._ws.send_method(
                "printer.gcode.script",
                {
                    "script": KlippyGcodes.set_ext_temp(target, heater.replace("tool",""))
                },
                callback,
                *args
            )

    def set_bed_temp(self, target, callback=None, *args):
        logger.debug("Sending set_bed_temp: %s", KlippyGcodes.set_bed_temp(target))
        self._ws.send_method(
            "printer.gcode.script",
            {
                "script": KlippyGcodes.set_bed_temp(target)
            },
            callback,
            *args
        )

    def set_tool_temp(self, tool, target, callback=None, *args):
        logger.debug("Sending set_tool_temp: %s", KlippyGcodes.set_ext_temp(target, tool))
        self._ws.send_method(
            "printer.gcode.script",
            {
                "script": KlippyGcodes.set_ext_temp(target, tool)
            },
            callback,
            *args
        )

    def restart(self):
        logger.debug("Sending printer.restart")
        self._ws.send_method(
            "printer.restart"
        )

    def restart_firmware(self):
        logger.debug("Sending printer.firmware_restart")
        self._ws.send_method(
            "printer.firmware_restart"
        )
