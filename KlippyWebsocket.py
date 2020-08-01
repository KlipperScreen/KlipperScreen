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
            logging.info("Failed to retrieve oneshot token")
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
                response['params'][0]
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
        print(json.dumps(data))
        self.ws.send(json.dumps(data))

    def on_open(self, ws):
        print("### ws open ###")
        logging.info("### ws open ###")
        self.connected = True

    def on_close(self, ws):
        print("### ws closed ###")
        logging.info("### ws closed ###")
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
            print(info)
            if info != False:
                self.connect()
                if self.is_connected():
                    break
            print ("### Waiting for websocket")
            time.sleep(.5)


    def on_error(self, ws, error):
        print(error)

class MoonrakerApi:
    def __init__ (self, ws):
        self._ws = ws

    def emergency_stop(self):
        self._ws.send_method(
            "post_printer_emergency_stop"
        )

    def print_cancel(self, callback=None, *args):
        self._ws.send_method(
            "post_printer_print_cancel",
            {},
            callback,
            *args
        )

    def print_pause(self, callback=None, *args):
        self._ws.send_method(
            "post_printer_print_pause",
            {},
            callback,
            *args
        )

    def print_resume(self, callback=None, *args):
        self._ws.send_method(
            "post_printer_print_resume",
            {},
            callback,
            *args
        )

    def print_start(self, filename, callback=None, *args):
        self._ws.send_method(
            "post_printer_print_start",
            {
                "filename": filename
            },
            callback,
            *args
        )

    def temperature_set(self, heater, target, callback=None, *args):
        if heater == "bed":
            self._ws.send_method(
                "post_printer_gcode_script",
                {
                    "script": KlippyGcodes.set_bed_temp(target)
                },
                callback,
                *args
            )
        else:
            #TODO: Add max/min limits
            self._ws.send_method(
                "post_printer_gcode_script",
                {
                    "script": KlippyGcodes.set_ext_temp(target, heater.replace("tool",""))
                },
                callback,
                *args
            )

    def restart(self):
        self._ws.send_method(
            "post_printer_restart"
        )

    def restart_firmware(self):
        self._ws.send_method(
            "post_printer_firmware_restart"
        )
