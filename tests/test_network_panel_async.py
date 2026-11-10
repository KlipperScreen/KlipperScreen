"""Unit tests for the async Wi-Fi network panel (panels.network).

The panel stays synchronous at the GTK boundary: every D-Bus action is routed
through a coroutine scheduled on a controllable asyncio loop.  These tests
replace GTK/GLib with fakes and the D-Bus backend with a mock, then drive the
scheduled coroutines to exercise the async scheduling, refresh coalescing and
teardown behaviour.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sdbus_async.networkmanager.enums as enums

import ks_includes.async_utils as async_utils
import ks_includes.screen_panel as screen_panel_mod
import panels.network as network_mod

# --- fakes ---------------------------------------------------------------


class FakeGLib:
    _src = 0

    @staticmethod
    def timeout_add_seconds(interval, cb, *args):
        FakeGLib._src += 1
        return FakeGLib._src

    @staticmethod
    def timeout_add(interval, cb, *args):
        FakeGLib._src += 1
        return FakeGLib._src

    @staticmethod
    def source_remove(sid):
        return True

    @staticmethod
    def idle_add(cb, *args):
        return 0


class FakeGtk:
    """Stand-in for ``gi.repository.Gtk``.

    A plain ``MagicMock`` returns the *same* instance for ``Gtk.Label`` on every
    call, so two labels (or two boxes, switches, …) would share one mock and
    per-widget assertions become meaningless.  Each attribute access here returns
    a fresh mock whose ``__call__`` also returns a fresh mock, so every widget is
    distinct while enum-style access such as ``Gtk.Align.CENTER`` still works.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        child = MagicMock()
        child.side_effect = lambda *a, **k: MagicMock()
        return child


class FakeScreen:
    def __init__(self, gtk):
        self.gtk = gtk
        self.vertical_mode = False
        self._config = MagicMock()
        self.files = MagicMock()
        self.printer = MagicMock()
        self._cur_panels = ["network"]
        self.panels_reinit = []
        self._popup_messages = []

    def show_popup_message(self, msg, level=3):
        self._popup_messages.append((str(msg), level))

    def remove_keyboard(self):
        pass

    def show_keyboard(self, *a):
        pass


def make_gtk():
    gtk = MagicMock()
    gtk.bsidescale = 1.0
    gtk.font_size = 20
    return gtk


def make_fake_nm(wifi=True, devices=None):
    nm = MagicMock()
    nm.wifi = wifi
    if devices is None:
        devices = [{"interface": "wlan0", "type": enums.DeviceType.WIFI}]
    nm.get_interfaces = AsyncMock(return_value=[d["interface"] for d in devices])
    nm.get_all_network_devices = AsyncMock(return_value=devices)
    nm.get_primary_interface = AsyncMock(
        return_value=(devices[0]["interface"] if devices else None)
    )
    nm.initialize = AsyncMock(return_value=True)
    nm.is_wifi_enabled = AsyncMock(return_value=True)
    nm.get_ip_for_interface = AsyncMock(return_value="192.168.1.5")
    nm.get_networks = AsyncMock(return_value=[])
    nm.get_connected_bssid = AsyncMock(return_value=None)
    nm.get_selected_interface = MagicMock(return_value=None)  # sync
    nm.set_selected_interface = AsyncMock(return_value=True)
    nm.set_connection_monitoring = MagicMock(return_value=None)  # sync
    nm.request_rescan = AsyncMock(return_value=0)
    nm.connect = AsyncMock(return_value="/org/Settings/1")
    nm.add_network = AsyncMock(return_value={"status": "success"})
    nm.delete_network = AsyncMock(return_value=None)
    nm.disconnect_network = AsyncMock(return_value=None)
    nm.toggle_wifi = AsyncMock(return_value=None)
    nm.is_known = AsyncMock(return_value=False)
    nm.get_security_type = AsyncMock(return_value="Open")
    nm.get_bssid_from_ssid = AsyncMock(return_value="BSSID1")
    return nm


