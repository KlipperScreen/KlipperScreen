"""Regression tests for the Wi-Fi device stale-path bug in the async sdbus backend.

NetworkManager re-creates the wireless device under a new D-Bus path when the
radio is toggled. The cached ``wlan_device`` proxy must be re-resolved, or later
accesses fail with a stale-object error. These tests verify that
``toggle_wifi`` and ``_refresh_wlan_device_if_stale`` re-resolve the device.
"""

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import sdbus  # noqa: F401  (import check only)

    import ks_includes.sdbus_nm as sdbus_nm
except Exception as exc:  # pragma: no cover - environment without the sdbus backend
    raise unittest.SkipTest(f"sdbus backend unavailable: {exc}")


def _wifi_type():
    return sdbus_nm.enums.DeviceType.WIFI


class FakeDevice:
    """Stand-in for NetworkDeviceGeneric: reports itself as wireless or not."""

    def __init__(self, path, is_wifi):
        self.path = path
        self.is_wifi = is_wifi

    @property
    def device_type(self):
        async def _get():
            return _wifi_type() if self.is_wifi else sdbus_nm.enums.DeviceType.WIRELESS

        return _get()


def fake_devices(wireless_path):
    """Patch the module device constructors so resolution is deterministic.

    ``_resolve_wireless_device`` reads these names from module globals, so the
    patch must be active on the module while the awaited code runs.
    """

    def make_generic(path):
        return FakeDevice(path, is_wifi=path == wireless_path)

    def make_wireless(path):
        return SimpleNamespace(path=path, kind="wireless")

    return mock.patch.multiple(
        sdbus_nm,
        NetworkDeviceGeneric=make_generic,
        NetworkDeviceWireless=make_wireless,
    )


def make_manager(device_paths):
    """A bare SdbusNm with only the attributes the tested methods touch."""
    obj = sdbus_nm.SdbusNm.__new__(sdbus_nm.SdbusNm)
    obj.nm = SimpleNamespace()
    obj.nm._paths = list(device_paths)

    async def get_devices():
        return list(obj.nm._paths)

    obj.nm.get_devices = get_devices
    obj.nm.wireless_enabled = SimpleNamespace(
        set_async=mock.AsyncMock(side_effect=lambda enable: setattr(obj.nm, "_enabled", enable))
    )
    obj.wlan_device = None
    obj.wlan_device_path = None
    obj.wifi = False
    obj.popup = lambda *args, **kwargs: None
    return obj


class ToggleWifiReResolvesTests(unittest.TestCase):
    def test_toggle_wifi_picks_up_new_device_path(self):
        old_path = "/org/freedesktop/NetworkManager/Devices/3"
        new_path = "/org/freedesktop/NetworkManager/Devices/5"
        obj = make_manager([new_path])
        # The proxy from a previous resolution still points at the old path.
        obj.wlan_device = SimpleNamespace(path=old_path)
        obj.wlan_device_path = old_path

        with fake_devices(new_path):
            asyncio.run(obj.toggle_wifi(True))

        self.assertEqual(obj.wlan_device_path, new_path)
        self.assertEqual(obj.wlan_device.path, new_path)
        obj.nm.wireless_enabled.set_async.assert_awaited_once_with(True)

    def test_toggle_wifi_moves_away_from_stale_path(self):
        old_path = "/org/freedesktop/NetworkManager/Devices/3"
        new_path = "/org/freedesktop/NetworkManager/Devices/5"
        obj = make_manager([new_path])
        obj.wlan_device = SimpleNamespace(path=old_path)
        obj.wlan_device_path = old_path

        with fake_devices(new_path):
            asyncio.run(obj.toggle_wifi(True))

        self.assertIsNot(obj.wlan_device_path, old_path)


class RefreshIfStaleTests(unittest.TestCase):
    def test_refresh_when_path_gone(self):
        old_path = "/org/freedesktop/NetworkManager/Devices/1"
        new_path = "/org/freedesktop/NetworkManager/Devices/9"
        obj = make_manager([new_path])
        obj.wlan_device = SimpleNamespace(path=old_path)
        obj.wlan_device_path = old_path

        with fake_devices(new_path):
            asyncio.run(obj._refresh_wlan_device_if_stale())

        self.assertEqual(obj.wlan_device_path, new_path)

    def test_refresh_noop_when_path_still_valid(self):
        valid_path = "/org/freedesktop/NetworkManager/Devices/9"
        obj = make_manager([valid_path])
        live = SimpleNamespace(path=valid_path)
        obj.wlan_device = live
        obj.wlan_device_path = valid_path

        with fake_devices(valid_path):
            asyncio.run(obj._refresh_wlan_device_if_stale())

        # Not stale: the cached proxy must be left untouched (no re-resolution).
        self.assertIs(obj.wlan_device, live)


if __name__ == "__main__":
    unittest.main()
