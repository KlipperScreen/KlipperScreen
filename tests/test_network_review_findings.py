"""Regression coverage for the libnm migration review."""

import unittest

import test_network_async as fixtures

NM = fixtures.NM
FakeAP = fixtures.FakeAP


class ReviewFindings(unittest.TestCase):
    setUp = fixtures.AsyncTests.setUp
    tearDown = fixtures.AsyncTests.tearDown
    start = fixtures.AsyncTests.start
    drain = fixtures.AsyncTests.drain
    resolve_factory = fixtures.AsyncTests.resolve_factory

    def test_reentry_restores_client_notifications(self):
        self.start()
        self.manager.deactivate()
        self.manager.activate()
        self.drain()
        self.assertIn(self.client, self.manager.object_handlers)

    def test_active_connection_is_not_a_settings_connection(self):
        self.start()
        active = NM.ActiveConnection()
        self.manager._objects_changed(self.client, active)
        self.drain()

    def test_connected_label_requires_activated_device(self):
        self.start()
        self.device.state = NM.DeviceState.CONFIG
        self.manager._changed()
        self.drain()
        self.assertFalse(any(ap.connected for ap in self.manager.snapshot.networks))

    def test_connect_does_not_report_success_before_activation(self):
        self.start()
        self.manager.connect("Network-1")
        self.assertFalse(any(r.operation == "connect" and r.success for r in self.results))

    def test_unique_bssid_in_snapshot(self):
        self.start()
        duplicate = FakeAP("Network-0", self.device.aps[0].bssid)
        self.device.aps.append(duplicate)
        self.device.emit("access-point-added", duplicate)
        self.drain()
        bssids = [ap.bssid for ap in self.manager.snapshot.networks]
        self.assertEqual(len(bssids), len(set(bssids)))


class ConnectionLifecycle(unittest.TestCase):
    setUp = fixtures.AsyncTests.setUp
    tearDown = fixtures.AsyncTests.tearDown
    start = fixtures.AsyncTests.start
    drain = fixtures.AsyncTests.drain
    resolve_factory = fixtures.AsyncTests.resolve_factory

    def activate_connection(self, ssid="Network-1", **kwargs):
        self.start()
        self.assertTrue(self.manager.connect(ssid, **kwargs))
        connection, device, callback = self.client.activate_callbacks.pop(0)
        active = fixtures.FakeActiveConnection()
        callback(self.client, active)
        self.drain()
        return connection, active

    def test_busy_until_active_connection_is_activated(self):
        _, active = self.activate_connection()
        self.assertEqual(self.manager.snapshot.connecting_ssid, "Network-1")
        self.assertFalse(any(r.operation == "connect" for r in self.results))
        active.state = int(NM.ActiveConnectionState.ACTIVATED)
        self.drain()
        self.assertIsNone(self.manager.snapshot.connecting_ssid)
        self.assertEqual([(r.operation, r.success) for r in self.results], [("connect", True)])
        self.assertNotIn(active, self.manager.object_handlers)

    def test_failed_activation_reports_once_and_releases_busy(self):
        _, active = self.activate_connection()
        active.state = int(NM.ActiveConnectionState.DEACTIVATED)
        self.drain()
        self.manager._connection_state_changed(active)
        self.assertIsNone(self.manager.connecting_ssid)
        self.assertEqual([(r.operation, r.success) for r in self.results], [("connect", False)])

    def test_hidden_connection_does_not_require_discovery(self):
        connection, active = self.activate_connection(
            "Unseen hidden network", psk="testpassword", hidden=True, security="WPA-PSK"
        )
        self.assertTrue(connection.get_setting_wireless().get_hidden())
        self.assertEqual(connection.get_setting_wireless_security().get_key_mgmt(), "wpa-psk")
        self.assertEqual(self.client.calls, ["add-and-activate"])
        active.state = int(NM.ActiveConnectionState.ACTIVATED)
        self.assertTrue(self.results[-1].success)

    def test_open_hidden_network_has_no_security_setting(self):
        connection, _active = self.activate_connection(
            "Open hidden network", hidden=True, security="Open"
        )
        self.assertIsNone(connection.get_setting_wireless_security())
        self.assertTrue(connection.verify())

    def test_hidden_network_rejects_invalid_name_without_saving(self):
        self.start()
        for name in ("", "a" * 33, "网" * 11):
            self.assertFalse(
                self.manager.connect(name, psk="testpassword", hidden=True, security="WPA-PSK")
            )
        self.assertEqual(self.client.calls, [])

    def test_profile_bound_to_another_interface_is_rebound_before_activation(self):
        self.start()
        profile = self.profiles[1]
        profile.get_setting_connection().set_property("interface-name", "wlan-old")
        self.manager.connect("Network-1")
        self.assertEqual(self.client.calls, [])
        settings, callback = profile.updates[0]
        self.assertEqual(settings.unpack()["connection"]["interface-name"], self.manager.interface)
        self.assertEqual(settings.unpack()["connection"]["uuid"], profile.get_uuid())
        callback(profile, None)
        self.assertEqual(self.client.calls, ["activate"])

    def test_profile_update_failure_preserves_saved_profile(self):
        self.start()
        profile = self.profiles[1]
        self.manager.connect("Network-1", psk="testpassword")
        profile.updates[0][1](profile, RuntimeError("write failed"))
        self.assertEqual(profile.deletions, 0)
        self.assertIn(profile, self.client.profiles)
        self.assertEqual(self.client.calls, [])
        self.assertIsNone(self.manager.connecting_ssid)
        self.assertFalse(self.results[-1].success)

    def test_departure_cancels_activation_observers(self):
        _, active = self.activate_connection()
        self.manager.deactivate()
        active.state = int(NM.ActiveConnectionState.ACTIVATED)
        self.assertEqual(self.results, [])
        self.assertIsNone(self.manager.connect_timeout_source)
        self.assertEqual(self.manager.object_handlers, {})

    def test_timeout_prevents_late_profile_update_from_activating(self):
        self.start()
        self.manager.connect("Network-1", psk="testpassword")
        callback = self.profiles[1].updates[0][1]
        self.manager._connect_timed_out(self.manager.generation)
        callback(self.profiles[1], None)
        self.assertEqual(self.client.calls, [])
        self.assertFalse(self.results[-1].success)

    def test_timed_out_callback_cannot_activate_a_new_attempt(self):
        self.start()
        self.manager.connect("Network-1", psk="testpassword")
        callback = self.profiles[1].updates[0][1]
        self.manager._connect_timed_out(self.manager.generation)
        self.manager.connect("Network-2")
        before = len(self.client.activate_callbacks)
        callback(self.profiles[1], None)
        self.assertEqual(len(self.client.activate_callbacks), before)
        self.assertEqual(self.manager.connecting_ssid, "Network-2")

    def test_async_errors_identify_the_ui_operation(self):
        self.start()
        for method, operation in (
            ("delete_async", "delete"),
            ("deactivate_connection_async", "disconnect"),
            ("dbus_set_property", "wifi"),
        ):
            self.manager._failed(method, RuntimeError("denied"))
            self.assertEqual(self.results[-1].operation, operation)

    def test_connection_state_progress_does_not_emit_popups(self):
        self.start()
        for state in (
            NM.DeviceState.PREPARE,
            NM.DeviceState.CONFIG,
            NM.DeviceState.IP_CONFIG,
            NM.DeviceState.ACTIVATED,
        ):
            self.device.state = state
            self.manager._state_changed(self.device)
        self.assertEqual(self.results, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
