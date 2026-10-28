# This is the backend of the UI panel that communicates to sdbus-networkmanager
# Alfredo Monclus (alfrix) 2024
import asyncio
import logging
import subprocess
import time
from uuid import uuid4

import sdbus
from sdbus_async.networkmanager import (
    AccessPoint,
    ActiveConnection,
    IPv4Config,
    NetworkConnectionSettings,
    NetworkDeviceGeneric,
    NetworkDeviceWireless,
    NetworkManager,
    NetworkManagerConnectionProperties,
    NetworkManagerSettings,
    enums,
    exceptions,
)

from ks_includes import async_utils

NONE = 0  # The access point has no special security requirements.
PAIR_WEP40 = 1  # 40/64-bit WEP is supported for pairwise/unicast encryption.
PAIR_WEP104 = 2  # 104/128-bit WEP is supported for pairwise/unicast encryption.
PAIR_TKIP = 4  # TKIP is supported for pairwise/unicast encryption.
PAIR_CCMP = 8  # AES/CCMP is supported for pairwise/unicast encryption.
GROUP_WEP40 = 16  # 40/64-bit WEP is supported for group/broadcast encryption.
GROUP_WEP104 = 32  # 104/128-bit WEP is supported for group/broadcast encryption.
GROUP_TKIP = 64  # TKIP is supported for group/broadcast encryption.
GROUP_CCMP = 128  # AES/CCMP is supported for group/broadcast encryption.
KEY_MGMT_PSK = 256  # WPA/RSN Pre-Shared Key encryption
KEY_MGMT_802_1X = 512  # 802.1x authentication and key management
KEY_MGMT_SAE = 1024  # WPA/RSN Simultaneous Authentication of Equals
KEY_MGMT_OWE = 2048  # WPA/RSN Opportunistic Wireless Encryption
KEY_MGMT_OWE_TM = 4096  # WPA/RSN Opportunistic Wireless Encryption transition mode
KEY_MGMT_EAP_SUITE_B_192 = 8192  # WPA3 Enterprise Suite-B 192

# Scan polling / timeout tuning.
SCAN_POLL_INTERVAL = 0.25
SCAN_TIMEOUT = 20

# Device states that mean the wireless device is usable for scanning.
SCAN_MIN_STATE = enums.DeviceState.DISCONNECTED
SCAN_MAX_STATE = enums.DeviceState.ACTIVATED


def get_encryption(flags):
    if flags == 0:
        return "Open"

    encryption_mapping = {
        PAIR_WEP40: "WEP",
        PAIR_WEP104: "WEP",
        PAIR_TKIP: "TKIP",
        PAIR_CCMP: "AES",
        GROUP_WEP40: "WEP",
        GROUP_WEP104: "WEP",
        GROUP_TKIP: "TKIP",
        GROUP_CCMP: "AES",
        KEY_MGMT_PSK: "WPA-PSK",
        KEY_MGMT_802_1X: "802.1x",
        KEY_MGMT_SAE: "WPA-SAE",
        KEY_MGMT_OWE: "OWE",
        KEY_MGMT_OWE_TM: "OWE-TM",
        KEY_MGMT_EAP_SUITE_B_192: "WPA3-B192",
    }

    encryption_methods = []
    for flag, method_name in encryption_mapping.items():
        if flags & flag and method_name not in encryption_methods:
            encryption_methods.append(method_name)
    return " ".join(encryption_methods)


def WifiChannels(freq: str):
    if freq == "2484":
        return "2.4", "14"
    try:
        freq = float(freq)
    except ValueError:
        return "?", "?"
    if 2412 <= freq <= 2472:
        return "2.4", str(int((freq - 2407) / 5))
    elif 3657.5 <= freq <= 3692.5:
        return "3", str(int((freq - 3000) / 5))
    elif 4915 <= freq <= 4980:
        return "5", str(int((freq - 4000) / 5))
    elif 5035 <= freq <= 5885:
        return "5", str(int((freq - 5000) / 5))
    elif 6455 <= freq <= 7115:
        return "6", str(int((freq - 5950) / 5))
    else:
        return "?", "?"


