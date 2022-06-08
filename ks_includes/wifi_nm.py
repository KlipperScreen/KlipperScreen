# Network in KlipperScreen is a connection in NetworkManager
# Interface in KlipperScreen is a device in NetworkManager

# Todo:
# + Disable hotspot autoconnect when page is showing.
# - Use the security provided by the AP when adding a network
# + Consider removing hotspot from list of APs
# + Handle hidden networks or networks with no SSID better.
# - Fix responsiveness issue. Might be realated to DBusGMainLoop
# - The IP address for the ethernet is not right. It is from wifi.
# - Avahi does not announce the ethernet IP.
# - settings = con.GetSettings() sometimes fails
# - When adding and removing connections, make sure known_connections is updated as well.

import os
import logging
import re
import socket
import threading

from threading import Thread
import NetworkManager
from queue import Queue
import uuid

from dbus.mainloop.glib import DBusGMainLoop
import dbus

import gi
gi.require_version('Gdk', '3.0')
from gi.repository import GLib, Gdk

from ks_includes.wifi import WifiChannels

class WifiManagerNM():
    networks_in_supplicant = []

    def __init__(self, interface_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        DBusGMainLoop(set_as_default=True)
        self._callbacks = {
            "connected": [],
            "connecting_status": [],
            "scan_results": []
        }
        self.connected = False
        self.connected_ssid = None
        self.connecting_info = []
        self.interface_name = interface_name
        self.known_networks = {} # List of known connections
        self.visible_networks = {} # List of visible access points
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
        self._set_autoconnect_on_hotspot(False)
        self.initialized = True

    def _update_known_connections(self):
        self.known_networks = {}
        for con in NetworkManager.Settings.ListConnections():
            settings = con.GetSettings()
            if "802-11-wireless" in settings and settings["802-11-wireless"]['ssid'] != "Recore":
                ssid = settings["802-11-wireless"]['ssid']
                self.known_networks[ssid] = con

    def _ap_added(self, nm, interface, signal, access_point):
        try:
            access_point.OnPropertiesChanged(self._ap_prop_changed)
            ssid = self._add_ap(access_point)
            for cb in self._callbacks['scan_results']:
                Gdk.threads_add_idle(
                    GLib.PRIORITY_DEFAULT_IDLE,
                    cb, [ssid], [])
        except NetworkManager.ObjectVanished:
            pass

    def _ap_removed(self, dev, interface, signal, access_point):
        path = access_point.object_path
        if path in self.ssid_by_path:
            ssid = self.ssid_by_path[path]
            self._remove_ap(path)
            for cb in self._callbacks['scan_results']:
                Gdk.threads_add_idle(
                    GLib.PRIORITY_DEFAULT_IDLE,
                    cb, [], [ssid])

    def _ap_state_changed(self, nm, interface, signal, old_state, new_state, reason):
        msg = ""
        if new_state == NetworkManager.NM_DEVICE_STATE_UNKNOWN:
            msg = "the device's state is unknown"
        elif new_state == NetworkManager.NM_DEVICE_STATE_UNMANAGED:
            msg = "the device is recognized, but not managed by NetworkManager"
        elif new_state == NetworkManager.NM_DEVICE_STATE_UNAVAILABLE:
            msg = "the device is managed by NetworkManager, but is not available for use. Reasons may include the wireless switched off, missing firmware, no ethernet carrier, missing supplicant or modem manager, etc."
        elif new_state == NetworkManager.NM_DEVICE_STATE_DISCONNECTED:
            msg = "the device can be activated, but is currently idle and not connected to a network."
        elif new_state == NetworkManager.NM_DEVICE_STATE_PREPARE:
            msg = "the device is preparing the connection to the network."
        elif new_state == NetworkManager.NM_DEVICE_STATE_CONFIG:
            msg = "the device is connecting to the requested network."
        elif new_state == NetworkManager.NM_DEVICE_STATE_NEED_AUTH:
            msg = "the device requires more information to continue connecting to the requested network."
        elif new_state == NetworkManager.NM_DEVICE_STATE_IP_CONFIG:
            msg = "the device is requesting IPv4 and/or IPv6 addresses and routing information from the network."
        elif new_state == NetworkManager.NM_DEVICE_STATE_IP_CHECK:
            msg = "the device is checking whether further action is required for the requested network connection."
        elif new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
            msg = "Connected"
        if msg != "":
            self.callback("connecting_status", msg)

        if new_state == NetworkManager.NM_DEVICE_STATE_ACTIVATED:
            self.connected = True
            for cb in self._callbacks['connected']:
                Gdk.threads_add_idle(
                    GLib.PRIORITY_DEFAULT_IDLE,
                    cb, self.get_connected_ssid(), None)
        else:
            self.connected = False

    def _ap_prop_changed(self, ap, interface, signal, properties):
        pass

    def _add_ap(self, ap):
        ssid = ap.Ssid
        if ssid == "":
            ssid = f"(hidden-{self.hidden_ssid_index})"
            self.hidden_ssid_index += 1
        self.ssid_by_path[ap.object_path] = ssid
        self.path_by_ssid[ssid] = ap.object_path
        self.visible_networks[ap.object_path] = ap
        return ssid

    def _remove_ap(self, path):
        ssid = self.ssid_by_path.pop(path, None)
        self.visible_networks.pop(path, None)

    def add_callback(self, name, callback):
        if name in self._callbacks and callback not in self._callbacks[name]:
            self._callbacks[name].append(callback)

    def remove_callback(self, name, callback):
        if name in self._callbacks and callback in self._callbacks[name]:
            self._callbacks[name].remove(callback)

    def callback(self, type, msg):
        if type in self._callbacks:
            for cb in self._callbacks[type]:
                Gdk.threads_add_idle(GLib.PRIORITY_DEFAULT_IDLE, cb, msg)

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
        NetworkManager.Settings.AddConnection(new_connection)
        self._update_known_connections()
        return True

    def connect(self, ssid):
        if ssid in self.known_networks:
            conn = self.known_networks[ssid]
            try:
                logging.info("Attempting to connect to wifi: %s" % id)
                NetworkManager.NetworkManager.ActivateConnection(conn, self.wifi_dev, "/")
            except NetworkManager.ObjectVanished:
              pass

    def _get_known_connections_by_uuid(self):
        connections = NetworkManager.Settings.ListConnections()
        return dict([(x.GetSettings()['connection']['uuid'], x) for x in connections])

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
            try:
                ret[ap.Ssid] = ap
            except NetworkManager.ObjectVanished:
              pass
        return ret

    def get_network_info(self, ssid):
        if ssid in self.known_networks:
            con = self.known_networks[ssid]
            try:
                settings = con.GetSettings()
                if settings and '802-11-wireless' in settings:
                    return {
                        "ssid": settings['802-11-wireless']['ssid'],
                        "connected": self.get_connected_ssid() == ssid
                    }
            except NetworkManager.ObjectVanished:
                pass
        path = self.path_by_ssid[ssid]
        aps = self.visible_networks
        if path in aps:
            ap = aps[path]
            try:
                return {
                    "mac": ap.HwAddress,
                    "channel": WifiChannels.lookup(str(ap.Frequency))[1],
                    "configured": ssid in self.known_networks,
                    "frequency": str(ap.Frequency),
                    "flags": ap.Flags,
                    "ssid": ssid,
                    "connected": self._get_connected_ap() == ap,
                    "encryption": self._get_encryption(ap.RsnFlags),
                    "signal_level_dBm": str(ap.Strength)
                }
            except NetworkManager.ObjectVanished:
                pass

    def _get_encryption(self, flags):
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
        return {ssid:{"ssid": ssid} for ssid in self.known_networks.keys()}

    def is_connected(self):
        return self.connected

    def is_initialized(self):
        return self.initialized

    def _set_autoconnect_on_hotspot(self, value):
        for con in NetworkManager.Settings.ListConnections():
            settings = con.GetSettings()
            if "802-11-wireless" in settings and settings["802-11-wireless"]['ssid'] == "Recore":
                old_val = settings["connection"]["autoconnect"]
                if old_val != value:
                    settings["connection"]["autoconnect"] = value
                    con.Update(settings)

    def rescan(self):
        try:
            self.wifi_dev.RequestScan({})
        except dbus.exceptions.DBusException:
            return False
        return True
