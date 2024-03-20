import logging
import os
import gi
import netifaces

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    initialized = False

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.show_add = False
        self.networks = {}
        self.interface = None
        self.prev_network = None
        self.update_timeout = None
        self.network_interfaces = netifaces.interfaces()
        self.wireless_interfaces = [iface for iface in self.network_interfaces if iface.startswith('wl')]
        self.wifi = None
        self.use_network_manager = os.system('systemctl is-active --quiet NetworkManager.service') == 0
        if self.wireless_interfaces:
            logging.info(f"Found wireless interfaces: {self.wireless_interfaces}")
            if self.use_network_manager:
                logging.info("Using NetworkManager")
                from ks_includes.wifi_nm import WifiManager
            else:
                logging.info("Using wpa_cli")
                from ks_includes.wifi import WifiManager
            self.wifi = WifiManager(self.wireless_interfaces[0])
        else:
            logging.info(_("No wireless interface has been found"))

        # Get IP Address
        gws = netifaces.gateways()
        if "default" in gws and netifaces.AF_INET in gws["default"]:
            self.interface = gws["default"][netifaces.AF_INET][1]
        else:
            ints = netifaces.interfaces()
            if 'lo' in ints:
                ints.pop(ints.index('lo'))
            self.interface = ints[0] if len(ints) > 0 else 'lo'

        self.labels['networks'] = {}

        self.labels['interface'] = Gtk.Label(hexpand=True)
        self.labels['interface'].set_text(_("Interface") + f': {self.interface}  ')

        self.labels['ip'] = Gtk.Label(hexpand=True)
        ifadd = netifaces.ifaddresses(self.interface)
        if ifadd.get(netifaces.AF_INET):
            self.labels['ip'].set_text(f"IP: {ifadd[netifaces.AF_INET][0]['addr']}  ")

        reload_networks = self._gtk.Button("refresh", None, "color1", self.bts)
        reload_networks.connect("clicked", self.reload_networks)
        reload_networks.set_hexpand(False)

        sbox = Gtk.Box(hexpand=True, vexpand=False)
        sbox.add(self.labels['interface'])
        sbox.add(self.labels['ip'])
        sbox.add(reload_networks)

        scroll = self._gtk.ScrolledWindow()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)

        self.labels['networklist'] = Gtk.Grid()

        if self.wifi is not None and self.wifi.initialized:
            box.pack_start(sbox, False, False, 5)
            box.pack_start(scroll, True, True, 0)

            GLib.idle_add(self.load_networks)
            scroll.add(self.labels['networklist'])

            self.wifi.add_callback("connected", self.connected_callback)
            self.wifi.add_callback("scan_results", self.scan_callback)
            self.wifi.add_callback("popup", self.popup_callback)
            if self.update_timeout is None:
                self.update_timeout = GLib.timeout_add_seconds(5, self.update_all_networks)
        else:
            self.labels['networkinfo'] = Gtk.Label()
            self.labels['networkinfo'].get_style_context().add_class('temperature_entry')
            box.pack_start(self.labels['networkinfo'], False, False, 0)
            self.update_single_network_info()
            if self.update_timeout is None:
                self.update_timeout = GLib.timeout_add_seconds(5, self.update_single_network_info)

        self.content.add(box)
        self.labels['main_box'] = box
        self.initialized = True

    def load_networks(self, widget=None):
        networks = self.wifi.get_networks()
        if not networks:
            return
        for net in networks:
            self.add_network(net, False)
        self.update_all_networks()
        if widget:
            GLib.timeout_add_seconds(10, self._gtk.Button_busy, widget, False)
        self.content.show_all()
        return False

    def add_network(self, ssid, show=True):

        if ssid is None:
            return
        ssid = ssid.strip()
        if ssid in list(self.networks):
            return

        configured_networks = self.wifi.get_supplicant_networks()
        network_id = -1
        for net in list(configured_networks):
            if configured_networks[net]['ssid'] == ssid:
                network_id = net

        display_name = _("Hidden") if ssid.startswith("\x00") else f"{ssid}"
        netinfo = self.wifi.get_network_info(ssid)
        connected_ssid = self.wifi.get_connected_ssid()
        if netinfo is None:
            logging.debug("Couldn't get netinfo")
            netinfo = {'connected': connected_ssid == ssid}

        name = Gtk.Label(hexpand=True, halign=Gtk.Align.START, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        if connected_ssid == ssid:
            display_name += " (" + _("Connected") + ")"
            name.set_markup(f"<big><b>{display_name}</b></big>")
        else:
            name.set_label(display_name)

        info = Gtk.Label(halign=Gtk.Align.START)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True,
                         halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        labels.add(name)
        labels.add(info)

        connect = self._gtk.Button("load", None, "color3", self.bts)
        connect.connect("clicked", self.connect_network, ssid)
        connect.set_hexpand(False)
        connect.set_halign(Gtk.Align.END)

        delete = self._gtk.Button("delete", None, "color3", self.bts)
        delete.connect("clicked", self.remove_wifi_network, ssid)
        delete.set_hexpand(False)
        delete.set_halign(Gtk.Align.END)

        network = Gtk.Box(spacing=5, hexpand=True, vexpand=False)
        network.get_style_context().add_class("frame-item")
        network.add(labels)

        buttons = Gtk.Box(spacing=5)
        if network_id != -1 or netinfo['connected']:
            buttons.pack_end(connect, False, False, 0)
            buttons.pack_end(delete, False, False, 0)
        else:
            buttons.pack_end(connect, False, False, 0)
        network.add(buttons)
        self.networks[ssid] = network

        nets = sorted(list(self.networks), reverse=False)
        if connected_ssid in nets:
            nets.remove(connected_ssid)
            nets.insert(0, connected_ssid)
        if nets.index(ssid) is not None:
            pos = nets.index(ssid)
        else:
            logging.info("Error: SSID not in nets")
            return

        self.labels['networks'][ssid] = {
            "connect": connect,
            "delete": delete,
            "info": info,
            "name": name,
            "row": network
        }

        self.labels['networklist'].insert_row(pos)
        self.labels['networklist'].attach(self.networks[ssid], 0, pos, 1, 1)
        if show:
            self.labels['networklist'].show()

    def add_new_network(self, widget, ssid):
        self._screen.remove_keyboard()
        result = self.wifi.add_network(ssid, self.labels['network_psk'].get_text())
        self.close_add_network()
        if result:
            self.connect_network(widget, ssid, False)
        else:
            self._screen.show_popup_message(f"Error adding network {ssid}")

    def back(self):
        if self.show_add:
            self.close_add_network()
            return True
        return False

    def check_missing_networks(self):
        networks = self.wifi.get_networks()
        for net in list(self.networks):
            if net in networks:
                networks.remove(net)

        for net in networks:
            self.add_network(net, False)
        self.labels['networklist'].show_all()

    def close_add_network(self):
        if not self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels['main_box'])
        self.content.show()
        for i in ['add_network', 'network_psk']:
            if i in self.labels:
                del self.labels[i]
        self.show_add = False

    def popup_callback(self, msg):
        self._screen.show_popup_message(msg)

    def connected_callback(self, ssid, prev_ssid):
        logging.info("Now connected to a new network")
        if ssid is not None:
            self.remove_network(ssid)
        if prev_ssid is not None:
            self.remove_network(prev_ssid)

        self.check_missing_networks()

    def connect_network(self, widget, ssid, showadd=True):
        isdef = any(net['ssid'] == ssid for netid, net in self.wifi.get_supplicant_networks().items())
        if not isdef:
            if showadd:
                self.show_add_network(widget, ssid)
            return
        self.prev_network = self.wifi.get_connected_ssid()

        buttons = [
            {"name": _("Close"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = self._gtk.ScrolledWindow()
        self.labels['connecting_info'] = Gtk.Label(
            label=_("Starting WiFi Association"), halign=Gtk.Align.START, valign=Gtk.Align.START, wrap=True)
        scroll.add(self.labels['connecting_info'])
        self._gtk.Dialog(_("Starting WiFi Association"), buttons, scroll, self._gtk.remove_dialog)
        self._screen.show_all()

        if ssid in list(self.networks):
            self.remove_network(ssid)
        if self.prev_network in list(self.networks):
            self.remove_network(self.prev_network)

        self.wifi.add_callback("connecting_status", self.connecting_status_callback)
        self.wifi.connect(ssid)

    def connecting_status_callback(self, msg):
        self.labels['connecting_info'].set_text(f"{self.labels['connecting_info'].get_text()}\n{msg}")
        self.labels['connecting_info'].show_all()

    def remove_network(self, ssid, show=True):
        if ssid not in list(self.networks):
            return
        for i in range(len(self.labels['networklist'])):
            if self.networks[ssid] == self.labels['networklist'].get_child_at(0, i):
                self.labels['networklist'].remove_row(i)
                self.labels['networklist'].show()
                del self.networks[ssid]
                del self.labels['networks'][ssid]
                return

    def remove_wifi_network(self, widget, ssid):
        self.wifi.delete_network(ssid)
        self.remove_network(ssid)
        self.check_missing_networks()

    def scan_callback(self, new_networks, old_networks):
        for net in old_networks:
            self.remove_network(net, False)
        for net in new_networks:
            self.add_network(net, False)
        self.content.show_all()

    def show_add_network(self, widget, ssid):
        if self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)

        if "add_network" in self.labels:
            del self.labels['add_network']

        label = Gtk.Label(label=_("PSK for") + ' ssid', hexpand=False)
        self.labels['network_psk'] = Gtk.Entry(hexpand=True)
        self.labels['network_psk'].connect("activate", self.add_new_network, ssid)
        self.labels['network_psk'].connect("focus-in-event", self._screen.show_keyboard)

        save = self._gtk.Button("sd", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.add_new_network, ssid)

        box = Gtk.Box()
        box.pack_start(self.labels['network_psk'], True, True, 5)
        box.pack_start(save, False, False, 5)

        self.labels['add_network'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, valign=Gtk.Align.CENTER,
                                             hexpand=True, vexpand=True)
        self.labels['add_network'].pack_start(label, True, True, 5)
        self.labels['add_network'].pack_start(box, True, True, 5)

        self.content.add(self.labels['add_network'])
        self.labels['network_psk'].grab_focus_without_selecting()
        self.content.show_all()
        self.show_add = True

    def update_all_networks(self):
        for network in list(self.networks):
            self.update_network_info(network)
        return True

    def update_network_info(self, ssid):
        info = freq = encr = chan = lvl = ipv4 = ipv6 = ""

        if ssid not in list(self.networks) or ssid not in self.labels['networks']:
            logging.info(f"Unknown SSID {ssid}")
            return
        netinfo = self.wifi.get_network_info(ssid)
        if netinfo.get('connected') or self.wifi.get_connected_ssid() == ssid:
            ifadd = netifaces.ifaddresses(self.interface)
            if ifadd.get(netifaces.AF_INET):
                ipv4 = f"<b>IPv4:</b> {ifadd[netifaces.AF_INET][0]['addr']}"
                self.labels['ip'].set_text(f"IP: {ifadd[netifaces.AF_INET][0]['addr']}  ")
            if ifadd.get(netifaces.AF_INET6):
                ipv6 = f"<b>IPv6:</b> {ifadd[netifaces.AF_INET6][0]['addr'].split('%')[0]}"

            info = '<b>' + _("Hostname") + f':</b> {os.uname().nodename}\n{ipv4}\n{ipv6}'
        else:
            self.labels['networks'][ssid]['name'].set_label(_("Hidden") if ssid.startswith("\x00") else f"{ssid}")
            if "psk" in netinfo:
                info = _("Password saved")
        if "encryption" in netinfo and netinfo['encryption'] != "off":
            encr = netinfo['encryption'].upper()
        if "frequency" in netinfo:
            freq = "2.4 GHz" if netinfo['frequency'][:1] == "2" else "5 Ghz"
        if "channel" in netinfo:
            chan = _("Channel") + f' {netinfo["channel"]}'
        if "signal_level_dBm" in netinfo:
            unit = "%" if self.use_network_manager else _("dBm")
            lvl = f"{netinfo['signal_level_dBm']} {unit}"
            icon = self.signal_strength(int(netinfo["signal_level_dBm"]))
            if 'icon' not in self.labels['networks'][ssid]:
                self.labels['networks'][ssid]['row'].add(icon)
                self.labels['networks'][ssid]['row'].reorder_child(icon, 0)
                self.labels['networks'][ssid]['icon'] = icon
            self.labels['networks'][ssid]['icon'] = icon

        self.labels['networks'][ssid]['info'].set_markup(f"{info}\n<small>{encr}  {freq}  {chan}  {lvl}</small>")
        self.labels['networks'][ssid]['row'].show_all()

    def signal_strength(self, signal_level):
        # networkmanager uses percentage not dbm
        # the bars of nmcli are aligned near this breakpoints
        exc = 77 if self.use_network_manager else -50
        good = 60 if self.use_network_manager else -60
        fair = 35 if self.use_network_manager else -70
        if signal_level > exc:
            return self._gtk.Image('wifi_excellent')
        elif signal_level > good:
            return self._gtk.Image('wifi_good')
        elif signal_level > fair:
            return self._gtk.Image('wifi_fair')
        else:
            return self._gtk.Image('wifi_weak')

    def update_single_network_info(self):
        ifadd = netifaces.ifaddresses(self.interface)
        ipv6 = f"{ifadd[netifaces.AF_INET6][0]['addr'].split('%')[0]}" if ifadd.get(netifaces.AF_INET6) else ""
        if netifaces.AF_INET in ifadd and ifadd[netifaces.AF_INET]:
            ipv4 = f"{ifadd[netifaces.AF_INET][0]['addr']} "
            self.labels['ip'].set_text(f"IP: {ifadd[netifaces.AF_INET][0]['addr']}  ")
        else:
            ipv4 = ""
        self.labels['networkinfo'].set_markup(
            f'<b>{self.interface}</b>\n\n'
            + '<b>' + _("Hostname") + f':</b> {os.uname().nodename}\n'
            f'<b>IPv4:</b> {ipv4}\n'
            f'<b>IPv6:</b> {ipv6}'
        )
        self.labels['networkinfo'].show_all()
        return True

    def reload_networks(self, widget=None):
        self.networks = {}
        self.labels['networklist'].remove_column(0)
        if self.wifi is not None and self.wifi.initialized:
            if widget:
                self._gtk.Button_busy(widget, True)
            self.wifi.rescan()
            GLib.idle_add(self.load_networks, widget)

    def activate(self):
        if self.initialized:
            self.reload_networks()
            if self.update_timeout is None:
                if self.wifi is not None and self.wifi.initialized:
                    self.update_timeout = GLib.timeout_add_seconds(5, self.update_all_networks)
                else:
                    self.update_timeout = GLib.timeout_add_seconds(5, self.update_single_network_info)

    def deactivate(self):
        if self.update_timeout is not None:
            GLib.source_remove(self.update_timeout)
            self.update_timeout = None
