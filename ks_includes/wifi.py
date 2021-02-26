import os, signal
import json
import logging
import re
import subprocess
import threading

from contextlib import suppress
from threading import Thread

RESCAN_INTERVAL = 120

class WifiManager(Thread):
    iw_regexes = [
        re.compile(r"^ESSID:\"(?P<essid>.*)\"$"),
        re.compile(r"^Protocol:(?P<protocol>.+)$"),
        re.compile(r"^Mode:(?P<mode>.+)$"),
        re.compile(r"^Frequency:(?P<frequency>[\d.]+) (?P<frequency_units>.+) \(Channel (?P<channel>\d+)\)$"),
        re.compile(r"^Encryption key:(?P<encryption>.+)$"),
        re.compile(r"^Quality=(?P<signal_quality>\d+)/(?P<signal_total>\d+)\s+Signal level=(?P<signal_level_dBm>.+) d.+$"),
        re.compile(r"^Signal level=(?P<signal_quality>\d+)/(?P<signal_total>\d+).*$")
    ]
    networks_in_supplicant = []
    wpa = {
        "wpa": re.compile(r"IE:\ WPA\ Version\ 1$"),
        "wpa2": re.compile(r"IE:\ IEEE\ 802\.11i/WPA2\ Version\ 1$")
    }
    connected = False
    _stop_loop = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = None
        self._poll_task = None
        self._scanning = False
        self.networks = {}
        self.read_wpa_supplicant()

    def run(self):
        event = threading.Event()
        logging.debug("Setting up wifi event loop")
        while self._stop_loop == False:
            try:
                self.scan()
                event.wait(RESCAN_INTERVAL)
            except:
                logging.exception("Poll wifi error")

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    def stop_loop(self):
        self._stop_loop = True

    def get_current_wifi(self, interface="wlan0"):
        p = subprocess.Popen(["iwconfig",interface], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        content = p.stdout.read().decode('utf-8').split('\n')

        essid = None
        mac = None
        for line in content:
            match = re.match(r'^.*ESSID:"(.*)"$', line.strip())
            if match:
                essid = match.group(1)
                continue
            match = re.match(r'^.*Access\s+Point:\s+([0-9A-Fa-f:]+)$', line.strip())
            if match:
                mac = match.group(1)
                break

        if essid is None or mac is None:
            self.connected = False
            return None
        self.connected = True
        return [essid, mac]

    def get_network_info(self, essid=None, mac=None):
        if essid is not None and essid in self.networks:
            return self.networks[essid]
        if mac is not None and essid is None:
            for net in self.networks:
                if mac == net['mac']:
                    return net
        return None

    def get_networks(self):
        return list(self.networks)

    def is_connected(self):
        return self.connected

    def parse(self, data):
        aps = []
        lines = data.split('\n')

        for line in lines:
            line = line.strip()
            match = re.match(r'^Cell\s+([0-9]+)\s+-\s+Address:\s+(?P<mac>[0-9A-Fa-f:]+)$', line)
            if match:
                aps.append({"mac":match.group(2)})
                continue
            if len(aps) < 1:
                continue
            for w, wreg in self.wpa.items():
                t = wreg.search(line)
                if t is not None:
                    aps[-1].update({'encryption': w})
            for exp in self.iw_regexes:
                result = exp.search(line)
                if result is not None:
                    if "encryption" in result.groupdict():
                        if result.groupdict()['encryption'] == 'on' :
                            aps[-1].update({'encryption': 'wep'})
                        else:
                            aps[-1].update({'encryption': 'off'})
                    else:
                        aps[-1].update(result.groupdict())
        return aps

    def read_wpa_supplicant(self):
        wpaconf = "/etc/wpa_supplicant/wpa_supplicant.conf"
        if not os.path.exists(wpaconf):
            return None

        regexes = [
            re.compile(r'^ssid\s*=\s*"(?P<ssid>.*)"$'),
            re.compile(r'^psk\s*=\s*"(?P<psk>.*)"$')
        ]
        networks = []
        p = subprocess.Popen(["sudo","cat",wpaconf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        contents = p.stdout.read().decode('utf-8').split('\n')

        for line in contents:
            if re.match(r'^network\s*=\s*{$', line.strip()):
                networks.append({})
                continue
            if len(networks) < 1:
                continue
            for exp in regexes:
                result = exp.search(line.strip())
                if result is not None:
                    networks[-1].update(result.groupdict())

        self.networks_in_supplicant = []
        for network in networks:
            self.networks_in_supplicant.append(network)

    def scan(self, interface='wlan0'):
        p = subprocess.Popen(["sudo","iwlist",interface,"scan"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        aps = self.parse(p.stdout.read().decode('utf-8'))
        cur_info = self.get_current_wifi()


        self.networks = {}
        for ap in aps:
            self.networks[ap['essid']] = ap
            if cur_info is not None and cur_info[0] == ap['essid'] and cur_info[1] == ap['mac']:
                self.networks[ap['essid']]['connected'] = True
                for net in self.networks_in_supplicant:
                    if ap['essid'] == net['ssid'] and "psk" in net:
                        ap['psk'] = net['psk']
                        break
