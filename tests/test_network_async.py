import builtins
import dataclasses
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

builtins._ = lambda text: text
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gi

gi.require_version("NM", "1.0")
from gi.repository import NM, GLib, GObject

from ks_includes.gio_nm import NetworkManagerClient


class FakeAP(GObject.Object):
    def __init__(self, ssid, bssid, strength=70, security="WPA-PSK"):
        super().__init__()
        self.ssid = ssid
        self.bssid = bssid
        self.strength = strength
        self.flags = (
            int(getattr(NM, "80211ApSecurityFlags").KEY_MGMT_PSK) if security != "Open" else 0
        )

    def get_ssid(self):
        return GLib.Bytes.new(self.ssid.encode()) if self.ssid is not None else None

    def get_bssid(self):
        return self.bssid

    def get_strength(self):
        return self.strength

    def get_frequency(self):
        return 2412

    def get_flags(self):
        return 1 if self.flags else 0

    def get_wpa_flags(self):
        return 0

    def get_rsn_flags(self):
        return self.flags


class FakeDevice(GObject.Object):
    __gsignals__ = {
        "access-point-added": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "access-point-removed": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, interface, aps=(), wireless=True):
        super().__init__()
        self.interface = interface
        self.aps = list(aps)
        self.wireless = wireless
        self.active_ap = self.aps[0] if self.aps else None
        self.last_scan = -1
        self.scan_callbacks = []
        self.scan_finishes = 0
        self.state = NM.DeviceState.DISCONNECTED
        self.address = None

    def get_iface(self):
        return self.interface

    def get_device_type(self):
        return NM.DeviceType.WIFI if self.wireless else NM.DeviceType.ETHERNET

    def get_state(self):
        return self.state

    def get_state_reason(self):
        return NM.DeviceStateReason.NONE

    def get_ip4_config(self):
        return self.address

    def get_access_points(self):
        return self.aps

    def get_active_access_point(self):
        return self.active_ap

    def get_last_scan(self):
        return self.last_scan

    def request_scan_async(self, cancellable, callback):
        self.scan_callbacks.append((cancellable, callback))

    def request_scan_finish(self, result):
        self.scan_finishes += 1
        if isinstance(result, Exception):
            raise result

    def complete_last_scan(self, timestamp):
        self.last_scan = timestamp
        self.manager._last_scan_changed(self, None)


class FakeActiveConnection(GObject.Object):
    state = GObject.Property(type=int, default=int(NM.ActiveConnectionState.ACTIVATING))

    def get_state(self):
        return self.state


class FakeClient(GObject.Object):
    __gsignals__ = {
        name: (GObject.SignalFlags.RUN_FIRST, None, (object,))
        for name in (
            "device-added",
            "device-removed",
            "connection-added",
            "connection-removed",
            "active-connection-added",
            "active-connection-removed",
        )
    }

    def __init__(self, devices, profiles=()):
        super().__init__()
        self.devices = list(devices)
        self.profiles = list(profiles)
        self.wireless = True
        self.calls = []
        self.activate_callbacks = []
        self.add_callbacks = []
        self.property_callbacks = []

    def get_devices(self):
        return self.devices

    def get_device_by_iface(self, interface):
        return next((device for device in self.devices if device.interface == interface), None)

    def get_connections(self):
        return self.profiles

    def get_primary_connection(self):
        return None

    def get_active_connections(self):
        return getattr(self, "active_connections", [])

    def deactivate_connection_async(self, active, cancellable, callback):
        self.calls.append("deactivate")
        self.deactivate_callback = callback

    def deactivate_connection_finish(self, result):
        return None

    def get_property(self, name):
        if name == "wireless-enabled":
            return self.wireless
        raise AttributeError(name)

    def add_connection_async(self, connection, save, cancellable, callback):
        self.calls.append("add")
        self.add_callbacks.append((connection, callback))

    def add_connection_finish(self, result):
        return result

    def activate_connection_async(self, connection, device, specific, cancellable, callback):
        self.calls.append("activate")
        self.activate_callbacks.append((connection, device, callback))

    def activate_connection_finish(self, result):
        if isinstance(result, Exception):
            raise result
        return result or FakeActiveConnection()

    def add_and_activate_connection_async(
        self, connection, device, specific, cancellable, callback
    ):
        self.calls.append("add-and-activate")
        self.activate_callbacks.append((connection, device, callback))

    add_and_activate_connection_finish = activate_connection_finish

    def dbus_set_property(self, path, interface, name, value, timeout, cancellable, callback):
        self.calls.append(("property", path, interface, name, value.get_boolean()))
        self.property_callbacks.append(callback)

    def dbus_set_property_finish(self, result):
        if isinstance(result, Exception):
            raise result


