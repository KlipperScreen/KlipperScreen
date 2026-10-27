import logging
from dataclasses import dataclass
from typing import Callable, Optional
from uuid import uuid4

import gi

gi.require_version("NM", "1.0")
from gi.repository import NM, Gio, GLib, GObject


@dataclass(frozen=True)
class WirelessDevice:
    interface: str
    wireless: bool
    state: int
    ip_address: str


@dataclass(frozen=True)
class AccessPoint:
    ssid: str
    bssid: str
    signal_level: int
    frequency: str
    channel: str
    security: str
    known: bool
    connected: bool


@dataclass(frozen=True)
class NetworkSnapshot:
    devices: tuple = ()
    networks: tuple = ()
    interface: Optional[str] = None
    wireless_enabled: bool = False
    scanning: bool = False
    last_scan: int = -1


@dataclass(frozen=True)
class OperationResult:
    operation: str
    success: bool
    message: str
    error: Optional[str] = None


APSecurity = getattr(NM, "80211ApSecurityFlags")
SECURITY_LABELS = (
    (APSecurity.PAIR_WEP40, "WEP"),
    (APSecurity.PAIR_WEP104, "WEP"),
    (APSecurity.PAIR_TKIP, "TKIP"),
    (APSecurity.PAIR_CCMP, "AES"),
    (APSecurity.GROUP_WEP40, "WEP"),
    (APSecurity.GROUP_WEP104, "WEP"),
    (APSecurity.GROUP_TKIP, "TKIP"),
    (APSecurity.GROUP_CCMP, "AES"),
    (APSecurity.KEY_MGMT_PSK, "WPA-PSK"),
    (APSecurity.KEY_MGMT_802_1X, "802.1x"),
    (APSecurity.KEY_MGMT_SAE, "WPA-SAE"),
    (APSecurity.KEY_MGMT_OWE, "OWE"),
    (APSecurity.KEY_MGMT_OWE_TM, "OWE-TM"),
    (APSecurity.KEY_MGMT_EAP_SUITE_B_192, "WPA3-B192"),
)


def get_encryption(flags: int) -> str:
    if not flags:
        return "Open"
    labels = []
    for flag, label in SECURITY_LABELS:
        if flags & flag and label not in labels:
            labels.append(label)
    return " ".join(labels)


