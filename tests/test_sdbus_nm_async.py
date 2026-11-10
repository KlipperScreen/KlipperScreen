"""Unit tests for the async NetworkManager backend (ks_includes.sdbus_nm).

The real D-Bus proxies are replaced with fakes so the coroutine logic can be
exercised without NetworkManager.  Coroutines run on a fresh asyncio loop.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sdbus_async.networkmanager import enums

import ks_includes.sdbus_nm as sdbus_nm_mod
from ks_includes.sdbus_nm import SdbusNm


class FakePopup:
    def __init__(self):
        self.messages = []

    def __call__(self, msg, level=3):
        self.messages.append((str(msg), level))


class FakeSignal:
    """Yields a fixed list of values, then ends."""

    def __init__(self, values=None):
        self.values = list(values or [])

    def catch(self):
        return self._catch()

    async def _catch(self):
        for value in self.values:
            yield value


class BlockingSignal:
    """A state-change signal that never yields and never ends.

    Awaits an event that is never set, so a task iterating it stays suspended
    -- this mirrors a live D-Bus subscription, which blocks until the next
    signal rather than exhausting like :class:`FakeSignal`.
    """

    def catch(self):
        return self._catch()

    async def _catch(self):
        while True:
            await asyncio.Event().wait()
            yield None


class Prop:
    """Awaitable property.

    The real sdbus async bindings expose properties that are awaitable
    directly (``await obj.prop``), unlike ``AsyncMock`` which only becomes
    awaitable after being called.  ``side_effect`` lets a property change its
    value across successive awaits (used for the scan ``last_scan``).
    """

    def __init__(self, value=None, side_effect=None):
        self._value = value
        self._side_effect = side_effect

    def __await__(self):
        prop = self

        async def _get():
            if prop._side_effect is not None:
                return prop._side_effect()
            return prop._value

        return _get().__await__()


class FakeWirelessEnabled:
    def __init__(self, value=True):
        self._value = value
        self.set_async = AsyncMock(return_value=None)

    def __await__(self):
        return Prop(self._value).__await__()


class FakeAP:
    def __init__(
        self,
        path="/org/AP1",
        ssid=b"NET",
        strength=80,
        freq="2437",
        hw="00:11:22:33:44:55",
        rsn_flags=8,
        wpa_flags=0,
        flags=0,
    ):
        self.path = path
        self.ssid = Prop(ssid)
        self.strength = Prop(strength)
        self.frequency = Prop(freq)
        self.hw_address = Prop(hw)
        self.rsn_flags = Prop(rsn_flags)
        self.wpa_flags = Prop(wpa_flags)
        self.flags = Prop(flags)


class FakeDevice:
    def __init__(
        self,
        iface="wlan0",
        dtype=enums.DeviceType.WIFI,
        state=enums.DeviceState.ACTIVATED,
        active_ap="/org/AP1",
        last_scan=0,
        access_points=None,
    ):
        self.interface = Prop(iface)
        self.device_type = Prop(dtype)
        self.state = Prop(state)
        self.active_access_point = Prop(active_ap)
        self.active_connection = Prop("/org/Active/1")
        self.access_points = Prop(access_points or ["/org/AP1"])
        self.last_scan = Prop(last_scan)
        self.perm_hw_address = Prop("aa:bb:cc:dd:ee:ff")
        self.state_changed = FakeSignal()
        self.disconnect = AsyncMock(return_value=None)
        self.request_scan = AsyncMock(return_value=None)


class FakeSettings:
    def __init__(self, settings=None, path="/org/Settings/1"):
        self._settings = (
            settings
            if settings is not None
            else {
                "connection": {
                    "type": ("s", "802-11-wireless"),
                    "uuid": ("s", "uuid-1"),
                    "id": ("s", "net"),
                },
                "802-11-wireless": {"ssid": ("ay", b"NET"), "mode": ("s", "infrastructure")},
            }
        )
        self.path = path
        self.get_settings = AsyncMock(return_value=self._settings)
        self.delete = AsyncMock(return_value=None)
        self.update = AsyncMock(return_value=None)
        self.list_connections = AsyncMock(return_value=["/org/Settings/1"])
        self.add_connection = AsyncMock(return_value="/org/Settings/2")


class FakeConn:
    def __init__(self, ip4="/org/IP4/1", devices=None, active="/"):
        self.ip4_config = Prop(ip4)
        self.devices = Prop(devices or ["/org/Devices/3"])
        self.state = Prop(enums.ConnectionState.ACTIVATED)
        self.state_changed = FakeSignal()


class FakeIP4:
    def __init__(self, address="192.168.1.5"):
        self.address_data = Prop([{"address": ("s", address), "prefix": ("y", 24)}])


class FakeNM:
    """A fake NetworkManager manager + per-path proxy registry."""

    def __init__(self):
        self.get_devices = AsyncMock(return_value=["/org/Devices/3"])
        self.list_connections = AsyncMock(return_value=["/org/Settings/1"])
        self.add_connection = AsyncMock(return_value="/org/Settings/2")
        self.activate_connection = AsyncMock(return_value="/org/Active/1")
        self.deactivate_connection = AsyncMock(return_value=None)
        self.primary_connection = Prop("/")
        self.get_device_by_ip_iface = AsyncMock(return_value="/org/Devices/3")
        self.wireless_enabled = FakeWirelessEnabled(True)
        self.state_changed = FakeSignal()


STARTED_PATCHES = []


def _start(patch_obj):
    patch_obj.start()
    STARTED_PATCHES.append(patch_obj)
    return patch_obj


def build_sdbus(state=None, **overrides):
    """Construct a SdbusNm with all D-Bus proxies faked.

    Returns (sdbus_nm, registry) where registry holds the fakes for
    assertions.  Patches stay active until :func:`stop_all_patches`.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    nm = FakeNM()
    wlan = FakeDevice(**(state or {}))
    generic = FakeDevice(
        iface="eth0",
        dtype=enums.DeviceType.ETHERNET,
        state=enums.DeviceState.ACTIVATED,
        active_ap="/",
    )
    eth = MagicMock()
    eth.interface = Prop("eth0")
    eth.device_type = Prop(enums.DeviceType.ETHERNET)
    eth.active_connection = Prop("/")

    ap = FakeAP()
    settings = FakeSettings()
    ip4 = FakeIP4()
    conn = FakeConn()

    popup = FakePopup()

    _start(patch.object(sdbus_nm_mod.subprocess, "run", return_value=MagicMock(returncode=0)))
    _start(patch.object(sdbus_nm_mod.sdbus, "sd_bus_open_system", return_value=MagicMock()))
    _start(patch.object(sdbus_nm_mod, "NetworkManager", return_value=nm))
    _start(
        patch.object(
            sdbus_nm_mod,
            "NetworkDeviceGeneric",
            side_effect=lambda p, *a, **k: {"/org/Devices/3": wlan, "/org/Devices/4": eth}.get(
                p, generic
            ),
        )
    )
    _start(patch.object(sdbus_nm_mod, "NetworkDeviceWireless", side_effect=lambda p, *a, **k: wlan))
    _start(patch.object(sdbus_nm_mod, "AccessPoint", side_effect=lambda p, *a, **k: ap))
    _start(patch.object(sdbus_nm_mod, "ActiveConnection", side_effect=lambda p, *a, **k: conn))
    _start(patch.object(sdbus_nm_mod, "IPv4Config", side_effect=lambda p, *a, **k: ip4))
    _start(
        patch.object(
            sdbus_nm_mod, "NetworkConnectionSettings", side_effect=lambda p, *a, **k: settings
        )
    )
    _start(
        patch.object(sdbus_nm_mod, "NetworkManagerSettings", side_effect=lambda *a, **k: settings)
    )

    obj = SdbusNm(popup, loop=loop)
    obj.nm = nm
    obj.wlan_device = wlan
    # Apply any per-test overrides on the manager.
    for key, value in overrides.items():
        setattr(obj.nm, key, value)
    registry = MagicMock()
    registry.nm = nm
    registry.wlan = wlan
    registry.generic = generic
    registry.eth = eth
    registry.ap = ap
    registry.settings = settings
    registry.ip4 = ip4
    registry.conn = conn
    registry.popup = popup
    return obj, registry, loop