class SdbusNm:
    """Asynchronous wrapper around the NetworkManager D-Bus interfaces."""

    def __init__(self, popup_callback, *, bus=None, loop=None):
        self.popup = popup_callback
        self._ensure_nm_running()

        self._tasks = set()
        self._subscriptions = []
        self._monitor_task = None
        self._state_callbacks = []
        self._destroyed = False
        self._last_phase_message = None

        self.wifi = False
        self.wlan_device = None
        self.wlan_device_path = None
        self.wifi_state = -1
        self.monitor_connection = False
        self._selected_interface = None

        self._bus = bus if bus is not None else sdbus.sd_bus_open_system()
        sdbus.set_default_bus(self._bus)
        self.nm = NetworkManager(self._bus)
        self.settings = NetworkManagerSettings(bus=self._bus)
        self.loop = loop if loop is not None else async_utils.get_event_loop()

        self.loop.call_soon_threadsafe(sdbus.set_default_bus, self._bus)

    # -- lifecycle ---------------------------------------------------------

    def _ensure_nm_running(self):
        try:
            status = subprocess.run(["systemctl", "is-active", "--quiet", "NetworkManager"])
            if status.returncode != 0:
                raise RuntimeError("Failed to detect NetworkManager service")
        except FileNotFoundError as e:
            logging.exception(f"{e}")
            raise RuntimeError(f"{e}") from e

    async def initialize(self):
        """Resolve the wireless device, subscribe to signals and read initial state."""
        await self._resolve_wireless_device()

        if self.wlan_device is not None:
            unmanaged = (await self.wlan_device.state) == enums.DeviceState.UNMANAGED
            if unmanaged:
                self.popup(
                    f"{self.wlan_device.interface} is not managed by "
                    "NetworkManager and cannot be controlled by this app"
                )
                return False

        self._subscribe_signals()
        return True

    def destroy(self):
        """Cancel all background work."""
        if self._destroyed:
            return
        self._destroyed = True
        async_utils.cancel_tasks(list(self._tasks))
        async_utils.cancel_tasks(list(self._subscriptions))
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            self._monitor_task = None

    def schedule(self, coro, *, name=None):
        """Schedule *coro* as a tracked task."""
        task = self.loop.create_task(coro, name=name)
        self._tasks.add(task)

        def _on_done(task):
            self._tasks.discard(task)

        task.add_done_callback(_on_done)
        return task

    def _track_subscription(self, coro):
        """Run a signal subscription coroutine as a tracked task."""
        task = self.loop.create_task(coro)
        self._subscriptions.append(task)
        return task

    def register_state_callback(self, cb):
        """Register *cb* to be called with the new DeviceState whenever the
        wireless device state transitions. *cb* runs on the event loop and must
        marshal to the GTK thread itself if it touches the UI."""
        self._state_callbacks.append(cb)

    def _subscribe_signals(self):
        """Subscribe to always-on signals."""
        self._track_subscription(self._subscribe_nm_global())

    async def _subscribe_nm_global(self):
        """Track global NetworkManager state changes (logging only)."""
        try:
            async for new_state in self.nm.state_changed.catch():
                try:
                    state_name = enums.NetworkManagerState(new_state).name
                except ValueError:
                    state_name = new_state
                logging.debug(f"NM global state changed: {state_name}")
        except exceptions.NetworkManagerUnknownDeviceError:
            return

    # -- device discovery --------------------------------------------------

    async def _resolve_wireless_device(self):
        self.wlan_device = None
        self.wlan_device_path = None
        for path in await self.nm.get_devices():
            dev = NetworkDeviceGeneric(path)
            try:
                if await dev.device_type == enums.DeviceType.WIFI:
                    self.wlan_device = NetworkDeviceWireless(path)
                    self.wlan_device_path = path
                    break
            except exceptions.NetworkManagerUnknownDeviceError:
                continue
        self.wifi = self.wlan_device is not None

    async def get_interfaces(self):
        interfaces = []
        for device in await self.nm.get_devices():
            try:
                interfaces.append(await NetworkDeviceGeneric(device).interface)
            except exceptions.NetworkManagerUnknownDeviceError:
                continue
        return interfaces

    async def get_all_network_devices(self):
        devices = []
        for path in await self.nm.get_devices():
            dev = NetworkDeviceGeneric(path)
            try:
                device_type = await dev.device_type
                interface = await dev.interface
            except exceptions.NetworkManagerUnknownDeviceError:
                continue
            if device_type in (enums.DeviceType.WIFI, enums.DeviceType.ETHERNET):
                devices.append(
                    {
                        "path": path,
                        "interface": interface,
                        "type": device_type,
                    }
                )
        return devices

    async def get_primary_interface(self):
        if await self.nm.primary_connection == "/":
            if self.wlan_device is not None:
                try:
                    return await self.wlan_device.interface
                except exceptions.NetworkManagerUnknownDeviceError:
                    pass
            async for interface in self._interface_names():
                if interface != "lo":
                    return interface
            return None
        active_conn = ActiveConnection(await self.nm.primary_connection)
        devices = await active_conn.devices
        if not devices:
            return None
        try:
            return await NetworkDeviceGeneric(devices[0]).interface
        except (IndexError, exceptions.NetworkManagerUnknownDeviceError):
            return None

    async def _interface_names(self):
        for path in await self.nm.get_devices():
            try:
                yield await NetworkDeviceGeneric(path).interface
            except exceptions.NetworkManagerUnknownDeviceError:
                continue

    async def get_ip_for_interface(self, iface):
        device_path = await self._get_device_path(iface)
        if device_path is None:
            return "?"
        device = NetworkDeviceGeneric(device_path)
        try:
            active_conn_path = await device.active_connection
            if active_conn_path == "/":
                return "?"
            active_conn = ActiveConnection(active_conn_path)
            ip4_path = await active_conn.ip4_config
            if ip4_path == "/":
                return "?"
            ip_info = IPv4Config(ip4_path)
            address_data = await ip_info.address_data
        except exceptions.NetworkManagerUnknownDeviceError:
            return "?"
        if address_data:
            return address_data[0]["address"][1]
        return "?"

    async def _get_device_path(self, iface):
        try:
            return await self.nm.get_device_by_ip_iface(iface)
        except exceptions.NetworkManagerUnknownDeviceError:
            return None

    async def set_selected_interface(self, iface):
        device_path = await self._get_device_path(iface)
        if device_path is not None:
            dev = NetworkDeviceGeneric(device_path)
            try:
                device_type = await dev.device_type
            except exceptions.NetworkManagerUnknownDeviceError:
                device_type = None
            if device_type == enums.DeviceType.WIFI:
                wireless = NetworkDeviceWireless(device_path)
                try:
                    if await wireless.state == enums.DeviceState.UNMANAGED:
                        self.popup(
                            f"{iface} is not managed by "
                            "NetworkManager and cannot be controlled by this app"
                        )
                        return False
                except exceptions.NetworkManagerUnknownDeviceError:
                    return False
                self.wlan_device = wireless
                self.wlan_device_path = device_path
                self.wifi = True
                if self.monitor_connection:
                    self._start_monitor()
        self._selected_interface = iface
        return True

    def get_selected_interface(self):
        return getattr(self, "_selected_interface", None)

    # -- network listing ---------------------------------------------------

    async def get_known_networks(self):
        known_networks = []
        saved_network_paths = await self.settings.list_connections()
        for netpath in saved_network_paths:
            saved_con = NetworkConnectionSettings(netpath)
            try:
                con_settings = await saved_con.get_settings()
            except exceptions.NetworkManagerUnknownDeviceError:
                continue
            if con_settings["connection"]["type"][1] == "802-11-wireless":
                known_networks.append(
                    {
                        "SSID": con_settings["802-11-wireless"]["ssid"][1].decode(
                            "utf-8", errors="ignore"
                        ),
                        "UUID": con_settings["connection"]["uuid"][1],
                    }
                )
        return known_networks

    async def is_known(self, ssid):
        return any(net["SSID"] == ssid for net in await self.get_known_networks())

    async def get_networks(self):
        networks = []
        if self.wlan_device is None:
            return networks
        try:
            ap_paths = await self.wlan_device.access_points
        except exceptions.NetworkManagerUnknownDeviceError:
            return networks

        known = await self.get_known_networks()
        known_ssid = {net["SSID"] for net in known}
        connected_ap = await self.wlan_device.active_access_point

        for ap_path in ap_paths:
            try:
                ap = AccessPoint(ap_path)
                ssid_bytes = await ap.ssid
                if not ssid_bytes:
                    continue
            except exceptions.NetworkManagerUnknownDeviceError:
                continue
            try:
                security_flags = (await ap.rsn_flags) or (await ap.wpa_flags) or (await ap.flags)
                strength = await ap.strength
                frequency = await ap.frequency
                hw_address = await ap.hw_address
            except exceptions.NetworkManagerUnknownDeviceError:
                continue
            ssid_text = ssid_bytes.decode("utf-8", errors="ignore")
            networks.append(
                {
                    "SSID": ssid_text,
                    "known": ssid_text in known_ssid,
                    "security": get_encryption(security_flags),
                    "frequency": WifiChannels(str(frequency))[0],
                    "channel": WifiChannels(str(frequency))[1],
                    "signal_level": strength,
                    "BSSID": hw_address,
                    "connected": ap_path == connected_ap,
                }
            )
        return sorted(networks, key=lambda i: i["signal_level"], reverse=True)

    async def get_bssid_from_ssid(self, ssid):
        for net in await self.get_networks():
            if ssid == net["SSID"]:
                return net["BSSID"]
        return None

    async def get_connected_bssid(self):
        if self.wlan_device is None:
            return None
        connected = await self.wlan_device.active_access_point
        if connected == "/":
            return None
        return await AccessPoint(connected).hw_address

    async def get_security_type(self, ssid):
        for network in await self.get_networks():
            if network["SSID"] == ssid:
                return network["security"]
        return None

    # -- scanning ----------------------------------------------------------

    async def request_rescan(self):
        """Request a Wi-Fi scan and return once it completes."""
        device = self.wlan_device
        if device is None:
            return None
        try:
            state = await device.state
            if state < SCAN_MIN_STATE or state > SCAN_MAX_STATE:
                logging.debug(f"Interface not ready for scan: {state}")
                return None
            initial_scan = await device.last_scan
            try:
                await device.request_scan({})
            except exceptions.NetworkManagerPermissionDeniedError:
                self.popup("Insufficient privileges to scan")
                return None
            except Exception as e:
                logging.exception("Scan request failed")
                self.popup(f"Unexpected error: {e}")
                return None

            scanned = await self._wait_for_scan(device, initial_scan)
            if not scanned:
                logging.debug("Scan timed out")
            # Always return the latest known scan timestamp, even on timeout, so
            # callers get a usable value instead of None.
            return await device.last_scan
        except exceptions.NetworkManagerUnknownDeviceError:
            logging.debug("Wireless device disappeared during scan")
            return None

    async def _wait_for_scan(self, device, initial_scan):
        """Wait until ``last_scan`` changes (or time out)."""
        deadline = time.monotonic() + SCAN_TIMEOUT
        while time.monotonic() < deadline:
            try:
                await asyncio.sleep(SCAN_POLL_INTERVAL)
            except asyncio.CancelledError:
                raise
            try:
                current = await device.last_scan
            except exceptions.NetworkManagerUnknownDeviceError:
                return False
            if current != initial_scan and current != -1:
                return True
        return False

    # -- saved networks ----------------------------------------------------

    async def add_network(self, ssid, psk, eap_method=None, identity="", phase2=None):
        security_type = await self.get_security_type(ssid)
        logging.debug(f"Adding network of type: {security_type}")
        if security_type is None:
            return {"error": "network_not_found", "message": _("Network not found")}

        if await self.is_known(ssid):
            await self.delete_network(ssid)

        wifi_iface = await self._wifi_interface()
        connection_props = {
            "id": ("s", ssid),
            "uuid": ("s", str(uuid4())),
            "type": ("s", "802-11-wireless"),
        }
        if wifi_iface:
            connection_props["interface-name"] = ("s", wifi_iface)
        properties: NetworkManagerConnectionProperties = {
            "connection": connection_props,
            "802-11-wireless": {
                "mode": ("s", "infrastructure"),
                "ssid": ("ay", ssid.encode("utf-8", errors="ignore")),
                "security": ("s", "802-11-wireless-security"),
            },
            "ipv4": {"method": ("s", "auto")},
            "ipv6": {"method": ("s", "auto")},
        }

        if security_type == "Open":
            properties["802-11-wireless-security"] = {
                "key-mgmt": ("s", "none"),
            }
        elif "WPA-PSK" in security_type:
            properties["802-11-wireless-security"] = {
                "key-mgmt": ("s", "wpa-psk"),
                "psk": ("s", psk),
            }
        elif "SAE" in security_type:
            properties["802-11-wireless-security"] = {
                "key-mgmt": ("s", "sae"),
                "psk": ("s", psk),
            }
        elif "WPA3-B192" in security_type:
            properties["802-11-wireless-security"] = {
                "key-mgmt": ("s", "wpa-eap-suite-b-192"),
                "psk": ("s", psk),
            }
        elif "OWE" in security_type:
            properties["802-11-wireless-security"] = {
                "key-mgmt": ("s", "owe"),
            }
        elif "802.1x" in security_type:
            properties["802-11-wireless-security"] = {
                "key-mgmt": ("s", "wpa-eap"),
                "eap": ("as", [eap_method]),
                "identity": ("s", identity),
                "password": ("s", psk.encode("utf-8")),
            }
            if phase2:
                if eap_method == "ttls":
                    properties["802-11-wireless-security"]["phase2_autheap"] = ("s", phase2)
                else:
                    properties["802-11-wireless-security"]["phase2_auth"] = ("s", phase2)
        elif "WEP" in security_type:
            properties["802-11-wireless-security"] = {
                "key-mgmt": ("s", "none"),
                "wep-key-type": ("u", 2),
                "wep-key0": ("s", psk),
                "auth-alg": ("s", "shared"),
            }
        else:
            return {
                "error": "unknown_security_type",
                "message": _("Unknown security type"),
            }

        try:
            await self.settings.add_connection(properties)
            return {"status": "success"}
        except exceptions.NmSettingsPermissionDeniedError:
            logging.exception("Insufficient privileges")
            return {
                "error": "insufficient_privileges",
                "message": _("Insufficient privileges"),
            }
        except exceptions.NmConnectionInvalidPropertyError:
            logging.exception("Invalid property")
            return {"error": "psk_invalid", "message": _("Invalid password")}
        except Exception as e:
            logging.exception("Couldn't add network")
            return {"error": "unknown", "message": _("Couldn't add network") + f"\n{e}"}

    async def _wifi_interface(self):
        if self.wlan_device is not None:
            try:
                return await self.wlan_device.interface
            except exceptions.NetworkManagerUnknownDeviceError:
                return None
        return None

    async def disconnect_network(self):
        if self.wlan_device is None:
            return
        try:
            await self.wlan_device.disconnect()
        except exceptions.NetworkManagerUnknownDeviceError:
            logging.debug("Wireless device disappeared on disconnect")

    async def delete_network(self, ssid):
        path = await self.get_connection_path_by_ssid(ssid)
        if path:
            await self.delete_connection_path(path)
        else:
            logging.debug(f"SSID '{ssid}' not found among saved connections")

    async def delete_connection_path(self, path):
        try:
            await NetworkConnectionSettings(path).delete()
            logging.info(f"Deleted connection path: {path}")
        except Exception as e:
            logging.exception(f"Failed to delete connection path: {path} - {e}")
            return {
                "error": "deletion_failed",
                "message": _("Failed to delete") + f"\n{e}",
            }

    async def get_connection_path_by_ssid(self, ssid):
        existing_networks = await self.settings.list_connections()
        for connection_path in existing_networks:
            try:
                connection_settings = await NetworkConnectionSettings(
                    connection_path
                ).get_settings()
            except exceptions.NetworkManagerUnknownDeviceError:
                continue
            wireless = connection_settings.get("802-11-wireless")
            if wireless and wireless.get("ssid") and wireless["ssid"][1].decode() == ssid:
                return connection_path
        return None

    async def connect(self, ssid):
        target_connection = await self.get_connection_path_by_ssid(ssid)
        if not target_connection:
            self.popup(f"SSID '{ssid}' not found among saved connections")
            return None
        logging.info(f"{ssid}: {_('Starting WiFi Association')}")
        try:
            con = NetworkConnectionSettings(target_connection)
            settings = await con.get_settings()

            if "802-11-wireless" in settings and settings["802-11-wireless"].get("mode") == (
                "s",
                "infrastructure",
            ):
                settings["connection"]["interface-name"] = (
                    "s",
                    await self._wifi_interface(),
                )
                await con.update(settings)

            await self.nm.activate_connection(target_connection)
            return target_connection
        except Exception as e:
            logging.exception("Unexpected error")
            self.popup(f"Unexpected error: {e}")
            return None

    # -- wifi toggle -------------------------------------------------------

    async def toggle_wifi(self, enable):
        if self.nm is None:
            return
        try:
            await self.nm.wireless_enabled.set_async(enable)
        except Exception as e:
            logging.exception("Failed to toggle wifi")
            self.popup(f"Unexpected error: {e}")

    async def is_wifi_enabled(self):
        return await self.nm.wireless_enabled

    # -- state monitoring (signal driven) ----------------------------------

    def set_connection_monitoring(self, enable):
        """Start or stop signal-driven connection-state monitoring."""
        self.monitor_connection = enable
        if enable:
            self._start_monitor()
        elif self._monitor_task is not None:
            self._monitor_task.cancel()
            self._monitor_task = None

    def _start_monitor(self):
        if self._destroyed:
            return
        if self._monitor_task is not None or self.wlan_device is None:
            return
        self._monitor_task = self.schedule(self._monitor_connection_status())

    async def _monitor_connection_status(self):
        """Drive connection popups from the wireless device state signal."""
        task = asyncio.current_task()
        device = self.wlan_device
        if device is None:
            if self._monitor_task is task:
                self._monitor_task = None
            return
        try:
            self.wifi_state = await device.state
        except exceptions.NetworkManagerUnknownDeviceError:
            self.wifi_state = None
        self._last_phase_message = None
        try:
            async for new_state, old_state, reason in device.state_changed.catch():
                await self._apply_state(new_state)
        except exceptions.NetworkManagerUnknownDeviceError:
            return
        finally:
            if self._monitor_task is task:
                self._monitor_task = None

    async def _apply_state(self, state):
        if self.wifi_state == state:
            return
        if self.wifi_state is None:
            self.wifi_state = state
            return

        self.wifi_state = state

        for cb in list(self._state_callbacks):
            try:
                cb(state)
            except Exception:
                logging.exception("Wi-Fi state callback failed")

        if state in (enums.DeviceState.DISCONNECTED, enums.DeviceState.DEACTIVATING):
            self._log_phase(_("Network disconnected"))
        elif state == enums.DeviceState.FAILED:
            self.popup(_("Connection failed"), 3)
        elif state in (enums.DeviceState.PREPARE, enums.DeviceState.CONFIG):
            self._log_phase(_("Connecting"))
        elif state in (
            enums.DeviceState.IP_CONFIG,
            enums.DeviceState.IP_CHECK,
            enums.DeviceState.SECONDARIES,
        ):
            self._log_phase(_("Getting IP address"))
        elif state == enums.DeviceState.ACTIVATED:
            self._log_phase(_("Network connected"))

    def _log_phase(self, message):
        # NM can re-emit a state (e.g. an association retry walks PREPARE/CONFIG
        # again), so log each phase once instead of once per emitted state.
        if message == self._last_phase_message:
            return
        self._last_phase_message = message
        logging.info(message)
