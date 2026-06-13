#!/usr/bin/python

import json
import logging
import os
import socket
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from ks_includes.MoonrakerApi import MoonrakerApi


class KlippyUDS(threading.Thread):
    _req_id = 0
    connected = False
    connecting = False
    callback_table = {}

    def __init__(self, callback, socket_path, port=None, api_key="", path="", ssl=None):
        threading.Thread.__init__(self)
        self._wst = None
        self._callback = callback
        self.api = MoonrakerApi(self)
        self.sock = None
        self.closing = False
        self.socket_path = os.path.expanduser(socket_path)
        self.api_key = api_key
        self._buffer = b""
        self._delimiter = "\x03"

    def initial_connect(self):
        logging.info("Starting UDS connection to %s", self.socket_path)
        self.connect()

    def connect(self):
        if self.connected:
            logging.debug("Already connected via UDS")
            return False
        self.closing = False
        self.connecting = True
        logging.debug("Attempting to connect via UDS")

        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect(self.socket_path)
            self.sock.settimeout(None)
            self.on_open()
            self._wst = threading.Thread(target=self._listen, daemon=True)
            self._wst.start()
        except Exception as e:
            logging.error("Failed to connect via UDS: %s", e)
            self.connected = False
            self.connecting = False
            if "on_error" in self._callback:
                GLib.idle_add(self._callback["on_error"], str(e), priority=GLib.PRIORITY_HIGH_IDLE)
            return True
        return False

    def close(self):
        logging.debug("Closing UDS connection")
        self.closing = True
        self.connecting = False
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass

    def _listen(self):
        while not self.closing:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self._buffer += chunk
                delimiter_bytes = self._delimiter.encode("utf-8")
                while delimiter_bytes in self._buffer:
                    frame, self._buffer = self._buffer.split(delimiter_bytes, 1)
                    frame_str = frame.decode("utf-8", errors="replace").strip()
                    if frame_str:
                        self._on_message(frame_str)
            except (ConnectionResetError, BrokenPipeError, OSError):
                break
            except Exception as e:
                logging.error("UDS Read Error: %s", e)
                break

        self.connected = False
        self.connecting = False
        if "on_close" in self._callback:
            GLib.idle_add(
                self._callback["on_close"], "Connection closed", priority=GLib.PRIORITY_HIGH_IDLE
            )

    def _on_message(self, message):
        try:
            response = json.loads(message)
        except json.JSONDecodeError:
            logging.debug("UDS: Invalid JSON received: %s", message)
            return

        if "id" in response and response["id"] in self.callback_table:
            args = (
                response,
                self.callback_table[response["id"]][1],
                self.callback_table[response["id"]][2],
                *self.callback_table[response["id"]][3],
            )
            GLib.idle_add(
                self.callback_table[response["id"]][0],
                *args,
                priority=GLib.PRIORITY_HIGH_IDLE,
            )
            self.callback_table.pop(response["id"])
            return

        if "method" in response and "on_message" in self._callback:
            args = (
                response["method"],
                response["params"][0] if "params" in response else {},
            )
            GLib.idle_add(self._callback["on_message"], *args, priority=GLib.PRIORITY_HIGH_IDLE)

    def send_method(self, method, params=None, callback=None, *args):
        if not self.connected or self.closing:
            return False
        if params is None:
            params = {}

        self._req_id += 1
        if callback is not None:
            self.callback_table[self._req_id] = [callback, method, params, [*args]]

        data = {"jsonrpc": "2.0", "method": method, "params": params, "id": self._req_id}
        message = json.dumps(data) + self._delimiter
        try:
            self.sock.sendall(message.encode("utf-8"))
        except Exception as e:
            logging.error("UDS Send Error: %s", e)
            self.connected = False
            return False
        return True

    def on_open(self):
        self.connected = True
        self.connecting = False
        if "on_connect" in self._callback:
            GLib.idle_add(self._callback["on_connect"], priority=GLib.PRIORITY_HIGH_IDLE)