def stop_all_patches():
    while STARTED_PATCHES:
        patch_obj = STARTED_PATCHES.pop()
        try:
            patch_obj.stop()
        except Exception:
            pass


class SdbusNmTests(unittest.TestCase):
    def setUp(self):
        # The backend uses the gettext builtin ``_``/``ngettext`` (installed by
        # the application at runtime); provide identity versions for tests.
        import builtins

        self._saved = (
            getattr(builtins, "_", None),
            getattr(builtins, "ngettext", None),
        )
        builtins._ = lambda s: s
        builtins.ngettext = lambda s, p, n: s if n == 1 else p

    def tearDown(self):
        import builtins

        old_, old_ng = self._saved
        if old_ is None:
            delattr(builtins, "_")
        else:
            builtins._ = old_
        if old_ng is None:
            delattr(builtins, "ngettext")
        else:
            builtins.ngettext = old_ng
        stop_all_patches()
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            loop.close()

    # -- device discovery --------------------------------------------------

    async def _resolve(self, obj):
        await obj._resolve_wireless_device()

    def test_resolve_wireless_device_filters_wifi(self):
        obj, reg, loop = build_sdbus()

        async def go():
            await obj._resolve_wireless_device()
            return obj.wifi, obj.wlan_device is not None

        wifi, has = loop.run_until_complete(go())
        self.assertTrue(wifi)
        self.assertTrue(has)
        reg.nm.get_devices.assert_awaited()

    def test_get_all_network_devices_includes_wifi_and_ethernet(self):
        obj, reg, loop = build_sdbus()
        reg.nm.get_devices = AsyncMock(return_value=["/org/Devices/3", "/org/Devices/4"])

        async def go():
            return await obj.get_all_network_devices()

        devices = loop.run_until_complete(go())
        interfaces = {d["interface"] for d in devices}
        self.assertIn("wlan0", interfaces)
        self.assertIn("eth0", interfaces)

    def test_get_interfaces_returns_names(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.get_interfaces()

        ifaces = loop.run_until_complete(go())
        self.assertIn("wlan0", ifaces)

    # -- network enumeration ----------------------------------------------

    def test_get_networks_structure(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.get_networks()

        nets = loop.run_until_complete(go())
        self.assertEqual(len(nets), 1)
        net = nets[0]
        self.assertEqual(net["SSID"], "NET")
        self.assertEqual(net["security"], "AES")  # rsn_flags=8 -> PAIR_CCMP
        self.assertEqual(net["signal_level"], 80)
        self.assertEqual(net["BSSID"], "00:11:22:33:44:55")

    def test_get_networks_marks_connected(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.get_networks()

        net = loop.run_until_complete(go())[0]
        self.assertTrue(net["connected"])

    def test_get_networks_skips_hidden_aps(self):
        obj, reg, loop = build_sdbus()
        reg.ap.ssid = Prop(None)

        async def go():
            return await obj.get_networks()

        self.assertEqual(loop.run_until_complete(go()), [])

    def test_get_connected_bssid(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.get_connected_bssid()

        self.assertEqual(loop.run_until_complete(go()), "00:11:22:33:44:55")

    def test_get_security_type(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.get_security_type("NET")

        self.assertEqual(loop.run_until_complete(go()), "AES")

    # -- scanning ----------------------------------------------------------

    def test_request_rescan_waits_for_scan_completion(self):
        obj, reg, loop = build_sdbus()
        # initial read, completion read, final read -> stable after first change.
        seq = iter([100, 101, 101, 101, 101])
        reg.wlan.last_scan = Prop(side_effect=seq.__next__)

        async def go():
            return await obj.request_rescan()

        result = loop.run_until_complete(go())
        self.assertEqual(result, 101)
        reg.wlan.request_scan.assert_awaited_once_with({})

    def test_request_rescan_skips_when_unmanaged(self):
        obj, reg, loop = build_sdbus(state={"state": enums.DeviceState.UNMANAGED})

        async def go():
            return await obj.request_rescan()

        self.assertIsNone(loop.run_until_complete(go()))
        reg.wlan.request_scan.assert_not_awaited()

    def test_request_rescan_timeout_still_clears_state(self):
        obj, reg, loop = build_sdbus()
        # last_scan never changes -> times out (fast, via monkeypatch).
        with patch.object(sdbus_nm_mod, "SCAN_TIMEOUT", 0):
            reg.wlan.last_scan = Prop(5)

            async def go():
                return await obj.request_rescan()

            result = loop.run_until_complete(go())
        # Scan was requested and the call returns promptly (no hang) even
        # though the scan never completes.
        reg.wlan.request_scan.assert_awaited_once()
        self.assertEqual(result, 5)

    def test_request_rescan_handles_permission_error(self):
        obj, reg, loop = build_sdbus()
        from sdbus_async.networkmanager import exceptions

        reg.wlan.request_scan = AsyncMock(
            side_effect=exceptions.NetworkManagerPermissionDeniedError("no")
        )

        async def go():
            return await obj.request_rescan()

        result = loop.run_until_complete(go())
        self.assertIsNone(result)
        self.any_contains_disconnect(reg.popup)

    def any_contains_disconnect(self, popup):
        self.assertTrue(any("privilege" in m.lower() for m, _ in popup.messages))

    # -- interface selection -----------------------------------------------

    def test_set_selected_interface_binds_wireless_device(self):
        obj, reg, loop = build_sdbus()
        # Simulate a fresh backend where the wireless device is not yet resolved.
        obj.wlan_device = None
        obj.wifi = False

        async def go():
            return await obj.set_selected_interface("wlan0")

        self.assertTrue(loop.run_until_complete(go()))
        # The selected wireless device is now bound, so scanning / listing
        # (which key off ``self.wlan_device``) operate on it.
        self.assertIs(obj.wlan_device, reg.wlan)
        self.assertEqual(obj.wlan_device_path, "/org/Devices/3")
        self.assertTrue(obj.wifi)

    def test_set_selected_interface_unmanaged_does_not_bind(self):
        obj, reg, loop = build_sdbus(state={"state": enums.DeviceState.UNMANAGED})
        obj.wlan_device = None

        async def go():
            return await obj.set_selected_interface("wlan0")

        self.assertFalse(loop.run_until_complete(go()))
        self.assertIsNone(obj.wlan_device)

    # -- saved networks ----------------------------------------------------

    def test_add_network_open(self):
        obj, reg, loop = build_sdbus()
        # security type Open -> rsn/wpa/flags all zero; SSID matches the AP.
        reg.ap.rsn_flags = Prop(0)
        reg.ap.wpa_flags = Prop(0)
        reg.ap.flags = Prop(0)

        async def go():
            return await obj.add_network("NET", "")

        result = loop.run_until_complete(go())
        self.assertEqual(result["status"], "success")
        reg.settings.add_connection.assert_awaited()

    def test_add_network_permission_denied(self):
        obj, reg, loop = build_sdbus()
        # WPA-PSK network so add_network proceeds past security handling.
        from ks_includes.sdbus_nm import KEY_MGMT_PSK, PAIR_CCMP

        reg.ap.rsn_flags = Prop(KEY_MGMT_PSK | PAIR_CCMP)
        from sdbus_async.networkmanager import exceptions

        reg.settings.add_connection = AsyncMock(
            side_effect=exceptions.NmSettingsPermissionDeniedError("no")
        )

        async def go():
            return await obj.add_network("NET", "psk")

        result = loop.run_until_complete(go())
        self.assertEqual(result["error"], "insufficient_privileges")

    def test_delete_network(self):
        obj, reg, loop = build_sdbus()

        async def go():
            await obj.delete_network("NET")
            return reg.settings.delete.call_count

        self.assertEqual(loop.run_until_complete(go()), 1)

    def test_get_connection_path_by_ssid(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.get_connection_path_by_ssid("NET")

        self.assertEqual(loop.run_until_complete(go()), "/org/Settings/1")

    def test_get_connection_path_by_ssid_missing(self):
        obj, reg, loop = build_sdbus()
        reg.settings._settings["802-11-wireless"]["ssid"] = ("ay", b"OTHER")

        async def go():
            return await obj.get_connection_path_by_ssid("NET")

        self.assertIsNone(loop.run_until_complete(go()))

    # -- connect / disconnect ---------------------------------------------

    def test_connect_activates(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.connect("NET")

        result = loop.run_until_complete(go())
        self.assertEqual(result, "/org/Settings/1")
        reg.nm.activate_connection.assert_awaited_once_with("/org/Settings/1")

    def test_connect_missing_ssid(self):
        obj, reg, loop = build_sdbus()
        reg.nm.list_connections = AsyncMock(return_value=[])

        async def go():
            return await obj.connect("NOPE")

        self.assertIsNone(loop.run_until_complete(go()))
        reg.nm.activate_connection.assert_not_awaited()

    def test_disconnect_network(self):
        obj, reg, loop = build_sdbus()

        async def go():
            await obj.disconnect_network()

        loop.run_until_complete(go())
        reg.wlan.disconnect.assert_awaited_once()

    # -- ip lookup ---------------------------------------------------------

    def test_get_ip_for_interface_connected(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.get_ip_for_interface("wlan0")

        self.assertEqual(loop.run_until_complete(go()), "192.168.1.5")

    def test_get_ip_for_interface_disconnected(self):
        obj, reg, loop = build_sdbus()
        reg.generic.active_connection = AsyncMock(return_value="/")
        reg.nm.get_device_by_ip_iface = AsyncMock(return_value="/org/Devices/4")

        async def go():
            return await obj.get_ip_for_interface("eth0")

        self.assertEqual(loop.run_until_complete(go()), "?")

    def test_get_ip_for_interface_unknown(self):
        obj, reg, loop = build_sdbus()
        from sdbus_async.networkmanager import exceptions

        reg.nm.get_device_by_ip_iface = AsyncMock(
            side_effect=exceptions.NetworkManagerUnknownDeviceError("x")
        )

        async def go():
            return await obj.get_ip_for_interface("ghost")

        self.assertEqual(loop.run_until_complete(go()), "?")

    # -- wifi toggle -------------------------------------------------------

    def test_toggle_wifi_sets_property(self):
        obj, reg, loop = build_sdbus()

        async def go():
            await obj.toggle_wifi(False)

        loop.run_until_complete(go())
        reg.nm.wireless_enabled.set_async.assert_awaited_once_with(False)

    def test_is_wifi_enabled(self):
        obj, reg, loop = build_sdbus()

        async def go():
            return await obj.is_wifi_enabled()

        self.assertTrue(loop.run_until_complete(go()))

    # -- state monitoring --------------------------------------------------

    def test_monitor_ignores_duplicate_state(self):
        obj, reg, loop = build_sdbus()
        reg.wlan.state_changed = FakeSignal(
            values=[
                (enums.DeviceState.ACTIVATED, 1, 0),
                (enums.DeviceState.ACTIVATED, 1, 0),
            ]
        )

        async def go():
            obj.set_connection_monitoring(True)
            await asyncio.sleep(0.05)
            return list(obj.popup.messages)

        messages = loop.run_until_complete(go())
        # baseline consumes first ACTIVATED, second is a duplicate -> no popup.
        self.assertEqual(messages, [])

    def test_apply_state_invokes_registered_callbacks(self):
        obj, reg, loop = build_sdbus()
        received = []
        obj.register_state_callback(received.append)

        async def go():
            # Baseline so the change is a real transition rather than the
            # initial-state guard, mirroring the monitor's first read.
            obj.wifi_state = enums.DeviceState.DISCONNECTED
            await obj._apply_state(enums.DeviceState.ACTIVATED)
            return received

        self.assertEqual(loop.run_until_complete(go()), [enums.DeviceState.ACTIVATED])

    def test_apply_state_ignores_callback_exceptions(self):
        obj, reg, loop = build_sdbus()
        with patch.object(sdbus_nm_mod.logger, "exception") as log_exc:

            def boom(state):
                raise ValueError("nope")

            obj.register_state_callback(boom)

            async def go():
                obj.wifi_state = enums.DeviceState.DISCONNECTED
                # A raising callback must not abort the state update.
                await obj._apply_state(enums.DeviceState.ACTIVATED)
                return obj.wifi_state

            self.assertEqual(loop.run_until_complete(go()), enums.DeviceState.ACTIVATED)
            log_exc.assert_called_once()

    def test_destroy_cancels_tasks(self):
        obj, reg, loop = build_sdbus()
        # A signal that never fires keeps the monitor task suspended -- like a
        # live D-Bus subscription -- so destroy() has a running task to cancel.
        reg.wlan.state_changed = BlockingSignal()

        async def go():
            obj.set_connection_monitoring(True)
            await asyncio.sleep(0.01)
            task = obj._monitor_task
            self.assertIsNotNone(task)
            obj.destroy()
            # destroy() clears the reference immediately...
            self.assertIsNone(obj._monitor_task)
            # ...but the cancellation only registers once the loop runs.
            await asyncio.sleep(0)
            return task.cancelled() or task.done()

        result = loop.run_until_complete(go())
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
