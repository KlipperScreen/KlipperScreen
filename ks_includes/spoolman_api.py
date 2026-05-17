import logging
import threading


class SpoolmanAPI:
    """Handles communication with the Spoolman proxy via Moonraker websocket."""

    def __init__(self, websocket_client):
        self._ws = websocket_client
        self._req_lock = threading.Lock()
        self._req_id_counter = 0

    def _send_request(self, method, params, callback):
        """Send a JSON-RPC request via websocket with callback."""
        if callback is None:
            logging.error(f"Spoolman API: Attempted to call method '{method}' without a callback.")
            return False

        if not self._ws.connected:
            logging.warning("Spoolman: websocket not connected")
            return False

        with self._req_lock:
            self._req_id_counter += 1
            req_id = self._req_id_counter

        def wrapper(response, *args):
            result = response.get("result") if isinstance(response, dict) else response
            callback(result, *args)

        self._ws.send_method(method, params, callback=wrapper)
        return True

    def _make_request(self, http_method, path, callback, json_body=None, query=None):
        """Proxy an arbitrary Spoolman API call via server.spoolman.proxy."""
        params = {
            "use_v2_response": True,
            "request_method": http_method,
            "path": path,
        }
        if json_body:
            params["body"] = json_body
        if query:
            params["query"] = query

        def handle_proxy(result, *args):
            if not result:
                callback(None)
                return
            if result.get("error"):
                callback(None)
                return
            callback(result.get("response"))

        self._send_request("server.spoolman.proxy", params, handle_proxy)

    def get_active_spool_id(self, callback):
        """Fetch the current active spool ID."""
        def handle(result, *args):
            if isinstance(result, dict):
                callback(result.get("spool_id"))
            else:
                callback(None)

        self._send_request("server.spoolman.get_spool_id", {}, callback=handle)

    def set_active_spool_id(self, spool_id, callback):
        """Set the active spool ID."""
        def handle(result, *args):
            if isinstance(result, dict) and "spool_id" in result:
                callback(True)
            else:
                callback(False)

        params = {"spool_id": spool_id}
        self._send_request("server.spoolman.post_spool_id", params, callback=handle)

    def clear_active_spool(self, callback):
        """Clear the active spool."""
        self.set_active_spool_id(None, callback)

    def get_spool_details(self, spool_id, callback):
        """Fetch full details for a specific spool."""
        self._make_request("GET", f"/v1/spool/{spool_id}", callback)

    def load_all_spools(self, allow_archived=False, callback=None):
        """Fetch the full list of spools."""
        query = f"allow_archived={str(allow_archived).lower()}"
        self._make_request("GET", "/v1/spool", callback, query=query)

    def update_spool(self, spool_id, payload, callback):
        """Update a spool."""
        self._make_request("PATCH", f"/v1/spool/{spool_id}", callback, json_body=payload)