def wifi_channel(frequency: int) -> tuple:
    if frequency == 2484:
        return "2.4", "14"
    if 2412 <= frequency <= 2472:
        return "2.4", str((frequency - 2407) // 5)
    if 3657.5 <= frequency <= 3692.5:
        return "3", str((frequency - 3000) // 5)
    if 4915 <= frequency <= 4980:
        return "5", str((frequency - 4000) // 5)
    if 5035 <= frequency <= 5885:
        return "5", str((frequency - 5000) // 5)
    if 6455 <= frequency <= 7115:
        return "6", str((frequency - 5950) // 5)
    return "?", "?"


class NetworkManagerClient:
    SCAN_INTERVAL = 15
    SCAN_TIMEOUT = 25
    SCAN_BACKOFF = 20

    def __init__(
        self,
        on_snapshot: Callable[[NetworkSnapshot], None],
        on_operation: Callable[[OperationResult], None],
        client_factory=None,
        client_finish=None,
        main_context=None,
        clock=None,
    ):
        self.on_snapshot = on_snapshot
        self.on_operation = on_operation
        self.client_factory = client_factory or NM.Client.new_async
        self.client_finish = client_finish or NM.Client.new_finish
        self.main_context = main_context or GLib.MainContext.default()
        self.clock = clock or (lambda: GLib.get_monotonic_time() / 1_000_000)
        self.client = None
        self.interface = None
        self.snapshot = NetworkSnapshot()
        self.active = False
        self.generation = 0
        self.starting = False
        self.scan_requested = False
        self.scan_after_ready = False
        self.scan_in_flight = False
        self.scan_state = "IDLE"
        self.scan_baseline = -1
        self.next_scan_at = 0.0
        self.pending = set()
        self.object_handlers = {}
        self.device_states = {}
        self.ip_configs = {}
        self.snapshot_source = None
        self.scan_timeout_source = None
        self.scan_retry_source = None

    def start(self):
        self.active = True
        self.generation += 1
        if self.client is not None:
            self._track_objects()
            self._schedule_snapshot()
            return
        if self.starting:
            return
        self.starting = True
        self._call(
            NM.Client,
            "new_finish",
            self._client_ready,
            "initialization",
            factory=True,
        )

    def activate(self):
        self.start()
        self.request_scan()

    def deactivate(self):
        self.active = False
        self._invalidate()
        for obj in tuple(self.object_handlers):
            self._untrack(obj)
        self.ip_configs.clear()

    def _invalidate(self):
        self.generation += 1
        for cancellable in tuple(self.pending):
            cancellable.cancel()
        self.pending.clear()
        self._cancel_source("snapshot_source")
        self._cancel_source("scan_timeout_source")
        self._cancel_source("scan_retry_source")
        self.scan_requested = False
        self.scan_in_flight = False
        self.scan_state = "IDLE"
        self.starting = False

    def _is_current(self, generation):
        return self.active and generation == self.generation

    def _source(self, delay, callback, *args):
        source = GLib.timeout_source_new(max(0, round(delay * 1000)))
        source.set_priority(GLib.PRIORITY_DEFAULT)
        source.set_callback(lambda *_: callback(*args))
        source.attach(self.main_context)
        return source

    def _idle(self, callback, *args):
        source = GLib.idle_source_new()
        source.set_callback(lambda *_: callback(*args))
        source.attach(self.main_context)
        return source

    def _cancel_source(self, name):
        source = getattr(self, name)
        if source is not None:
            source.destroy()
            setattr(self, name, None)

    def _call(self, source, finish, done, operation, args=(), factory=False, method=None):
        generation = self.generation
        cancellable = Gio.Cancellable()
        self.pending.add(cancellable)

        def ready(_source, result):
            self.pending.discard(cancellable)
            if not self._is_current(generation):
                return
            try:
                value = self.client_finish(result) if factory else getattr(source, finish)(result)
            except Exception as error:
                self._failed(operation, error)
                return
            if self._is_current(generation):
                done(value)

        try:
            if factory:
                self.client_factory(cancellable, ready)
            else:
                getattr(source, method or operation)(*args, cancellable, ready)
        except Exception as error:
            self.pending.discard(cancellable)
            if self._is_current(generation):
                self._failed(operation, error)

    def _report(self, result):
        if self.active:
            self.on_operation(result)

    def _completed(self, operation):
        self._schedule_snapshot()
        self._report(OperationResult(operation, True, ""))

    def _failed(self, operation, error):
        if operation == "scan":
            self._scan_finished(error=error)
            return
        if operation == "initialization":
            self.starting = False
        logging.info("NetworkManager %s failed: %s", operation, error)
        message = str(error)
        lowered = message.lower()
        code = None
        if "psk" in lowered or "password" in lowered:
            message = _("Invalid password")
            code = "psk_invalid"
        elif "notauthorized" in lowered or "not authorized" in lowered:
            message = _("Insufficient privileges")
            code = "insufficient_privileges"
        if operation in ("update2", "add_connection_async", "activate_connection_async"):
            operation = "connect"
        self._report(OperationResult(operation, False, message, code))
        self._schedule_snapshot()

    def _client_ready(self, client):
        self.starting = False
        self.client = client
        self._connect(client, "notify::nm-running", self._changed)
        self._connect(client, "notify::wireless-enabled", self._changed)
        self._connect(client, "notify::primary-connection", self._changed)
        for signal in (
            "device-added",
            "device-removed",
            "connection-added",
            "connection-removed",
            "active-connection-added",
            "active-connection-removed",
        ):
            self._connect(client, signal, self._objects_changed)
        self._track_objects()
        self._schedule_snapshot()

    def _track_objects(self):
        for device in self.client.get_devices() or ():
            self._track_device(device)
        for connection in self.client.get_connections() or ():
            self._track_connection(connection)

    def _connect(self, obj, signal, callback):
        handler = obj.connect(signal, callback)
        self.object_handlers.setdefault(obj, []).append(handler)

    def _untrack(self, obj):
        for handler in self.object_handlers.pop(obj, ()):
            GObject.Object.disconnect(obj, handler)

    def _objects_changed(self, _client, obj):
        if obj in self.object_handlers:
            if hasattr(obj, "get_access_points"):
                for ap in obj.get_access_points() or ():
                    self._untrack(ap)
            self._clear_ip_config(obj)
            self._untrack(obj)
        elif hasattr(obj, "get_device_type"):
            self._track_device(obj)
        elif hasattr(obj, "get_connection_type"):
            self._track_connection(obj)
        self._changed()

    def _track_device(self, device):
        if device not in self.object_handlers:
            self._connect(device, "notify::state", self._state_changed)
            self._connect(device, "notify::ip4-config", self._ip_config_changed)
            self._track_ip_config(device)
            if device.get_device_type() == NM.DeviceType.WIFI:
                self._connect(device, "notify::active-access-point", self._changed)
                self._connect(device, "notify::last-scan", self._last_scan_changed)
                self._connect(device, "access-point-added", self._ap_added)
                self._connect(device, "access-point-removed", self._ap_removed)
                for ap in device.get_access_points() or ():
                    self._track_ap(ap)

    def _ip_config_changed(self, device, _param=None):
        self._track_ip_config(device)
        self._changed()

    def _track_ip_config(self, device):
        config = device.get_ip4_config()
        previous = self.ip_configs.get(device)
        if config == previous:
            return
        self._clear_ip_config(device)
        self.ip_configs[device] = config
        if config is not None:
            self._connect(config, "notify::addresses", self._changed)
            self._connect(config, "notify::address-data", self._changed)

    def _clear_ip_config(self, device):
        config = self.ip_configs.pop(device, None)
        if config is not None:
            self._untrack(config)

    def _track_ap(self, ap):
        if ap not in self.object_handlers:
            self._connect(ap, "notify::strength", self._changed)

    def _track_connection(self, connection):
        if connection not in self.object_handlers:
            self._connect(connection, "changed", self._changed)

    def _ap_added(self, _device, ap):
        self._track_ap(ap)
        self._changed()

    def _ap_removed(self, _device, ap):
        self._untrack(ap)
        self._changed()

    def _changed(self, *_args):
        if self.active and self.client is not None:
            self._schedule_snapshot()

    def _state_changed(self, device, _param=None, schedule=True):
        interface = device.get_iface()
        state = device.get_state()
        previous = self.device_states.get(interface)
        self.device_states[interface] = state
        if self.active and interface == self.interface and previous != state:
            logging.debug("Wi-Fi state changed: %s %s", state, device.get_state_reason())
            if previous is not None:
                if state in (NM.DeviceState.PREPARE, NM.DeviceState.CONFIG):
                    self._report(OperationResult("state", True, _("Connecting")))
                elif state in (
                    NM.DeviceState.IP_CONFIG,
                    NM.DeviceState.IP_CHECK,
                    NM.DeviceState.SECONDARIES,
                ):
                    self._report(OperationResult("state", True, _("Getting IP address")))
                elif state == NM.DeviceState.ACTIVATED:
                    self._report(OperationResult("state", True, _("Network connected")))
                elif state in (NM.DeviceState.DISCONNECTED, NM.DeviceState.DEACTIVATING):
                    self._report(OperationResult("state", True, _("Network disconnected")))
                elif state == NM.DeviceState.FAILED:
                    self._report(OperationResult("state", False, _("Connection failed")))
        if schedule:
            self._changed()

    def select_interface(self, interface):
        if self.client is None:
            self.interface = interface
            return True
        device = self.client.get_device_by_iface(interface)
        if device is None or device.get_device_type() not in (
            NM.DeviceType.WIFI,
            NM.DeviceType.ETHERNET,
        ):
            return False
        if interface == self.interface:
            return True
        if (
            device.get_device_type() == NM.DeviceType.WIFI
            and device.get_state() == NM.DeviceState.UNMANAGED
        ):
            self._report(
                OperationResult(
                    "interface",
                    False,
                    _("%s is not managed by NetworkManager") % interface,
                )
            )
            return False
        self._invalidate()
        self.active = True
        self.interface = interface
        self.next_scan_at = self.clock()
        self._schedule_snapshot()
        self.request_scan()
        return True

    def _selected_device(self):
        if self.client is None:
            return None
        if self.interface:
            return self.client.get_device_by_iface(self.interface)
        return None

    def _wireless_device(self):
        device = self._selected_device()
        if device is not None and device.get_device_type() == NM.DeviceType.WIFI:
            return device
        return None

    def request_scan(self):
        if not self.active:
            return
        if self.client is None:
            self.scan_after_ready = True
            return
        device = self._wireless_device()
        if device is None or not self.client.get_property("wireless-enabled"):
            return
        if self.scan_in_flight:
            self.scan_requested = True
            return
        self.scan_requested = True
        self._begin_scan()

    def _begin_scan(self):
        if not self.active or self.client is None:
            return
        device = self._wireless_device()
        if device is None or not self.client.get_property("wireless-enabled"):
            self.scan_requested = False
            self.scan_state = "IDLE"
            self._schedule_snapshot()
            return
        if not NM.DeviceState.DISCONNECTED <= device.get_state() <= NM.DeviceState.ACTIVATED:
            logging.debug("Wi-Fi interface not ready: %s", device.get_state())
            self.scan_requested = False
            self.scan_state = "IDLE"
            self._schedule_snapshot()
            return
        remaining = self.next_scan_at - self.clock()
        if remaining > 0:
            self.scan_state = "REQUESTED"
            if not self.scan_retry_source:
                self.scan_retry_source = self._source(remaining, self._scan_retry, self.generation)
                self._schedule_snapshot()
            return
        self._cancel_source("scan_retry_source")
        self.scan_requested = False
        self.scan_in_flight = True
        self.scan_state = "SCANNING"
        self.scan_baseline = device.get_last_scan()
        self.next_scan_at = self.clock() + self.SCAN_INTERVAL
        self._cancel_source("scan_timeout_source")
        self.scan_timeout_source = self._source(
            self.SCAN_TIMEOUT, self._scan_timed_out, self.generation
        )
        self._schedule_snapshot()
        self._call(
            device,
            "request_scan_finish",
            self._scan_accepted,
            "scan",
            method="request_scan_async",
        )

    def _scan_retry(self, generation):
        self.scan_retry_source = None
        if self._is_current(generation) and self.scan_requested:
            self._begin_scan()
        return False

    def _scan_timed_out(self, generation):
        self.scan_timeout_source = None
        if self._is_current(generation) and self.scan_in_flight:
            self._scan_finished(error=TimeoutError(_("Scan timed out")))
        return False

    def _scan_accepted(self, _result):
        if not self.scan_in_flight:
            return
        device = self._wireless_device()
        if device is not None and device.get_last_scan() != self.scan_baseline:
            self._scan_finished()

    def _last_scan_changed(self, device, _param):
        if self.scan_in_flight and device == self._wireless_device():
            if device.get_last_scan() != self.scan_baseline:
                self._scan_finished()
        elif self.scan_requested and not self.scan_in_flight:
            self.scan_requested = False
            self._cancel_source("scan_retry_source")
            self.scan_state = "IDLE"
        self._changed()

    def _scan_finished(self, error=None):
        self._cancel_source("scan_timeout_source")
        self.scan_in_flight = False
        self.scan_state = "SNAPSHOTTING"
        if error is not None:
            message = str(error)
            if "NotAllowed" in message:
                self.next_scan_at = max(self.next_scan_at, self.clock() + self.SCAN_BACKOFF)
                self.scan_requested = True
                logging.debug("Wi-Fi scan throttled by NetworkManager")
            else:
                logging.info("Wi-Fi scan failed: %s", error)
                self._report(OperationResult("scan", False, message))
        self._schedule_snapshot()

    def _schedule_snapshot(self):
        if self.active and self.client is not None and not self.snapshot_source:
            self.snapshot_source = self._idle(self._publish_snapshot, self.generation)

    def _publish_snapshot(self, generation):
        self.snapshot_source = None
        if not self._is_current(generation):
            return False
        devices = tuple(
            self._device_snapshot(device)
            for device in self.client.get_devices() or ()
            if device.get_device_type() in (NM.DeviceType.WIFI, NM.DeviceType.ETHERNET)
            and device.get_iface()
        )
        interfaces = {device.interface for device in devices}
        if self.interface not in interfaces:
            self.interface = self._default_interface(devices)
        if self.scan_after_ready:
            self.scan_after_ready = False
            self.request_scan()
        device = self._wireless_device()
        wireless_enabled = self.client.get_property("wireless-enabled")
        networks = self._network_snapshots(device) if device and wireless_enabled else ()
        self.snapshot = NetworkSnapshot(
            devices=devices,
            networks=networks,
            interface=self.interface,
            wireless_enabled=wireless_enabled,
            scanning=self.scan_in_flight or self.scan_requested,
            last_scan=device.get_last_scan() if device else -1,
        )
        if device is not None:
            self._state_changed(device, schedule=False)
        if not self.scan_in_flight:
            self.scan_state = "IDLE"
        self.on_snapshot(self.snapshot)
        if self.scan_requested and not self.scan_in_flight:
            self._begin_scan()
        return False

    def _default_interface(self, devices):
        primary = self.client.get_primary_connection()
        if primary is not None:
            for device in primary.get_devices() or ():
                interface = device.get_iface()
                if interface in {item.interface for item in devices}:
                    return interface
        return next(
            (item.interface for item in devices if item.wireless),
            next((item.interface for item in devices), None),
        )

    @staticmethod
    def _device_snapshot(device):
        address = "?"
        config = device.get_ip4_config()
        if config is not None:
            addresses = config.get_addresses() or ()
            if addresses:
                address = addresses[0].get_address()
        return WirelessDevice(
            interface=device.get_iface(),
            wireless=device.get_device_type() == NM.DeviceType.WIFI,
            state=int(device.get_state()),
            ip_address=address,
        )

    def _network_snapshots(self, device):
        active = device.get_active_access_point()
        connected_bssid = active.get_bssid() if active is not None else None
        saved_ssids = {
            self._connection_ssid(connection) for connection in self.client.get_connections() or ()
        }
        saved_ssids.discard(None)
        networks = []
        for ap in device.get_access_points() or ():
            ssid_bytes = ap.get_ssid()
            bssid = ap.get_bssid()
            if ssid_bytes is None or bssid is None:
                continue
            ssid = ssid_bytes.get_data().decode("utf-8", errors="replace")
            if not ssid:
                continue
            frequency, channel = wifi_channel(ap.get_frequency())
            security = get_encryption(ap.get_rsn_flags() or ap.get_wpa_flags() or ap.get_flags())
            networks.append(
                AccessPoint(
                    ssid=ssid,
                    bssid=bssid,
                    signal_level=ap.get_strength(),
                    frequency=frequency,
                    channel=channel,
                    security=security,
                    known=ssid in saved_ssids,
                    connected=bssid == connected_bssid,
                )
            )
        networks.sort(key=lambda ap: (not ap.connected, -ap.signal_level, ap.ssid, ap.bssid))
        return tuple(networks)

    @staticmethod
    def _connection_ssid(connection):
        if connection.get_connection_type() != NM.SETTING_WIRELESS_SETTING_NAME:
            return None
        setting = connection.get_setting_wireless()
        value = setting.get_ssid() if setting is not None else None
        if value is None:
            return None
        return value.get_data().decode("utf-8", errors="replace")

    def _profile(self, ssid):
        if self.client is None:
            return None
        for connection in self.client.get_connections() or ():
            if connection.get_connection_type() != NM.SETTING_WIRELESS_SETTING_NAME:
                continue
            setting = connection.get_setting_wireless()
            value = setting.get_ssid() if setting is not None else None
            if value is not None and value.get_data().decode("utf-8", errors="replace") == ssid:
                return connection
        return None

    def _access_point(self, ssid):
        return next((ap for ap in self.snapshot.networks if ap.ssid == ssid), None)

    def connect(self, ssid, psk=None, eap_method=None, identity="", phase2=None):
        profile = self._profile(ssid)
        if profile is not None and psk is None:
            self._report(OperationResult("connect", True, _("Starting WiFi Association")))
            self._update_and_activate(profile)
            return True
        try:
            connection = self._build_connection(ssid, psk or "", eap_method, identity, phase2)
        except Exception as error:
            self._failed("connect", error)
            return False
        self._report(OperationResult("connect", True, _("Starting WiFi Association")))
        if profile is not None:
            self._delete_then_add(profile, connection)
        else:
            self._add_then_activate(connection)
        return True

    def _update_and_activate(self, profile):
        draft = NM.SimpleConnection.new()
        draft.replace_settings_from_connection(profile)
        draft.get_setting_connection().set_property(
            NM.SETTING_CONNECTION_INTERFACE_NAME, self.interface
        )
        self._call(
            profile,
            "update2_finish",
            lambda _result: self._activate(profile),
            "update2",
            args=(
                draft.to_dbus(NM.ConnectionSerializationFlags.ALL),
                NM.SettingsUpdate2Flags.TO_DISK,
                None,
            ),
        )

    def _delete_then_add(self, profile, connection):
        self._call(
            profile,
            "delete_finish",
            lambda _result: self._add_then_activate(connection),
            "delete_async",
        )

    def _add_then_activate(self, connection):
        self._call(
            self.client,
            "add_connection_finish",
            self._activate,
            "add_connection_async",
            args=(connection, True),
        )

    def _activate(self, connection):
        device = self._wireless_device()
        if device is None:
            self._report(OperationResult("connect", False, _("Network not found")))
            return
        self._call(
            self.client,
            "activate_connection_finish",
            lambda _result: self._schedule_snapshot(),
            "activate_connection_async",
            args=(connection, device, None),
        )

    def _build_connection(self, ssid, psk, eap_method, identity, phase2):
        ap = self._access_point(ssid)
        device = self._wireless_device()
        if ap is None or device is None:
            raise ValueError(_("Network not found"))
        if "WPA-PSK" in ap.security and not (
            8 <= len(psk) <= 63
            or len(psk) == 64
            and all(character in "0123456789abcdefABCDEF" for character in psk)
        ):
            raise ValueError(_("Invalid password"))
        connection = NM.SimpleConnection.new()
        settings = NM.SettingConnection.new()
        settings.set_property(NM.SETTING_CONNECTION_ID, ssid)
        settings.set_property(NM.SETTING_CONNECTION_UUID, str(uuid4()))
        settings.set_property(NM.SETTING_CONNECTION_TYPE, NM.SETTING_WIRELESS_SETTING_NAME)
        settings.set_property(NM.SETTING_CONNECTION_INTERFACE_NAME, self.interface)
        connection.add_setting(settings)
        wireless = NM.SettingWireless.new()
        wireless.set_property(NM.SETTING_WIRELESS_MODE, NM.SETTING_WIRELESS_MODE_INFRA)
        wireless.set_property(NM.SETTING_WIRELESS_SSID, GLib.Bytes.new(ssid.encode()))
        connection.add_setting(wireless)
        security = NM.SettingWirelessSecurity.new()
        if ap.security == "Open" or "OWE" in ap.security:
            security.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "none")
            if "OWE" in ap.security:
                security.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "owe")
        elif "802.1x" in ap.security or "WPA3-B192" in ap.security:
            key_mgmt = "wpa-eap-suite-b-192" if "WPA3-B192" in ap.security else "wpa-eap"
            security.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, key_mgmt)
            enterprise = NM.Setting8021x.new()
            enterprise.set_property(NM.SETTING_802_1X_EAP, [eap_method] if eap_method else [])
            enterprise.set_property(NM.SETTING_802_1X_IDENTITY, identity)
            enterprise.set_property(NM.SETTING_802_1X_PASSWORD, psk)
            if phase2:
                if eap_method == "ttls":
                    enterprise.set_property(NM.SETTING_802_1X_PHASE2_AUTHEAP, phase2)
                else:
                    enterprise.set_property(NM.SETTING_802_1X_PHASE2_AUTH, phase2)
            connection.add_setting(enterprise)
        elif "WEP" in ap.security:
            security.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "none")
            security.set_property(NM.SETTING_WIRELESS_SECURITY_WEP_KEY_TYPE, 2)
            security.set_property(NM.SETTING_WIRELESS_SECURITY_WEP_KEY0, psk)
            security.set_property(NM.SETTING_WIRELESS_SECURITY_AUTH_ALG, "shared")
        else:
            key_mgmt = "sae" if "WPA-SAE" in ap.security else "wpa-psk"
            security.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, key_mgmt)
            security.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, psk)
        connection.add_setting(security)
        for setting_type in (NM.SettingIP4Config, NM.SettingIP6Config):
            setting = setting_type.new()
            setting.set_property(NM.SETTING_IP_CONFIG_METHOD, NM.SETTING_IP4_CONFIG_METHOD_AUTO)
            connection.add_setting(setting)
        connection.verify()
        return connection

    def delete_network(self, ssid):
        profile = self._profile(ssid)
        if profile is None:
            self._report(OperationResult("delete", False, _("Network not found")))
            return False
        self._call(
            profile,
            "delete_finish",
            lambda _result: self._completed("delete"),
            "delete_async",
        )
        return True

    def disconnect(self):
        device = self._wireless_device()
        if device is None:
            return False
        active = next(
            (
                connection
                for connection in self.client.get_active_connections() or ()
                if device in (connection.get_devices() or ())
            ),
            None,
        )
        if active is None:
            self._report(OperationResult("disconnect", False, _("Network disconnected")))
            return False
        self._call(
            self.client,
            "deactivate_connection_finish",
            lambda _result: self._completed("disconnect"),
            "deactivate_connection_async",
            args=(active,),
        )
        return True

    def set_wireless_enabled(self, enabled):
        if self.client is None:
            return False
        self._call(
            self.client,
            "dbus_set_property_finish",
            lambda _result: self._schedule_snapshot(),
            "dbus_set_property",
            args=(
                NM.DBUS_PATH,
                NM.DBUS_INTERFACE,
                "WirelessEnabled",
                GLib.Variant("b", enabled),
                -1,
            ),
        )
        return True
