import logging
import re


class NotificationHandler:
    """Handles routing of Moonraker websocket notifications"""

    def __init__(self, screen):
        self._screen = screen

        self._routes = {
            "notify_klippy_disconnected": self._klippy_disconnected,
            "notify_klippy_shutdown": self._klippy_shutdown,
            "notify_klippy_ready": self._klippy_ready,
            "notify_status_update": self._status_update,
            "notify_filelist_changed": self._filelist_changed,
            "notify_metadata_update": self._metadata_update,
            "notify_update_response": self._update_response,
            "notify_power_changed": self._power_changed,
            "notify_gcode_response": self._gcode_response,
            "notify_active_spool_set": self._active_spool_set,
        }

    def handle(self, action, data):
        handler = self._routes.get(action)

        if handler and handler(data):
            # return True to skip process_update
            return
        self._screen.process_update(action, data)

    def _klippy_disconnected(self, data):
        self._screen.printer.process_update({"webhooks": {"state": "disconnected"}})

    def _klippy_shutdown(self, data):
        self._screen.printer.process_update({"webhooks": {"state": "shutdown"}})

    def _klippy_ready(self, data):
        if not self._screen.initialized:
            self._screen.init_klipper()
            return True
        self._screen.printer.process_update({"webhooks": {"state": "ready"}})

    def _status_update(self, data):
        if self._screen.printer.state == "shutdown":
            return True

        self._screen.printer.process_update(data)

        if (
            "manual_probe" in data
            and data["manual_probe"]["is_active"]
            and "zcalibrate" not in self._screen._cur_panels
        ):
            self._screen.show_panel("zcalibrate")

        if (
            "screws_tilt_adjust" in data
            and "max_deviation" in data["screws_tilt_adjust"]
            and not data["screws_tilt_adjust"]["max_deviation"]
            and "bed_level" not in self._screen._cur_panels
        ):
            self._screen.show_panel("bed_level")

    def _filelist_changed(self, data):
        if self._screen.files is not None:
            self._screen.files.process_update(data)
        return True

    def _metadata_update(self, data):
        self._screen.files.request_metadata(data["filename"])

    def _update_response(self, data):
        if "message" in data and "Error" in data["message"]:
            logging.error(f"notify_update_response: {data['message']}")
            self._screen.show_popup_message(data["message"], 3, from_ws=True)
            if "KlipperScreen" in data["message"]:
                self._screen.restart_ks()

    def _power_changed(self, data):
        logging.debug("Power status changed: %s", data)
        self._screen.printer.process_power_update(data)
        self._screen.panels["splash_screen"].check_power_status()

    def _gcode_response(self, data):
        if self._screen.printer.state in ["error", "shutdown"]:
            return True

        if re.match("^(?:ok\\s+)?(B|C|T\\d*):", data):
            return True

        if data.startswith("// action:"):
            self._screen.process_action(data[10:])
            return True

        if data.startswith("echo: "):
            self._screen.show_popup_message(data[6:], 1, from_ws=True)
        elif "!! Extrude below minimum temp" in data:
            if self._screen._cur_panels[-1] != "temperature":
                self._screen.show_panel(
                    "temperature",
                    extra=self._screen.printer.get_stat("toolhead", "extruder"),
                )
            self._screen.show_popup_message(_("Temperature too low to extrude"))
            return True
        elif data.startswith("!! "):
            self._screen.show_popup_message(data[3:], 3, from_ws=True)
        elif (
            "unknown" in data.lower()
            and "TESTZ" not in data
            and "MEASURE_AXES_NOISE" not in data
            and "ACCELEROMETER_QUERY" not in data
        ):
            self._screen.show_popup_message(data, from_ws=True)
        elif "SAVE_CONFIG" in data and self._screen.printer.state == "ready":
            script = {"script": "SAVE_CONFIG"}
            self._screen._confirm_send_action(
                None,
                _("Save configuration?") + "\n\n" + _("Klipper will reboot"),
                "printer.gcode.script",
                script,
            )

    def _active_spool_set(self, data):
        self._screen.set_active_spool_details(data.get("spool_id"))
        # set_active_spool_details will trigger process update after getting the details
        return True
