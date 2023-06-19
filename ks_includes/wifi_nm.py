# Network in KlipperScreen is a connection in NetworkManager
# Interface in KlipperScreen is a device in NetworkManager

import contextlib
import logging
import uuid

from ks_includes import NetworkManager
import dbus
from dbus.mainloop.glib import DBusGMainLoop
import gi

gi.require_version('Gdk', '3.0')
from gi.repository import GLib

from ks_includes.wifi import WifiChannels


class WifiManager:
    networks_in_supplicant = []

    def __init__(self, interface_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DBusGMainLoop(set_as_default=True)
        self._callbacks = {
            "connected": [],
            "connecting_status": [],
            "scan_results": [],
            "popup": [],
        }
        self.connected = False
        self.connected_ssid = None
        self.interface_name = interface_name
        self.known_networks = {}  # List of known connections
        self.visible_networks = {}  # List of visible access points
        self.ssid_by_path = {}
        self.path_by_ssid = {}
        self.hidden_ssid_index = 0

        self.wifi_dev = NetworkManager.NetworkManager.GetDeviceByIpIface(interface_name)
        self.wifi_dev.OnAccessPointAdded(self._ap_added)
        self.wifi_dev.OnAccessPointRemoved(self._ap_removed)
        self.wifi_dev.OnStateChanged(self._ap_state_changed)

        for ap in self.wifi_dev.GetAccessPoints():
            self._add_ap(ap)
        self._update_known_connections()
        self.initialized = True

    def _update_known_connections(self):
        self.known_networks = {}
        for con in NetworkManager.Settings.ListConnections():
            settings = con.GetSettings()
            if "802-11-wireless" in settings:
                ssid = settings["802-11-wireless"]['ssid']
                self.known_networks[ssid] = con

    def _ap_added(self, nm, interface, signal, access_point):
        with contextlib.suppress(NetworkManager.ObjectVanished):
            access_point.OnPropertiesChanged(self._ap_prop_changed)
            ssid = self._add_ap(access_point)
            for cb in self._callbacks['scan_results']:
                args = (cb, [ssid], [])
                GLib.idle_add(*args)

    def _ap_removed(self, dev, interface, signal, access_point):
        path = access_point.object_path
        if path in self.ssid_by_path:
            ssid = self.ssid_by_path[path]
            self._remove_ap(path)
            for cb in self._callbacks['scan_results']:
                args = (cb, [ssid], [])
                GLib.idle_add(*args)

    def _ap_state_changed(self, nm, interface, signal, old_state, new_state, reason):
        msg = ""
        if new_state in (NetworkManager.NM_DEVICE_STATE_UNKNOWN, NetworkManager.NM_DEVICE_STATE_REASON_UNKNOWN):
            msg = "State is unknown"
        elif new_state == NetworkManager.NM_DEVICE_STATE_UNMANAGED:
            msg = "Error: Not managed by NetworkManager"
        elif new_state == NetworkManager.NM_DEVICE_STATE_UNAVAILABLE:
            msg = "Error: Not available for use:\nReasons may include the wireless switched off, missing firmware, etc."
        elif new_state == NetworkManager.NM_DEVICE_STATE_DISCONNECTED:
            msg = "Currently disconnected"
        elif new_state == NetworkManager.NM_DEVICE_STATE_PREPARE:
            msg = "Preparing the connection to the network"
        elif new_state == NetworkManager.NM_DEVICE_STATE_CONFIG:
            msg = "Connecting to the requested network..."
        elif new_state == NetworkManager.NM_DEVICE_STATE_NEED_AUTH:
            msg = "Authorizing"
        elif new_state == NetworkManager.NM_DEVICE_STATE_IP_CONFIG:
            msg = "Requesting IP addresses and routing information"
        elif new_state == NetworkManager.NM_DEVICE_STATE_IP_CHECK:
            msg = "Checking whether further action is required for the requested network connection"
        elif new_state == NetworkManager.NM_DEVICE_STATE_SECONDARIES:
            msg = "Waiting for a secondary connection (like a VPN)"
        elif new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
            msg = "Connected"
        elif new_state == NetworkManager.NM_DEVICE_STATE_DEACTIVATING:
            msg = "A disconnection from the current network connection was requested"
        elif new_state == NetworkManager.NM_DEVICE_STATE_FAILED:
            msg = "Failed to connect to the requested network"
            self.callback("popup", msg)
        elif new_state == NetworkManager.NM_DEVICE_STATE_REASON_DEPENDENCY_FAILED:
            msg = "A dependency of the connection failed"
        elif new_state == NetworkManager.NM_DEVICE_STATE_REASON_CARRIER:
            msg = ""
        else:
            logging.info(f"State {new_state}")
        if msg != "":
            self.callback("connecting_status", msg)

        if new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
            self.connected = True
            for cb in self._callbacks['connected']:
                args = (cb, self.get_connected_ssid(), None)
                GLib.idle_add(*args)
        else:
            self.connected = False

    def _ap_prop_changed(self, ap, interface, signal, properties):
        pass

    def _add_ap(self, ap):
        ssid = ap.Ssid
        if ssid == "":
            ssid = _("Hidden") + f" {self.hidden_ssid_index}"
            self.hidden_ssid_index += 1
        self.ssid_by_path[ap.object_path] = ssid
        self.path_by_ssid[ssid] = ap.object_path
        self.visible_networks[ap.object_path] = ap
        return ssid

    def _remove_ap(self, path):
        self.ssid_by_path.pop(path, None)
        self.visible_networks.pop(path, None)

    def add_callback(self, name, callback):
        if name in self._callbacks and callback not in self._callbacks[name]:
            self._callbacks[name].append(callback)

    def callback(self, cb_type, msg):
        if cb_type in self._callbacks:
            for cb in self._callbacks[cb_type]:
                GLib.idle_add(cb, msg)

    def add_network(self, ssid, psk):
        aps = self._visible_networks_by_ssid()
        if ssid in aps:
            ap = aps[ssid]
        new_connection = {
            '802-11-wireless': {
                'mode': 'infrastructure',
                'security': '802-11-wireless-security',
                'ssid': ssid
            },
            '802-11-wireless-security': {
                'auth-alg': 'open',
                'key-mgmt': 'wpa-psk',
                'psk': psk
            },
            'connection': {
                'id': ssid,
                'type': '802-11-wireless',
                'uuid': str(uuid.uuid4())
            },
            'ipv4': {
                'method': 'auto'
            },
            'ipv6': {
                'method': 'auto'
            }
        }
        try:
            NetworkManager.Settings.AddConnection(new_connection)
        except dbus.exceptions.DBusException as e:
            msg = _("Invalid password") if "802-11-wireless-security.psk" in e else f"{e}"
            self.callback("popup", msg)
            logging.info(f"Error adding network {e}")
        self._update_known_connections()
        return True

    def connect(self, ssid):
        if ssid in self.known_networks:
            conn = self.known_networks[ssid]
            with contextlib.suppress(NetworkManager.ObjectVanished):
                msg = f"Connecting to: {ssid}"
                logging.info(msg)
                self.callback("connecting_status", msg)
                NetworkManager.NetworkManager.ActivateConnection(conn, self.wifi_dev, "/")

    def delete_network(self, ssid):
        for ssid in self.known_networks:
            con = self.known_networks[ssid]
            if con.GetSettings()['connection']['id'] == ssid:
                con.Delete()
        self._update_known_connections()

    def get_connected_ssid(self):
        if self.wifi_dev.SpecificDevice().ActiveAccessPoint:
            return self.wifi_dev.SpecificDevice().ActiveAccessPoint.Ssid
        return None

    def _get_connected_ap(self):
        return self.wifi_dev.SpecificDevice().ActiveAccessPoint

    def _visible_networks_by_ssid(self):
        aps = self.wifi_dev.GetAccessPoints()
        ret = {}
        for ap in aps:
            with contextlib.suppress(NetworkManager.ObjectVanished):
                ret[ap.Ssid] = ap
        return ret

    def get_network_info(self, ssid):
        netinfo = {}
        if ssid in self.known_networks:
            con = self.known_networks[ssid]
            with contextlib.suppress(NetworkManager.ObjectVanished):
                settings = con.GetSettings()
                if settings and '802-11-wireless' in settings:
                    netinfo.update({
                        "ssid": settings['802-11-wireless']['ssid'],
                        "connected": self.get_connected_ssid() == ssid
                    })
        path = self.path_by_ssid[ssid]
        aps = self.visible_networks
        if path in aps:
            ap = aps[path]
            with contextlib.suppress(NetworkManager.ObjectVanished):
                netinfo.update({
                    "mac": ap.HwAddress,
                    "channel": WifiChannels.lookup(str(ap.Frequency))[1],
                    "configured": ssid in self.known_networks,
                    "frequency": str(ap.Frequency),
                    "flags": ap.Flags,
                    "ssid": ssid,
                    "connected": self._get_connected_ap() == ap,
                    "encryption": self._get_encryption(ap.RsnFlags),
                    "signal_level_dBm": str(ap.Strength)
                })
        return netinfo

    @staticmethod
    def _get_encryption(flags):
        encryption = ""
        if (flags & NetworkManager.NM_802_11_AP_SEC_PAIR_WEP40 or
                flags & NetworkManager.NM_802_11_AP_SEC_PAIR_WEP104 or
                flags & NetworkManager.NM_802_11_AP_SEC_GROUP_WEP40 or
                flags & NetworkManager.NM_802_11_AP_SEC_GROUP_WEP104):
            encryption += "WEP "
        if (flags & NetworkManager.NM_802_11_AP_SEC_PAIR_TKIP or
                flags & NetworkManager.NM_802_11_AP_SEC_GROUP_TKIP):
            encryption += "TKIP "
        if (flags & NetworkManager.NM_802_11_AP_SEC_PAIR_CCMP or
                flags & NetworkManager.NM_802_11_AP_SEC_GROUP_CCMP):
            encryption += "AES "
        if flags & NetworkManager.NM_802_11_AP_SEC_KEY_MGMT_PSK:
            encryption += "WPA-PSK "
        if flags & NetworkManager.NM_802_11_AP_SEC_KEY_MGMT_802_1X:
            encryption += "802.1x "
        return encryption.strip()

    def get_networks(self):
        return list(set(list(self.known_networks.keys()) + list(self.ssid_by_path.values())))

    def get_supplicant_networks(self):
        return {ssid: {"ssid": ssid} for ssid in self.known_networks.keys()}

    def rescan(self):
        try:
            self.wifi_dev.RequestScan({})
        except dbus.exceptions.DBusException as e:
            logging.error(f"Error during rescan {e}")
