# This is the backend of the UI panel that communicates to sdbus-networkmanager
# TODO device selection/swtichability
# Alfredo Monclus (alfrix) 2024

import logging

from sdbus_block.networkmanager import (
    NetworkManager,
    NetworkDeviceGeneric,
    NetworkDeviceWireless,
    NetworkConnectionSettings,
    NetworkManagerSettings,
    AccessPoint,
    NetworkManagerConnectionProperties,
    IPv4Config,
    ActiveConnection,
    enums,
    exceptions,
)
from sdbus import sd_bus_open_system, set_default_bus
from gi.repository import GLib
from uuid import uuid4


NM_802_11_AP_SEC_NONE = 0
NM_802_11_AP_SEC_PAIR_WEP40 = 1
NM_802_11_AP_SEC_PAIR_WEP104 = 2
NM_802_11_AP_SEC_PAIR_TKIP = 4
NM_802_11_AP_SEC_PAIR_CCMP = 8
NM_802_11_AP_SEC_GROUP_WEP40 = 16
NM_802_11_AP_SEC_GROUP_WEP104 = 32
NM_802_11_AP_SEC_GROUP_TKIP = 64
NM_802_11_AP_SEC_GROUP_CCMP = 128
NM_802_11_AP_SEC_KEY_MGMT_PSK = 256
NM_802_11_AP_SEC_KEY_MGMT_802_1X = 512


def get_encryption(flags):
    encryption = ""
    if (flags & NM_802_11_AP_SEC_PAIR_WEP40 or
            flags & NM_802_11_AP_SEC_PAIR_WEP104 or
            flags & NM_802_11_AP_SEC_GROUP_WEP40 or
            flags & NM_802_11_AP_SEC_GROUP_WEP104):
        encryption += "WEP "
    if (flags & NM_802_11_AP_SEC_PAIR_TKIP or
            flags & NM_802_11_AP_SEC_GROUP_TKIP):
        encryption += "TKIP "
    if (flags & NM_802_11_AP_SEC_PAIR_CCMP or
            flags & NM_802_11_AP_SEC_GROUP_CCMP):
        encryption += "AES "
    if flags & NM_802_11_AP_SEC_KEY_MGMT_PSK:
        encryption += "WPA-PSK "
    if flags & NM_802_11_AP_SEC_KEY_MGMT_802_1X:
        encryption += "802.1x "
    if not encryption:
        encryption += "Open"
    return encryption


