import os, signal
import json
import logging
import re
import socket
import subprocess
import threading
import time

from contextlib import suppress
from threading import Thread

from subprocess import PIPE, Popen, STDOUT
from queue import Queue, Empty

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

RESCAN_INTERVAL = 180
KS_SOCKET_FILE = "/tmp/.KS_wpa_supplicant"

class WifiManager():
    networks_in_supplicant = []
    connected = False
    _stop_loop = False
    thread = None

    def __init__(self, interface, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = None
        self._poll_task = None
        self._scanning = False
        self._callbacks = {
            "connected": [],
            "connecting_status": [],
            "scan_results": []
        }
        self._stop_loop = False
        self.connected = False
        self.connected_ssid = None
        self.connecting_info = []
        self.event = threading.Event()
        self.initialized = False
        self.interface = interface
        self.networks = {}
        self.supplicant_networks = {}
        self.queue = Queue()
        self.tasks = []
        self.timeout = None
        self.scan_time = 0

        if os.path.exists(KS_SOCKET_FILE):
            os.remove(KS_SOCKET_FILE)

        try:
            self.soc = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.soc.bind(KS_SOCKET_FILE)
            self.soc.connect("/var/run/wpa_supplicant/%s" % interface)
        except:
            logging.info("Error connecting to wifi socket: %s" % interface)
            return

        self.wpa_thread = WpaSocket(self, self.queue, self.callback)
        self.wpa_thread.start()
        self.initialized = True

        self.wpa_cli("ATTACH", False)
        self.wpa_cli("SCAN", False)
        GLib.idle_add(self.read_wpa_supplicant)
        self.timeout = GLib.timeout_add_seconds(RESCAN_INTERVAL, self.rescan)

    def add_callback(self, name, callback):
        if name in self._callbacks and callback not in self._callbacks[name]:
            self._callbacks[name].append(callback)

    def add_network(self, ssid, psk):
        for id in list(self.supplicant_networks):
            if self.supplicant_networks[id]['ssid'] == ssid:
                #Modify network
                return

        # TODO: Add wpa_cli error checking
        network_id = self.wpa_cli("ADD_NETWORK")
        commands = [
            'ENABLE_NETWORK %s' % (network_id),
            'SET_NETWORK %s ssid "%s"' % (network_id, ssid.replace('"','\"')),
            'SET_NETWORK %s psk "%s"' % (network_id, psk.replace('"','\"'))
        ]
        self.wpa_cli_batch(commands)

        self.read_wpa_supplicant()
        id = None
        for i in list(self.supplicant_networks):
            if self.supplicant_networks[i]['ssid'] == ssid:
                id = i
                break

        if id == None:
            logging.info("Error adding network")
            return False

        self.save_wpa_conf()
        return True

    def callback(self, type, msg):
        if type in self._callbacks:
            for cb in self._callbacks[type]:
                Gdk.threads_add_idle(
                    GLib.PRIORITY_DEFAULT_IDLE,
                    cb,
                    msg)

    def connect(self, ssid):
        id = None
        for netid, net in self.supplicant_networks.items():
            if net['ssid'] == ssid:
                id = netid
                break

        if id == None:
            logging.info("Wifi network is not defined in wpa_supplicant")
            return False

        logging.info("Attempting to connect to wifi: %s" % id)
        self.connecting_info = ["Attempting to connect to %s" % ssid]
        self.wpa_cli("SELECT_NETWORK %s" % id)
        self.save_wpa_conf()

    def delete_network(self, ssid):
        id = None
        for i in list(self.supplicant_networks):
            if self.supplicant_networks[i]['ssid'] == ssid:
                id = i
                break

        if id == None:
            logging.debug("Unable to find network in wpa_supplicant")
            return
        self.wpa_cli("REMOVE_NETWORK %s" % id)

        for id in list(self.supplicant_networks):
            if self.supplicant_networks[id]['ssid'] == ssid:
                del self.supplicant_networks[id]
                break

        self.save_wpa_conf()

    def get_connected_ssid(self):
        return self.connected_ssid

    def get_current_wifi(self, interface="wlan0"):
        logging.info("Getting current wifi information")
        status = self.wpa_cli("STATUS").split('\n')
        vars = {}
        for line in status:
            arr = line.split('=')
            vars[arr[0]] = "=".join(arr[1:])

        prev_ssid = self.connected_ssid
        if "ssid" in vars and "bssid" in vars:
            self.connected = True
            self.connected_ssid = vars['ssid']
            for ssid, val in self.networks.items():
                if ssid == vars['ssid']:
                    self.networks[ssid]['connected'] = True
                else:
                    self.networks[ssid]['connected'] = False
            if prev_ssid != self.connected_ssid:
                for cb in self._callbacks['connected']:
                    Gdk.threads_add_idle(
                        GLib.PRIORITY_DEFAULT_IDLE,
                        cb, self.connected_ssid, prev_ssid)
            return [vars['ssid'], vars['bssid']]
        else:
            logging.info("Resetting connected_ssid")
            self.connected = False
            self.connected_ssid = None
            for ssid, val in self.networks.items():
                self.networks[ssid]['connected'] = False
            if prev_ssid != self.connected_ssid:
                for cb in self._callbacks['connected']:
                    Gdk.threads_add_idle(
                        GLib.PRIORITY_DEFAULT_IDLE,
                        cb, self.connected_ssid, prev_ssid)
            return None

    def get_current_wifi_idle_add(self):
        self.get_current_wifi()
        return False

    def get_network_info(self, ssid=None, mac=None):
        if ssid is not None and ssid in self.networks:
            return self.networks[ssid]
        if mac is not None and ssid is None:
            for net in self.networks:
                if mac == net['mac']:
                    return net
        return None

    def get_networks(self):
        return list(self.networks)

    def get_supplicant_networks(self):
        return self.supplicant_networks

    def is_connected(self):
        return self.connected

    def is_initialized(self):
        return self.initialized

    def read_wpa_supplicant(self):
        results = self.wpa_cli("LIST_NETWORKS").split('\n')
        results.pop(0)
        self.supplicant_networks = {}
        self.networks_in_supplicant = []
        for net in [n.split('\t') for n in results]:
            self.supplicant_networks[net[0]] = {
                "ssid": net[1],
                "bssid": net[2],
                "flags": net[3] if len(net) == 4 else ""
            }
            self.networks_in_supplicant.append(self.supplicant_networks[net[0]])

    def remove_callback(self, name, callback):
        if name in self._callbacks and callback in self._callbacks[name]:
            self._callbacks[name].remove(callback)

    def rescan(self):
        self.wpa_cli("SCAN", False)
        return True

    def save_wpa_conf(self):
        logging.info("Saving WPA config")
        self.wpa_cli("SAVE_CONFIG")

    def scan_results(self, interface='wlan0'):
        new_networks = []
        deleted_networks = list(self.networks)

        logging.info("Trying to get scan results")
        results = self.wpa_cli("SCAN_RESULTS").split('\n')
        results.pop(0)

        aps = []
        for res in results:
            match = re.match("^([a-f0-9:]+)\s+([0-9]+)\s+([\-0-9]+)\s+(\S+)\s+(.+)?", res)
            if match:
                net = {
                    "mac": match.group(1),
                    "channel": WifiChannels.lookup(match.group(2))[1],
                    "connected": False,
                    "configured": False,
                    "frequency": match.group(2),
                    "flags": match.group(4),
                    "signal_level_dBm": match.group(3),
                    "ssid": match.group(5)
                }

                if "WPA2" in net['flags']:
                    net['encryption'] = "WPA2"
                elif "WPA" in net['flags']:
                    net['encryption'] = "WPA"
                elif "WEP" in net['flags']:
                    net['encryption'] = "WEP"
                else:
                    net['encryption'] = "off"

                aps.append(net)

        cur_info = self.get_current_wifi()
        self.networks = {}
        for ap in aps:
            self.networks[ap['ssid']] = ap
            if cur_info is not None and cur_info[0] == ap['ssid'] and cur_info[1].lower() == ap['mac'].lower():
                self.networks[ap['ssid']]['connected'] = True

        for net in list(self.networks):
            if net in deleted_networks:
                deleted_networks.remove(net)
            else:
                new_networks.append(net)
        if len(new_networks) > 0 or len(deleted_networks) > 0:
            for cb in self._callbacks['scan_results']:
                Gdk.threads_add_idle(
                    GLib.PRIORITY_DEFAULT_IDLE,
                    cb, new_networks, deleted_networks)

    def wpa_cli(self, command, wait=True):
        if wait == False:
            self.wpa_thread.skip_command()
        self.soc.send(command.encode())
        if wait == True:
            resp = self.queue.get()
            return resp

    def wpa_cli_batch(self, commands):
        for cmd in commands:
            self.wpa_cli(cmd)


class WpaSocket(Thread):
    def __init__ (self, wm, queue, callback):
        super().__init__()
        self.queue = queue
        self.callback = callback
        self.soc = wm.soc
        self._stop_loop = False
        self.skip_commands = 0
        self.wm = wm

    def run(self):
        event = threading.Event()
        logging.debug("Setting up wifi event loop")
        while self._stop_loop == False:
            try:
                msg = self.soc.recv(4096).decode().strip()
            except:
                # TODO: Socket error
                continue
            if msg.startswith("<"):
                if "CTRL-EVENT-SCAN-RESULTS" in msg:
                    logging.info("Adding scan_results to callbacks")
                    Gdk.threads_add_idle(GLib.PRIORITY_DEFAULT_IDLE, self.wm.scan_results)
                elif "CTRL-EVENT-DISCONNECTED" in msg:
                    self.callback("connecting_status", msg)
                    match = re.match('<3>CTRL-EVENT-DISCONNECTED bssid=(\S+) reason=3 locally_generated=1', msg)
                    if match:
                        for net in self.wm.networks:
                            if self.wm.networks[net]['mac'] == match.group(1):
                                self.wm.networks[net]['connected'] = False
                                break
                elif "Trying to associate" in msg:
                    self.callback("connecting_status", msg)
                elif "CTRL-EVENT-REGDOM-CHANGE" in msg:
                    self.callback("connecting_status", msg)
                elif "CTRL-EVENT-CONNECTED" in msg:
                    Gdk.threads_add_idle(GLib.PRIORITY_DEFAULT_IDLE, self.wm.get_current_wifi_idle_add)
                    self.callback("connecting_status", msg)
            else:
                if self.skip_commands > 0:
                    self.skip_commands = self.skip_commands - 1
                else:
                    self.queue.put(msg)
        logging.info("Wifi event loop ended")

    def skip_command(self):
        self.skip_commands = self.skip_commands + 1

    def stop(self):
        self._stop_loop = True


class WifiChannels:
    @staticmethod
    def lookup(freq):
        if freq == "2412":
            return ("2.4","1")
        if freq == "2417":
            return ("2.4","2")
        if freq == "2422":
            return ("2.4","3")
        if freq == "2427":
            return ("2.4","4")
        if freq == "2432":
            return ("2.4","5")
        if freq == "2437":
            return ("2.4","6")
        if freq == "2442":
            return ("2.4","7")
        if freq == "2447":
            return ("2.4","8")
        if freq == "2452":
            return ("2.4","9")
        if freq == "2457":
            return ("2.4","10")
        if freq == "2462":
            return ("2.4","11")
        if freq == "2467":
            return ("2.4","12")
        if freq == "2472":
            return ("2.4","13")
        if freq == "2484":
            return ("2.4","14")
        if freq == "5035":
            return ("5","7")
        if freq == "5040":
            return ("5","8")
        if freq == "5045":
            return ("5","9")
        if freq == "5055":
            return ("5","11")
        if freq == "5060":
            return ("5","12")
        if freq == "5080":
            return ("5","16")
        if freq == "5170":
            return ("5","34")
        if freq == "5180":
            return ("5","36")
        if freq == "5190":
            return ("5","38")
        if freq == "5200":
            return ("5","40")
        if freq == "5210":
            return ("5","42")
        if freq == "5220":
            return ("5","44")
        if freq == "5230":
            return ("5","46")
        if freq == "5240":
            return ("5","48")
        if freq == "5260":
            return ("5","52")
        if freq == "5280":
            return ("5","56")
        if freq == "5300":
            return ("5","60")
        if freq == "5320":
            return ("5","64")
        if freq == "5500":
            return ("5","100")
        if freq == "5520":
            return ("5","104")
        if freq == "5540":
            return ("5","108")
        if freq == "5560":
            return ("5","112")
        if freq == "5580":
            return ("5","116")
        if freq == "5600":
            return ("5","120")
        if freq == "5620":
            return ("5","124")
        if freq == "5640":
            return ("5","128")
        if freq == "5660":
            return ("5","132")
        if freq == "5680":
            return ("5","136")
        if freq == "5700":
            return ("5","140")
        if freq == "5720":
            return ("5","144")
        if freq == "5745":
            return ("5","149")
        if freq == "5765":
            return ("5","153")
        if freq == "5785":
            return ("5","157")
        if freq == "5805":
            return ("5","161")
        if freq == "5825":
            return ("5","165")
        if freq == "4915":
            return ("5","183")
        if freq == "4920":
            return ("5","184")
        if freq == "4925":
            return ("5","185")
        if freq == "4935":
            return ("5","187")
        if freq == "4940":
            return ("5","188")
        if freq == "4945":
            return ("5","189")
        if freq == "4960":
            return ("5","192")
        if freq == "4980":
            return ("5","196")
        return None;
