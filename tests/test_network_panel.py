"""GTK regression tests; run with a display, for example xvfb-run -a python3 -m unittest."""

import builtins
import configparser
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gi

builtins._ = lambda text: text
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
except ValueError:
    raise unittest.SkipTest("GTK is not installed") from None
from gi.repository import GdkPixbuf, Gtk

from ks_includes.gio_nm import AccessPoint, NetworkSnapshot, OperationResult, WirelessDevice
from ks_includes.KlippyGtk import KlippyGtk, find_widget
from panels.network import Panel


class Widgets:
    bsidescale = 1
    font_size = 12
    Button_busy = staticmethod(KlippyGtk.Button_busy)
    Image = staticmethod(Gtk.Image)
    ScrolledWindow = staticmethod(Gtk.ScrolledWindow)

    @staticmethod
    def PixbufFromIcon(_name):
        return GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 24, 24)

    @staticmethod
    def Button(_icon, label=None, *_args):
        button = Gtk.Button()
        box = Gtk.Box()
        box.add(Gtk.Image.new_from_icon_name("network-wireless", Gtk.IconSize.BUTTON))
        if label:
            box.add(Gtk.Label(label=label))
        box.add(Gtk.Spinner(no_show_all=True))
        button.add(box)
        return button


@unittest.skipUnless(Gtk.init_check()[0], "GTK requires a display")
class PanelTests(unittest.TestCase):
    def setUp(self):
        config = configparser.ConfigParser()
        config.read_dict({"main": {}})
        self.screen = SimpleNamespace(
            _config=SimpleNamespace(get_main_config=lambda: config["main"]),
            files=None,
            printer=None,
            gtk=Widgets(),
            vertical_mode=False,
            show_popup_message=Mock(),
            remove_keyboard=Mock(),
            show_keyboard=Mock(),
        )
        with patch("panels.network.NetworkManagerClient") as factory:
            self.backend = factory.return_value
            self.panel = Panel(self.screen, "Network")
        self.ap = AccessPoint(
            "Test network", "00:11:22:33:44:55", 80, "2.4", "1", "WPA-PSK", True, False
        )
        self.publish()

    def publish(self, **kwargs):
        self.panel._on_snapshot(
            NetworkSnapshot(
                devices=(WirelessDevice("wlan0", True, 30, "?"),),
                networks=kwargs.pop("networks", (self.ap,)),
                interface="wlan0",
                wireless_enabled=True,
                **kwargs,
            )
        )

    def tearDown(self):
        self.panel.deactivate()
        self.panel.content.destroy()

    def test_connect_spinner_waits_for_completion(self):
        self.panel.connect_network(None, self.ap.ssid)
        button = self.panel.networks[self.ap.bssid]["connect"]
        spinner = find_widget(button, Gtk.Spinner)
        self.assertTrue(spinner.props.active)
        self.assertFalse(button.get_sensitive())
        self.publish(connecting_ssid=self.ap.ssid)
        self.assertTrue(self.panel.operation_pending)
        self.panel._on_operation(OperationResult("connect", True, ""))
        self.assertFalse(spinner.props.active)
        self.assertFalse(self.panel.operation_pending)
        self.screen.show_popup_message.assert_not_called()

    def test_scan_result_does_not_clear_pending_connection(self):
        self.panel.connect_network(None, self.ap.ssid)
        self.panel._on_operation(OperationResult("scan", False, "Scan failed"))
        self.assertTrue(self.panel.operation_pending)
        self.assertTrue(self.panel.networks[self.ap.bssid]["busy"])

    def test_scan_spinner_follows_snapshot(self):
        spinner = find_widget(self.panel.reload_button, Gtk.Spinner)
        self.publish(scanning=True)
        self.assertTrue(spinner.props.active)
        self.assertFalse(self.panel.reload_button.get_sensitive())
        self.publish(scanning=False)
        self.assertFalse(spinner.props.active)
        self.assertTrue(self.panel.reload_button.get_sensitive())

    def test_hidden_form_submits_without_scan_entry(self):
        self.panel.show_add_network()
        self.panel.labels["network_ssid"].set_text("Unseen network")
        self.panel.labels["network_psk"].set_text("testpassword")
        self.assertFalse(self.panel.labels["network_psk"].get_visibility())
        self.panel.add_new_network(None, None)
        args, kwargs = self.backend.connect.call_args
        self.assertEqual(args, ("Unseen network",))
        self.assertTrue(kwargs["hidden"])
        self.assertEqual(kwargs["security"], "WPA-PSK")
        self.assertTrue(find_widget(self.panel.labels["save_network"], Gtk.Spinner).props.active)
        self.panel._on_operation(OperationResult("connect", True, ""))
        self.assertFalse(self.panel.show_add)

    def test_hidden_security_controls(self):
        self.panel.show_add_network()
        combo = self.panel.labels["network_security"]
        combo.set_active_id("802.1x")
        for name in ("auth_selection", "network_eap_method", "network_phase2", "network_identity"):
            self.assertTrue(self.panel.labels[name].get_visible(), name)
        combo.set_active_id("Open")
        self.assertFalse(self.panel.labels["network_identity"].get_visible())
        self.assertFalse(self.panel.labels["network_psk"].get_sensitive())

    def test_failure_unlocks_form_without_discarding_credentials(self):
        self.panel.show_add_network()
        self.panel.labels["network_ssid"].set_text("Retry network")
        self.panel.labels["network_psk"].set_text("testpassword")
        self.panel.add_new_network(None, None)
        self.panel._on_operation(OperationResult("connect", False, "Connection failed"))
        self.assertTrue(self.panel.show_add)
        self.assertTrue(self.panel.labels["network_psk"].get_sensitive())
        self.assertEqual(self.panel.labels["network_psk"].get_text(), "testpassword")
        self.screen.show_popup_message.assert_called_once_with("Connection failed", 3)

    def test_disappeared_ap_row_is_removed(self):
        self.publish(networks=())
        self.assertEqual(self.panel.network_rows, {})
        self.publish()
        self.assertIn(self.ap.bssid, self.panel.network_rows)


if __name__ == "__main__":
    unittest.main()