def WifiChannels(freq: str):
    if freq == '2484':
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

    def __init__(self):
        self.system_bus = sd_bus_open_system()  # We need system bus
        set_default_bus(self.system_bus)
        self.nm = NetworkManager()
        if self.get_wireless_interfaces():
            self.wlan_device = self.get_wireless_interfaces()[0]
            self.wifi = True
        else:
            self.wlan_device = None
            self.wifi = False

    def is_wifi_enabled(self):
        return self.nm.wireless_enabled

    def get_interfaces(self):
        return [NetworkDeviceGeneric(device).interface for device in self.nm.get_devices()]

    def get_wireless_interfaces(self):
        devices = {path: NetworkDeviceGeneric(path) for path in self.nm.get_devices()}
        return [
            NetworkDeviceWireless(path)
            for path, device in devices.items()
            if device.device_type == enums.DeviceType.WIFI
        ]

    def get_primary_interface(self):
        if self.nm.primary_connection == '/':
            # Nothing connected
            if self.wlan_device:
                return self.wlan_device.interface
            if len(self.get_interfaces()) > 1:
                # skips the loopback device
                return self.get_interfaces()[1]
            return None
        gateway = ActiveConnection(self.nm.primary_connection).devices[0]
        return NetworkDeviceGeneric(gateway).interface

    @staticmethod
    def get_known_networks():
        known_networks = []
        saved_network_paths = NetworkManagerSettings().list_connections()
        for netpath in saved_network_paths:
            saved_con = NetworkConnectionSettings(netpath)
            con_settings = saved_con.get_settings()
            # 'type': ('s', '802-11-wireless')
            if con_settings['connection']['type'][1] == "802-11-wireless":
                known_networks.append({
                    'SSID': con_settings['802-11-wireless']['ssid'][1].decode(),
                    'UUID': con_settings['connection']['uuid'][1]
                })
        return known_networks

    def is_known(self, ssid):
        return any(net['SSID'] == ssid for net in self.get_known_networks())

    def is_open(self, ssid):
        for network in self.get_networks():
            if network["SSID"] == ssid:
                return network["security"] == "Open"

    def get_ip_address(self):
        active_connection_path = self.nm.primary_connection
        if not active_connection_path or active_connection_path == '/':
            return "?"
        active_connection = ActiveConnection(active_connection_path)
        ip_info = IPv4Config(active_connection.ip4_config)

        return ip_info.address_data[0]['address'][1]

    def get_networks(self):
        networks = []
        if self.wlan_device:
            all_aps = [AccessPoint(result) for result in self.wlan_device.access_points]
            networks.extend(
                {
                    "SSID": ap.ssid.decode("utf-8"),
                    "known": self.is_known(ap.ssid.decode("utf-8")),
                    "security": get_encryption(ap.rsn_flags),
                    "frequency": WifiChannels(ap.frequency)[0],
                    "channel": WifiChannels(ap.frequency)[1],
                    "signal_level": ap.strength,
                    "max_bitrate": ap.max_bitrate,
                    "BSSID": ap.hw_address,
                }
                for ap in all_aps
                if ap.ssid
            )
            return sorted(networks, key=lambda i: i['signal_level'], reverse=True)
        return networks

    def get_bssid_from_ssid(self, ssid):
        return next(net['BSSID'] for net in self.get_networks() if ssid == net['SSID'])

    def get_connected_ap(self):
        if self.wlan_device.active_access_point == "/":
            return None
        return AccessPoint(self.wlan_device.active_access_point)

    def get_connected_bssid(self):
        return self.get_connected_ap().hw_address if self.get_connected_ap() is not None else None

    def add_network(self, ssid, psk):
        if existing_network := NetworkManagerSettings().get_connections_by_id(ssid):
            for network in existing_network:
                self.delete_connection_path(network)

        properties: NetworkManagerConnectionProperties = {
            "connection": {
                "id": ("s", ssid),
                "uuid": ("s", str(uuid4())),
                "type": ("s", "802-11-wireless"),
                "interface-name": ("s", self.wlan_device.interface)
            },
            "802-11-wireless": {
                "mode": ("s", "infrastructure"),
                "security": ("s", "802-11-wireless-security"),
                "ssid": ("ay", ssid.encode("utf-8")),
            },
            "802-11-wireless-security": {
                "key-mgmt": ("s", "wpa-psk"),
                "auth-alg": ("s", "open"),
                "psk": ("s", psk),
            },
            "ipv4": {"method": ("s", "auto")},
            "ipv6": {"method": ("s", "auto")},
        }

        try:
            NetworkManagerSettings().add_connection(properties)
            return {"status": "success"}
        except exceptions.NmConnectionInvalidPropertyError:
            logging.exception("Invalid property")
            return {"error": "psk_invalid", "message": _("Invalid password")}
        except Exception as e:
            logging.exception("Couldn't add network")
            return {"error": "unknown", "message": _("Couldn't add network") + f"\n{e}"}

    def disconnect_network(self):
        self.wlan_device.disconnect()

    def delete_network(self, ssid):
        connection = NetworkManagerSettings().get_connections_by_id(ssid)
        for path in connection:
            self.delete_connection_path(path)

    @staticmethod
    def delete_connection_path(path):
        NetworkConnectionSettings(path).delete()

    def rescan(self):
        return self.wlan_device.request_scan({})

    def connect(self, ssid):
        connection = NetworkManagerSettings().get_connections_by_id(ssid)
        if connection:
            self.nm.activate_connection(connection[0])
        return connection

    def toggle_wifi(self, enable):
        self.nm.wireless_enabled = enable