def make_profile(ssid):
    profile = NM.SimpleConnection.new()
    setting = NM.SettingConnection.new()
    setting.set_property("id", ssid)
    setting.set_property("uuid", "12345678-1234-1234-1234-123456789012")
    setting.set_property("type", "802-11-wireless")
    profile.add_setting(setting)
    wireless = NM.SettingWireless.new()
    wireless.set_property("ssid", GLib.Bytes.new(ssid.encode()))
    profile.add_setting(wireless)
    profile.updates = []
    profile.deletions = 0

    def update2(self, settings, flags, args, cancellable, callback):
        self.updates.append((settings, callback))

    def update2_finish(self, result):
        if isinstance(result, Exception):
            raise result

    def delete_async(self, cancellable, callback):
        self.deletions += 1
        self.delete_callback = callback

    def delete_finish(self, result):
        if isinstance(result, Exception):
            raise result

    profile.update2 = types.MethodType(update2, profile)
    profile.update2_finish = types.MethodType(update2_finish, profile)
    profile.delete_async = types.MethodType(delete_async, profile)
    profile.delete_finish = types.MethodType(delete_finish, profile)
    return profile


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class AsyncTests(unittest.TestCase):
    def setUp(self):
        self.context = GLib.MainContext.new()
        self.context.push_thread_default()
        self.clock = Clock()
        self.device = FakeDevice(
            "wlan0", [FakeAP(f"Network-{i}", f"00:11:22:33:44:{i:02x}", i) for i in range(19)]
        )
        self.device.manager = self.manager if hasattr(self, "manager") else None
        self.profiles = [make_profile(f"Network-{i}") for i in range(5)]
        self.client = FakeClient([self.device], self.profiles)
        self.factory_callbacks = []
        self.factory_finishes = []
        self.snapshots = []
        self.results = []
        self.manager = NetworkManagerClient(
            self.snapshots.append,
            self.results.append,
            client_factory=lambda cancellable, callback: self.factory_callbacks.append(
                (cancellable, callback)
            ),
            client_finish=lambda result: self.factory_finishes.append(result) or result,
            main_context=self.context,
            clock=self.clock,
        )

    def tearDown(self):
        self.manager.deactivate()
        self.context.pop_thread_default()

    def drain(self):
        count = 0
        while self.context.pending():
            self.context.iteration(False)
            count += 1
            if count > 30:
                self.fail("Idle snapshot coalescing did not settle")

    def resolve_factory(self):
        cancellable, callback = self.factory_callbacks.pop(0)
        callback(None, self.client)

    def start(self):
        self.device.manager = self.manager
        self.manager.activate()
        self.assertEqual(len(self.factory_callbacks), 1)
        self.resolve_factory()
        self.drain()
        self.assertTrue(self.snapshots)

    def accept_scan(self, error=None):
        _cancellable, callback = self.device.scan_callbacks.pop(0)
        callback(self.device, error)

    def test_cache_first_and_single_profile_index(self):
        self.manager.activate()
        self.assertEqual(self.snapshots, [])
        reads = 0
        for profile in self.profiles:
            getter = profile.get_setting_wireless

            def counted(getter=getter):
                nonlocal reads
                reads += 1
                return getter()

            profile.get_setting_wireless = counted
        self.resolve_factory()
        self.drain()
        self.assertEqual(len(self.snapshots[-1].networks), 19)
        self.assertEqual(sum(ap.known for ap in self.snapshots[-1].networks), 5)
        self.assertEqual(reads, 5 * len(self.snapshots))
        self.assertEqual(len(self.device.scan_callbacks), 1)
        self.assertTrue(self.snapshots[-1].scanning)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.snapshots[-1].interface = "other"
        count = len(self.snapshots)
        self.drain()
        self.assertEqual(len(self.snapshots), count)

    def test_scan_completion_and_coalescing(self):
        self.start()
        self.manager.request_scan()
        self.manager.request_scan()
        self.assertEqual(len(self.device.scan_callbacks), 1)
        self.accept_scan()
        self.assertTrue(self.manager.scan_in_flight)
        self.device.complete_last_scan(123)
        self.drain()
        self.assertFalse(self.manager.scan_in_flight)
        self.assertTrue(self.manager.scan_requested)
        self.assertEqual(self.snapshots[-1].last_scan, 123)
        self.clock.now = 15.0
        self.manager._cancel_source("scan_retry_source")
        self.manager._begin_scan()
        self.assertEqual(len(self.device.scan_callbacks), 1)

    def test_not_allowed_backs_off(self):
        self.start()
        self.accept_scan(RuntimeError("org.freedesktop.NetworkManager.Device.ScanNotAllowed"))
        self.drain()
        self.assertGreaterEqual(self.manager.next_scan_at, 20.0)
        self.assertFalse(any(not result.success for result in self.results))

    def test_stale_scan_result_is_not_finished_or_rendered(self):
        self.start()
        cancellable, callback = self.device.scan_callbacks[0]
        count = len(self.snapshots)
        self.manager.deactivate()
        self.assertTrue(cancellable.is_cancelled())
        callback(self.device, None)
        self.drain()
        self.assertEqual(self.device.scan_finishes, 0)
        self.assertEqual(len(self.snapshots), count)
        self.assertEqual(self.manager.object_handlers, {})

    def test_stale_initialization_does_not_replace_new_client(self):
        self.manager.activate()
        callback = self.factory_callbacks[0][1]
        self.manager.deactivate()
        callback(None, self.client)
        self.assertEqual(self.factory_finishes, [])
        self.assertIsNone(self.manager.client)

    def test_interface_switch_cancels_old_device(self):
        second = FakeDevice("wlan1", [FakeAP("Second", "aa:bb:cc:dd:ee:ff")])
        self.client.devices.append(second)
        self.start()
        self.assertTrue(self.manager.select_interface("wlan1"))
        self.drain()
        self.assertEqual(self.manager.snapshot.interface, "wlan1")
        self.assertEqual(self.manager.snapshot.networks[0].ssid, "Second")
        self.assertEqual(len(second.scan_callbacks), 1)
        self.assertEqual(len(self.device.scan_callbacks), 1)
        self.assertTrue(self.device.scan_callbacks[0][0].is_cancelled())

    def test_ap_disappearance_and_non_wifi_profile(self):
        self.start()
        removed = self.device.aps[0]
        removed.get_ssid = lambda: (_ for _ in ()).throw(AssertionError("stale AP read"))
        self.device.aps.remove(removed)
        self.device.emit("access-point-removed", removed)
        self.drain()
        self.assertEqual(len(self.manager.snapshot.networks), 18)

    def test_saved_connection_activates_without_rewriting_profile(self):
        self.start()
        self.manager.connect("Network-1")
        profile = self.profiles[1]
        self.assertEqual(profile.updates, [])
        self.assertEqual(self.client.calls, ["activate"])
        connection, device, callback = self.client.activate_callbacks.pop(0)
        self.assertIs(device, self.device)
        callback(self.client, None)
        self.drain()

    def test_credentials_update_preserves_profile_before_activation(self):
        self.start()
        self.manager.connect("Network-1", psk="12345678")
        profile = self.profiles[1]
        self.assertEqual(profile.deletions, 0)
        self.assertEqual(self.client.calls, [])
        settings, callback = profile.updates.pop(0)
        self.assertEqual(settings.unpack()["connection"]["uuid"], profile.get_uuid())
        self.assertEqual(settings.unpack()["802-11-wireless-security"]["psk"], "12345678")
        callback(profile, None)
        self.assertEqual(self.client.calls, ["activate"])
        _connection, _device, callback = self.client.activate_callbacks.pop(0)
        callback(self.client, None)

    def test_invalid_psk_does_not_add_profile(self):
        self.start()
        self.assertFalse(self.manager.connect("Network-8", psk="short"))
        self.assertNotIn("add", self.client.calls)
        self.assertEqual(self.results[-1].error, "psk_invalid")

    def test_wifi_uses_async_property_write(self):
        self.start()
        self.manager.set_wireless_enabled(False)
        operation = self.client.calls[-1]
        self.assertEqual(operation[0], "property")
        self.assertEqual(operation[3], "WirelessEnabled")
        self.assertFalse(operation[4])
        self.client.property_callbacks.pop(0)(self.client, None)
        self.drain()

    def test_delete_and_disconnect_completion(self):
        self.start()
        self.manager.delete_network("Network-1")
        profile = self.profiles[1]
        profile.delete_callback(profile, None)
        self.assertEqual(self.results[-1].operation, "delete")
        self.assertTrue(self.results[-1].success)
        active = SimpleNamespace(get_devices=lambda: [self.device])
        self.client.active_connections = [active]
        self.manager.disconnect()
        self.client.deactivate_callback(self.client, None)
        self.assertEqual(self.client.calls, ["deactivate"])
        self.assertEqual(self.results[-1].operation, "disconnect")
        self.assertTrue(self.results[-1].success)

    def test_timeout_reports_error_and_settles(self):
        self.manager.SCAN_TIMEOUT = 0.01
        self.start()
        loop = GLib.MainLoop(context=self.context)
        timeout = GLib.timeout_source_new(150)
        timeout.set_callback(lambda *_: loop.quit())
        timeout.attach(self.context)
        loop.run()
        self.drain()
        self.assertFalse(self.manager.snapshot.scanning)
        self.assertTrue(
            any(result.operation == "scan" and not result.success for result in self.results)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
