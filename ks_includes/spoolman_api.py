import logging


class SpoolmanAPI:
    """Handles communication with the Spoolman proxy."""

    def __init__(self, api_client):
        self.api = api_client

    def _make_request(self, method="GET", path="/v1/spool"):
        """Helper to standardize API calls through the KlipperScreen proxy."""
        try:
            result = self.api.post_request("server/spoolman/proxy", json={
                "request_method": method,
                "path": path,
            })

            if not result or "result" not in result:
                logging.warning(f"Spoolman API Error: {result}")
                return None

            # If the path was empty (e.g., setting spool_id), result might be True/False or a dict
            if isinstance(result["result"], bool):
                return result["result"]

            return result["result"]

        except Exception as e:
            logging.error(f"Spoolman API Exception: {e}")
            return None

    def get_active_spool_id(self) -> int:
        """Fetches the current active spool ID."""
        result = self.api.send_request("server/spoolman/spool_id")
        if not result or "spool_id" not in result:
            return None
        return result["spool_id"]

    def set_active_spool_id(self, spool_id: int) -> bool:
        """Sets the active spool ID."""
        try:
            self.api.post_request("server/spoolman/spool_id", json={"spool_id": spool_id})
            return True
        except Exception as e:
            logging.error(f"Error setting active spool: {e}")
            return False

    def clear_active_spool(self) -> bool:
        """Clears the active spool."""
        try:
            self.api.post_request("server/spoolman/spool_id", json={})
            return True
        except Exception as e:
            logging.error(f"Error clearing active spool: {e}")
            return False

    def get_spool_details(self, spool_id: int) -> dict:
        """Fetches full details for a specific spool."""
        return self._make_request(method="GET", path=f"/v1/spool/{spool_id}")

    def load_all_spools(self, allow_archived: bool = False) -> list:
        """Fetches the full list of spools."""
        path = f"/v1/spool?allow_archived={str(allow_archived).lower()}"
        return self._make_request(method="GET", path=path)
