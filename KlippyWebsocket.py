#!/usr/bin/python

import gi
import time
import threading

import json
import requests
import websocket

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

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
    def __init__(self, callback):
        threading.Thread.__init__(self)
        self._callback = callback

        self._url = "127.0.0.1:7125"

    def connect (self):
        r = requests.get("http://" + self._url + api['oneshot_token']['url'], headers={"x-api-key":api_key})
        if r.status_code != 200:
            print "Failed to retrieve oneshot token"
            return

        token = json.loads(r.content)['result']
        self.ws_url = "ws://" + self._url + "/websocket?token=" + token
        self.ws = websocket.WebSocketApp(self.ws_url,
            on_open = self.on_open,
            on_message = self.on_message,
            on_error = self.on_error,
            on_close = self.on_close,
        )
        self.ws.on_open = self.on_open
        self._wst = threading.Thread(target=self.ws.run_forever)
        self._wst.daemon = True
        self._wst.start()

    def on_message(self, message):
        result = json.loads(message)
        print json.dumps(result, indent=2)
        GLib.idle_add(self._callback, result['method'], result['params'][0])

    def send_method(self, method, params):
        #print "{jsonrpc: \"2.0\", method: \"" + str(method) + "\", params: " + json.dumps(params) + ", id: \"2\"}"
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": "2"
        }
        print json.dumps(data)
        self.ws.send(json.dumps(data))

    def on_open(self, ws):
        print "### ws open ###"
        self.ws.send('{jsonrpc: "2.0", method: "post_printer_objects_subscription", params: {extruder: ["temperature","target"], toolhead: ["position", "status"]}, id: "1"}')

    def on_close(self, ws):
        print "### ws closed ###"

    def on_error(self, ws, error):
        print(error)