class Harness:
    """Build a Panel with GTK/GLib/backend faked and a driven asyncio loop."""

    def __init__(self, wifi=True, devices=None):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.nm = make_fake_nm(wifi=wifi, devices=devices)
        self.gtk = make_gtk()
        self.screen = FakeScreen(self.gtk)

        self._patches = [
            patch.object(screen_panel_mod, "Gtk", FakeGtk()),
            patch.object(network_mod, "Gtk", FakeGtk()),
            patch.object(network_mod, "Pango", MagicMock()),
            patch.object(network_mod, "GLib", FakeGLib),
            patch.object(network_mod, "SdbusNm", return_value=self.nm),
            patch.object(async_utils, "get_event_loop", return_value=self.loop),
        ]
        for p in self._patches:
            p.start()

        self.panel = network_mod.Panel(self.screen, "Network")

    def drain(self, rounds=30):
        """Yield to the loop until scheduled coroutines settle."""
        for _ in range(rounds):
            self.loop.run_until_complete(asyncio.sleep(0))

    def run(self, coro):
        return self.loop.run_until_complete(coro)

    def close(self):
        self.loop.close()
        asyncio.set_event_loop(None)
        for p in reversed(self._patches):
            p.stop()


class NetworkPanelTests(unittest.TestCase):
    def setUp(self):
        import builtins

        self._saved = (
            getattr(builtins, "_", None),
            getattr(builtins, "ngettext", None),
        )
        builtins._ = lambda s: s
        builtins.ngettext = lambda s, p, n: s if n == 1 else p

    def tearDown(self):
        import builtins

        (builtins._, builtins.ngettext) = self._saved

    # -- lifecycle ---------------------------------------------------------

    def test_init_schedules_discovery_and_builds_wifi_ui(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            self.assertEqual(p.interface, "wlan0")
            self.assertEqual(p.network_devices[0]["interface"], "wlan0")
            # Wi-Fi path taken: toggle shown, monitoring started, load scheduled.
            p.wifi_toggle_switch.set_sensitive.assert_called_with(True)
            p.sdbus_nm.set_connection_monitoring.assert_called_with(True)
            # IP label populated from the backend.
            self.assertIn("192.168.1.5", p.labels["ip"].set_text.call_args[0][0])
            # Single interface: shown in the interface label, not left blank.
            p.labels["interface"].set_text.assert_called_with("wlan0")
        finally:
            h.close()

    def test_init_builds_interface_selector_with_all_devices(self):
        """With more than one device the selector is a combobox populated from
        the device list, with the primary interface selected."""
        devices = [
            {"interface": "eth0", "type": enums.DeviceType.ETHERNET},
            {"interface": "wlan0", "type": enums.DeviceType.WIFI},
        ]
        h = Harness(devices=devices)
        try:
            h.nm.get_primary_interface.return_value = "wlan0"
            h.drain()
            p = h.panel
            selector = p.labels["interface"]
            # A combobox is built and every interface is added as an entry.
            selector.append.assert_any_call("eth0", "eth0")
            selector.append.assert_any_call("wlan0", "wlan0")
            # The primary interface is the selected one.
            selector.set_active_id.assert_called_with("wlan0")
        finally:
            h.close()

    def test_init_selector_blank_when_no_devices(self):
        """No devices: the selector is never populated and a notice is shown."""
        h = Harness(devices=[])
        try:
            h.drain()
            p = h.panel
            p.labels["interface"].set_text.assert_not_called()
            self.assertTrue(len(h.screen._popup_messages) >= 1)
        finally:
            h.close()

    def test_async_init_contains_discovery_error(self):
        """A D-Bus discovery failure must be contained (logged with a
        traceback), not crash the panel into a frozen skeleton."""
        h = Harness()
        try:
            h.drain()
            p = h.panel
            # Simulate a real-hardware failure the fakes never exercise.
            h.nm.get_all_network_devices.side_effect = RuntimeError("bus gone")
            with self.assertLogs(level="INFO") as cm:
                h.run(p._async_init())
            # Panel stays usable and the failure is recorded, not swallowed.
            self.assertFalse(p._destroyed)
            self.assertIn("network panel: _async_init failed", "\n".join(cm.output))
        finally:
            h.close()

    def test_deactivate_marks_destroyed_and_cancels_tasks(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel

            async def never():
                await asyncio.sleep(3600)
                return 0

            p.sdbus_nm.request_rescan.side_effect = never
            task = p.schedule(p._async_reload())
            h.drain()
            self.assertEqual(len(p._nm_tasks), 1)
            p.deactivate()
            h.drain()  # let the cancellation register
            self.assertTrue(p._destroyed)
            self.assertEqual(p._nm_tasks, [])
            self.assertTrue(task.cancelled())
            p.sdbus_nm.set_connection_monitoring.assert_called_with(False)
        finally:
            h.close()

    def test_deactivate_destroys_backend(self):
        """Teardown must cancel the backend's tasks and subscriptions, which
        ``async_utils.cancel_all_tasks()`` never touches (subscription leak)."""
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.deactivate()
            p.sdbus_nm.destroy.assert_called()
        finally:
            h.close()

    # -- refresh coalescing ------------------------------------------------

    def test_stale_refresh_adds_no_rows(self):
        """A refresh superseded mid-flight must not update widgets."""
        h = Harness()
        try:
            h.drain()
            p = h.panel

            async def flaky_get_networks():
                # Simulate a newer refresh starting while this one is awaiting.
                p._next_refresh_token()
                return [
                    {
                        "BSSID": "X",
                        "SSID": b"X",
                        "known": False,
                        "security": "Open",
                        "frequency": 2437,
                        "channel": "7",
                        "signal_level": 90,
                    }
                ]

            p.sdbus_nm.get_networks.side_effect = flaky_get_networks
            h.run(p._async_load_networks())
            h.drain()
            # Superseded before it could add any rows.
            self.assertEqual(p.network_rows, {})
        finally:
            h.close()

    def test_pause_resume_updates_token(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            t1 = p._refresh_token
            p._pause_refresh()
            self.assertGreater(p._refresh_token, t1)
            self.assertFalse(p._refresh_token_valid(t1))
            self.assertTrue(p._refresh_token_valid(p._refresh_token))
        finally:
            h.close()

    def test_periodic_skipped_while_manual_refresh_in_progress(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.get_networks.reset_mock()
            p._refreshing = True
            # A periodic tick during a manual refresh must be a no-op.
            self.assertTrue(p.update_all_networks())
            p.sdbus_nm.get_networks.assert_not_called()
        finally:
            h.close()

    def test_periodic_wired_refreshes_on_tick(self):
        """The wired periodic timer must keep re-reading the IP every tick.

        The old token guard always bailed (the armed refresh bumped the token
        before the first tick), so wired auto-refresh never fired.
        """
        h = Harness(
            wifi=False,
            devices=[{"interface": "eth0", "type": enums.DeviceType.ETHERNET}],
        )
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.get_ip_for_interface.return_value = "192.168.1.9"
            p._resume_refresh()  # arm the wired periodic timer
            h.drain()  # let the resume's immediate refresh run
            p.sdbus_nm.get_ip_for_interface.reset_mock()
            p._periodic_wired()  # simulate a timer tick
            h.drain()
            p.sdbus_nm.get_ip_for_interface.assert_called()
        finally:
            h.close()

    # -- destroyed panel guard --------------------------------------------

    def test_destroyed_panel_does_not_touch_backend(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.get_networks.reset_mock()
            p.sdbus_nm.get_primary_interface.reset_mock()
            p.deactivate()
            h.run(p._async_load_networks())
            h.run(p._async_update_all_networks())
            p.sdbus_nm.get_networks.assert_not_called()
            p.sdbus_nm.get_primary_interface.assert_not_called()
        finally:
            h.close()

    def test_destroyed_cancelled_task_does_not_update(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            task = p.schedule(p._async_load_networks())
            h.drain()  # first load runs and calls get_networks
            p.sdbus_nm.get_networks.reset_mock()
            p.deactivate()  # cancels the tracked task
            self.assertTrue(task.cancelled() or task.done())
            # Even if it had produced rows, the destroy guard blocks updates.
            h.run(p._async_load_networks())
            p.sdbus_nm.get_networks.assert_not_called()
        finally:
            h.close()

    # -- profile save then activate failure --------------------------------

    def test_add_network_error_shows_popup(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.add_network.side_effect = None
            p.sdbus_nm.add_network.return_value = {
                "error": "insufficient_privileges",
                "message": "No perms",
            }
            h.run(p._async_add_new_network(None, "NET", "", "", None, None))
            self.assertEqual(len(h.screen._popup_messages), 1)
            self.assertEqual(h.screen._popup_messages[0][0], "No perms")
        finally:
            h.close()

    def test_add_network_success_triggers_connect(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.add_network.return_value = {"status": "success"}
            with patch.object(network_mod.asyncio, "sleep", new=AsyncMock()):
                h.run(p._async_add_new_network(None, "NET", "", "", None, None))
                h.drain()
            p.sdbus_nm.connect.assert_called_with("NET")
        finally:
            h.close()

    # -- scan lifecycle ----------------------------------------------------

    def test_reload_rescans_then_loads(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.get_networks.return_value = [
                {
                    "BSSID": "B1",
                    "SSID": b"Net1",
                    "known": True,
                    "security": "WPA-PSK",
                    "frequency": 2437,
                    "channel": "7",
                    "signal_level": 80,
                }
            ]
            p.reload_networks()
            h.drain()
            p.sdbus_nm.request_rescan.assert_called_once()
            self.assertIn("B1", p.network_rows)
        finally:
            h.close()

    def test_iface_changed_wifi_scans_and_sets_indicator(self):
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.get_networks.return_value = [
                {
                    "BSSID": "B1",
                    "SSID": b"Net1",
                    "known": True,
                    "security": "WPA-PSK",
                    "frequency": 2437,
                    "channel": "7",
                    "signal_level": 80,
                }
            ]
            combo = MagicMock()
            h.run(p._async_iface_changed("wlan0", combo))
            h.drain()
            # Selecting a Wi-Fi interface triggers a scan ...
            p.sdbus_nm.request_rescan.assert_called()
            # ... and marks the reload button as busy while scanning.
            p._gtk.Button_busy.assert_called()
            self.assertIn("B1", p.network_rows)
        finally:
            h.close()

    def test_connect_open_or_owe_uses_empty_password(self):
        """An Open or OWE AP is added with an empty secret (no credential
        prompt).  This exercises the ``"OWE" in sec_type`` branch directly."""
        for sec in ("Open", "WPA2-OWE"):
            h = Harness()
            try:
                h.drain()
                p = h.panel
                p.sdbus_nm.is_known.return_value = False
                p.sdbus_nm.get_security_type.return_value = sec
                p.sdbus_nm.add_network.return_value = {"status": "success"}
                h.run(p._async_connect_network(None, "NET", True))
                h.drain()  # let the fire-and-forget reload settle before close
                p.sdbus_nm.add_network.assert_called_with("NET", "")
            finally:
                h.close()

    def test_connect_marks_row_button_busy(self):
        """Connecting should mark the ssid row's connect button busy (spinner),
        like the rescan button, so the user sees we are connecting."""
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.get_networks.return_value = [
                {
                    "BSSID": "B1",
                    "SSID": "Net1",
                    "known": True,
                    "security": "WPA-PSK",
                    "frequency": 2437,
                    "channel": "7",
                    "signal_level": 80,
                }
            ]
            p.sdbus_nm.is_known.return_value = True
            h.run(p._async_load_networks())
            h.drain()
            self.assertIn("B1", p.network_rows)
            connect_button = p.networks["B1"]["connect"]
            h.run(p._async_connect_network(connect_button, "Net1", False))
            h.drain()
            p._gtk.Button_busy.assert_any_call(connect_button, True)
            # The busy state is cleared once the connection attempt finishes.
            p._gtk.Button_busy.assert_any_call(connect_button, False)
        finally:
            h.close()

    def test_disconnect_drops_connected_label(self):
        """Disconnecting must remove the "(Connected)" suffix from the row's
        name, which is otherwise only set when the row is first created."""
        h = Harness()
        try:
            h.drain()
            p = h.panel
            net = {
                "BSSID": "B1",
                "SSID": "Net1",
                "known": True,
                "security": "WPA-PSK",
                "frequency": 2437,
                "channel": "7",
                "signal_level": 80,
            }
            p.sdbus_nm.get_networks.return_value = [net]
            p.sdbus_nm.get_connected_bssid.return_value = "B1"  # currently connected
            h.run(p._async_load_networks())
            h.drain()
            self.assertIn("B1", p.network_rows)
            name = p.networks["B1"]["name"]
            self.assertIn(
                "Connected",
                "".join(str(c.args[0]) for c in name.set_markup.call_args_list),
            )
            # Simulate NM having torn the connection down (so
            # get_connected_bssid now returns None) and the device firing the
            # DISCONNECTED state signal that the panel subscribes to.
            p.sdbus_nm.get_connected_bssid.return_value = None
            p.on_wifi_state_changed(enums.DeviceState.DISCONNECTED)
            h.drain()
            self.assertNotIn(
                "Connected", str(p.networks["B1"]["name"].set_markup.call_args.args[0])
            )
        finally:
            h.close()

    def test_connect_unknown_sec_type_does_not_raise(self):
        """An AP that left range between scan and connect yields None; the
        connect must fall back to the credential prompt, not raise TypeError."""
        h = Harness()
        try:
            h.drain()
            p = h.panel
            p.sdbus_nm.is_known.return_value = False
            p.sdbus_nm.get_security_type.return_value = None
            # Stub the (mock-only) credential form so the None type can't reach
            # the not-iterable get_children() path.
            p.show_add_network = MagicMock()
            h.run(p._async_connect_network(None, "NET", True))
            h.drain()  # let the fire-and-forget refresh settle before close
            p.sdbus_nm.add_network.assert_not_called()
            p.show_add_network.assert_called()
        finally:
            h.close()


if __name__ == "__main__":
    unittest.main()
