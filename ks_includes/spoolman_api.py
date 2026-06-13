import logging


class SpoolmanAPI:
    """Handles communication with the Spoolman proxy via Moonraker."""

    def __init__(self, client):
        self._client = client

    def _send_request(self, method, params, callback):
        """Send a JSON-RPC request via Moonraker with callback."""

        if callback is None:
            logging.error(f"Spoolman API: Attempted to call method '{method}' without a callback.")
            return False

        if not self._client.connected:
            logging.warning("Spoolman: not connected")
            return False

        def wrapper(response, *args):
            result = response.get("result") if isinstance(response, dict) else response
            callback(result, *args)

        self._client.send_method(method, params, callback=wrapper)
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
            if isinstance(result, dict) and "error" in result:
                logging.warning(f"Spoolman API error: {result.get('error')}")
                callback(False)
                return
            if result is None:
                callback(True)
                return
            if isinstance(result, dict) and "spool_id" in result:
                callback(True)
            elif isinstance(result, dict) and "result" in result:
                inner = result.get("result")
                if inner is None or (isinstance(inner, dict) and "spool_id" in inner):
                    callback(True)
                else:
                    callback(False)
            else:
                callback(False)

        if spool_id:
            params = {"spool_id": spool_id}
        else:
            # 24/05/26 Moonraker bug: it should accept None/null but it doesnt
            params = {}
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
