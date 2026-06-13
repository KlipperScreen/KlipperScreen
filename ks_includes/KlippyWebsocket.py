#!/usr/bin/python

import json
import logging
import threading

import gi
import websocket

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from ks_includes.MoonrakerApi import MoonrakerApi


class KlippyWebsocket(threading.Thread):
    _req_id = 0
    connected = False
    connecting = False
    callback_table = {}

    @staticmethod
    def _format_error(error):
        if not error:
            return ""
        error_str = str(error)
        if "opcode=8" in error_str and "data=b'" in error_str:
            try:
                start = error_str.index("data=b'") + len("data=b'")
                end = error_str.index("'", start)
                payload = error_str[start:end]
                raw = payload.encode("latin1").decode("unicode_escape").encode("latin1")
                if len(raw) >= 2:
                    message = raw[2:].decode("utf-8", errors="ignore").strip()
                    return message
            except Exception:
                pass
        if error_str.startswith("[Errno "):
            end = error_str.find("] ")
            if end != -1:
                error_str = error_str[end + 2 :]
        return error_str

    @staticmethod
    def _format_close(status, message):
        if message:
            return f"Connection closed: {message}"
        return ""

    def __init__(self, callback, host, port, api_key, path="", ssl=None):
        threading.Thread.__init__(self)
        self._wst = None
        self.ws_url = None
        self._callback = callback
        self.api = MoonrakerApi(self)
        self.ws = None
        self.closing = False
        self.host = host
        self.port = port
        self.path = f"/{path}" if path else ""
        self.ssl = int(self.port) in {443, 7130} if ssl is None else bool(ssl)
        self.header = {"x-api-key": api_key} if api_key else {}
        self.api_key = api_key

    @property
    def _url(self):
        return f"{self.host}:{self.port}{self.path}"

    @property
    def ws_proto(self):
        return "wss" if self.ssl else "ws"

    def initial_connect(self):
        logging.info("Starting connection")
        self.connect()

    def connect(self):
        if self.connected:
            logging.debug("Already connected")
            return False
        self.closing = False
        self.connecting = True
        logging.debug("Attempting to connect")

        self.ws_url = f"{self.ws_proto}://{self._url}/websocket?token={self.api_key}"
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_close=self.on_close,
            on_error=self.on_error,
            on_message=self.on_message,
            on_open=self.on_open,
            header=self.header,
        )
        self._wst = threading.Thread(target=self.ws.run_forever, daemon=True)
        try:
            logging.debug("Starting websocket thread")
            self._wst.start()
        except Exception as e:
            logging.debug(f"Error starting web socket {e}")
            return True
        return False

    def close(self):
        logging.debug("Closing websocket")
        self.closing = True
        self.connecting = False
        if self.ws is not None:
            self.ws.keep_running = False
            self.ws.close()

    def on_message(self, *args):
        message = args[1] if len(args) == 2 else args[0]
        response = json.loads(message)
        if "id" in response and response["id"] in self.callback_table:
            args = (
                response,
                self.callback_table[response["id"]][1],
                self.callback_table[response["id"]][2],
                *self.callback_table[response["id"]][3],
            )
            GLib.idle_add(
                self.callback_table[response["id"]][0], *args, priority=GLib.PRIORITY_HIGH_IDLE
            )
            self.callback_table.pop(response["id"])
            return

        if "method" in response and "on_message" in self._callback:
            args = (response["method"], response["params"][0] if "params" in response else {})
            GLib.idle_add(self._callback["on_message"], *args, priority=GLib.PRIORITY_HIGH_IDLE)
        if self.closing:
            timer = threading.Timer(2, self.ws.close)
            timer.start()
        return

    def send_method(self, method, params=None, callback=None, *args):
        if not self.connected or self.closing:
            return False
        if params is None:
            params = {}

        self._req_id += 1
        if callback is not None:
            self.callback_table[self._req_id] = [callback, method, params, [*args]]

        data = {"jsonrpc": "2.0", "method": method, "params": params, "id": self._req_id}
        self.ws.send(json.dumps(data))
        return True

    def on_open(self, *args):
        self.connected = True
        self.connecting = False
        if "on_connect" in self._callback:
            GLib.idle_add(self._callback["on_connect"], priority=GLib.PRIORITY_HIGH_IDLE)

    def on_close(self, *args):
        # args: ws, status, message
        # sometimes ws is not passed due to bugs
        if len(args) == 3:
            status = args[1]
            message = args[2]
        else:
            status = args[0]
            message = args[1]
        info = self._format_close(status, message)
        if "on_close" in self._callback:
            GLib.idle_add(self._callback["on_close"], info, priority=GLib.PRIORITY_HIGH_IDLE)
        logging.info("Moonraker Websocket Closed")
        self.connected = False
        self.connecting = False

    def on_error(self, *args):
        error = args[1] if len(args) == 2 else args[0]
        formatted = self._format_error(error)
        if "on_error" in self._callback:
            GLib.idle_add(self._callback["on_error"], formatted, priority=GLib.PRIORITY_HIGH_IDLE)
