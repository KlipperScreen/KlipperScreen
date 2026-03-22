import json
import logging
import threading
from urllib.parse import urlsplit, urlunsplit

import gi
import websocket

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


class SpoolmanWebsocket:
    def __init__(self, callback):
        self._callback = callback
        self._wst = None
        self.ws = None
        self.ws_url = None
        self.connected = False
        self.closing = False
        self.spool_id = None

    @staticmethod
    def build_url(server, spool_id):
        parsed = urlsplit(server)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        base_path = parsed.path.rstrip("/")
        path = f"{base_path}/api/v1/spool/{spool_id}"
        return urlunsplit((scheme, parsed.netloc, path, "", ""))

    def connect(self, server, spool_id):
        if not server or spool_id is None:
            return False
        self.closing = False
        self.spool_id = spool_id
        self.ws_url = self.build_url(server, spool_id)
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_close=self.on_close,
            on_error=self.on_error,
            on_message=self.on_message,
            on_open=self.on_open,
        )
        self._wst = threading.Thread(target=self.ws.run_forever, daemon=True)
        try:
            logging.debug(f"Starting Spoolman websocket thread for spool {spool_id}")
            self._wst.start()
        except Exception as e:
            logging.debug(f"Error starting Spoolman websocket {e}")
            return False
        return True

    def close(self):
        logging.debug("Closing Spoolman websocket")
        self.closing = True
        self.connected = False
        if self.ws is not None:
            self.ws.keep_running = False
            self.ws.close()

    def on_message(self, *args):
        message = args[1] if len(args) == 2 else args[0]
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logging.debug(f"Invalid Spoolman websocket payload: {message}")
            return
        if "on_message" in self._callback:
            GLib.idle_add(self._callback["on_message"], self, payload, priority=GLib.PRIORITY_HIGH_IDLE)

    def on_open(self, *args):
        logging.info("Spoolman Websocket Open")
        self.connected = True
        if "on_connect" in self._callback:
            GLib.idle_add(self._callback["on_connect"], self, priority=GLib.PRIORITY_HIGH_IDLE)

    def on_close(self, *args):
        if len(args) == 3:
            status = args[1]
            message = args[2]
        else:
            status = args[0]
            message = args[1]
        if message is not None:
            logging.info(f"Spoolman websocket closed {status} {message}")
        self.connected = False
        if "on_close" in self._callback:
            GLib.idle_add(self._callback["on_close"], self, priority=GLib.PRIORITY_HIGH_IDLE)

    @staticmethod
    def on_error(*args):
        error = args[1] if len(args) == 2 else args[0]
        logging.debug(f"Spoolman websocket error: {error}")
