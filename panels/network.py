import gi
import json
import logging
import netifaces
import os
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return NetworkPanel(*args)

class NetworkPanel(ScreenPanel):
    networks = {}
    network_list = []

    def initialize(self, menu):
        _ = self.lang.gettext
        grid = self._gtk.HomogeneousGrid()
        grid.set_hexpand(True)

        # Get Hostname
        stream = os.popen('hostname -A')
        hostname = stream.read()
        # Get IP Address
        gws = netifaces.gateways()
        if "default" in gws and netifaces.AF_INET in gws["default"]:
            self.interface = gws["default"][netifaces.AF_INET][1]
        else:
            ints = netifaces.interfaces()
            if 'lo' in ints:
                ints.pop('lo')
            self.interfaces = ints[0]

        res = netifaces.ifaddresses(self.interface)
        if netifaces.AF_INET in res and len(res[netifaces.AF_INET]) > 0:
            ip = res[netifaces.AF_INET][0]['addr']
        else:
            ip = "0.0.0.0"

        self.labels['networks'] = {}

        self.labels['interface'] = Gtk.Label()
        self.labels['interface'].set_text(" %s: %s" % (_("Interface"), self.interface))
        self.labels['disconnect'] = self._gtk.Button(_("Disconnect"), "color2")


        sbox = Gtk.Box()
        sbox.set_hexpand(True)
        sbox.set_vexpand(False)
        sbox.add(self.labels['interface'])
        #sbox.add(self.labels['disconnect'])


        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)

        self.labels['networklist'] = Gtk.Grid()
        self.files = {}

        if self._screen.wifi != None and self._screen.wifi.is_initialized():
            box.pack_start(sbox, False, False, 0)
            box.pack_start(scroll, True, True, 0)

            GLib.idle_add(self.load_networks)
            scroll.add(self.labels['networklist'])

            self._screen.wifi.add_callback("connected", self.connected_callback)
            self._screen.wifi.add_callback("scan_results", self.scan_callback)
            self.timeout = GLib.timeout_add_seconds(5, self.update_all_networks)
        else:
            self.labels['networkinfo'] = Gtk.Label("")
            self.labels['networkinfo'].get_style_context().add_class('temperature_entry')
            box.pack_start(self.labels['networkinfo'], False, False, 0)
            self.update_single_network_info()
            self.timeout = GLib.timeout_add_seconds(5, self.update_single_network_info)

        self.content.add(box)
        self.labels['main_box'] = box

    def load_networks(self):
        networks = self._screen.wifi.get_networks()

        conn_ssid = self._screen.wifi.get_connected_ssid()
        if conn_ssid in networks:
            networks.remove(conn_ssid)
        self.add_network(conn_ssid, False)

        for net in networks:
            self.add_network(net, False)

        self.update_all_networks()
        self.content.show_all()

    def add_network(self, ssid, show=True):
        _ = self.lang.gettext

        if ssid == None:
            return
        ssid = ssid.strip()

        if ssid in list(self.networks):
            logging.info("SSID already listed")
            return

        netinfo = self._screen.wifi.get_network_info(ssid)
        if netinfo == None:
            logging.debug("Couldn't get netinfo")
            return

        configured_networks = self._screen.wifi.get_supplicant_networks()
        network_id = -1
        for net in list(configured_networks):
            if configured_networks[net]['ssid'] == ssid:
                network_id = net

        frame = Gtk.Frame()
        frame.set_property("shadow-type",Gtk.ShadowType.NONE)
        frame.get_style_context().add_class("frame-item")


        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (ssid))
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        info = Gtk.Label()
        info.set_halign(Gtk.Align.START)
        #info.set_markup(self.get_file_info_str(ssid))
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)
        labels.add(info)
        labels.set_vexpand(True)
        labels.set_valign(Gtk.Align.CENTER)
        labels.set_halign(Gtk.Align.START)

        connect = self._gtk.ButtonImage("load",None,"color3")
        connect.connect("clicked", self.connect_network, ssid)
        connect.set_hexpand(False)
        connect.set_halign(Gtk.Align.END)

        delete = self._gtk.ButtonImage("delete","","color3")
        delete.connect("clicked", self.remove_wifi_network, ssid)
        delete.set_size_request(60,0)
        delete.set_hexpand(False)
        delete.set_halign(Gtk.Align.END)

        network = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        network.set_hexpand(True)
        network.set_vexpand(False)

        network.add(labels)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        if network_id != -1:
            buttons.pack_end(delete, False, False, 0)
        if netinfo['connected'] == False:
            buttons.pack_end(connect, False, False, 0)

        network.add(buttons)

        self.networks[ssid] = frame
        frame.add(network)

        reverse = False

        pos = 0
        if netinfo['connected'] == True:
            pos = 0
        else:
            connected_ssid = self._screen.wifi.get_connected_ssid()
            nets = list(self.networks)
            if connected_ssid != None:
                if connected_ssid in nets:
                    nets.remove(connected_ssid)
            nets = sorted(nets, reverse=reverse)
            pos = nets.index(ssid)
            if connected_ssid != None:
                pos += 1

        self.labels['networks'][ssid] = {
            "connect": connect,
            "delete": delete,
            "info": info,
            "name": name,
            "row": network
        }

        self.labels['networklist'].insert_row(pos)
        self.labels['networklist'].attach(self.networks[ssid], 0, pos, 1, 1)
        if show == True:
            self.labels['networklist'].show()

    def add_new_network(self, widget, ssid, connect=False):
        networks = self._screen.wifi.get_networks()
        psk = self.labels['network_psk'].get_text()
        result = self._screen.wifi.add_network(ssid, psk)

        self.close_add_network(widget, ssid)

        if connect == True:
            if result == True:
                self.connect_network(widget, ssid, False)
            else:
                self._screen.show_popup_message("Error adding network %s" % ssid)

    def check_missing_networks(self):
        networks = self._screen.wifi.get_networks()
        for net in list(self.networks):
            if net in networks:
                networks.remove(net)

        for net in networks:
            self.add_network(net)
        self.labels['networklist'].show_all()

    def close_add_network(self, widget, ssid):
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels['main_box'])
        self.content.show()

    def close_dialog(self, widget, response_id):
        widget.destroy()

    def connected_callback(self, ssid, prev_ssid):
        logging.info("Now connected to a new network")
        if ssid != None:
            self.remove_network(ssid)
        if prev_ssid != None:
            self.remove_network(prev_ssid)

        self.check_missing_networks()

    def connect_network(self, widget, ssid, showadd=True):
        _ = self.lang.gettext

        snets = self._screen.wifi.get_supplicant_networks()
        isdef = False
        for id, net in snets.items():
            if net['ssid'] == ssid:
                isdef = True
                break

        if isdef == False:
            if showadd == True:
                self.show_add_network(widget, ssid)
            return
        self.prev_network = self._screen.wifi.get_connected_ssid()

        buttons = [
            {"name": _("Close"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_size_request(800,400)
        self.labels['connecting_info'] = Gtk.Label(_("Starting WiFi Re-association"))
        self.labels['connecting_info'].set_halign(Gtk.Align.START)
        self.labels['connecting_info'].set_valign(Gtk.Align.START)
        scroll.add(self.labels['connecting_info'])
        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.close_dialog)
        self._screen.show_all()

        if ssid in self.networks:
            self.remove_network(ssid)
        if self.prev_network in self.networks:
            self.remove_network(self.prev_network)
            #GLib.timeout_add(500, self.add_network, self.prev_network)

        self._screen.wifi.add_callback("connecting_status", self.connecting_status_callback)
        self._screen.wifi.connect(ssid)

    def connecting_status_callback(self, msg):
        self.labels['connecting_info'].set_text(self.labels['connecting_info'].get_text() + "\n" + msg)
        self.labels['connecting_info'].show_all()

    def remove_network(self, ssid, show=True):
        if ssid not in self.networks:
            return

        i = 0
        while self.labels['networklist'].get_child_at(0, i) != None:
            if self.networks[ssid] == self.labels['networklist'].get_child_at(0, i):
                self.labels['networklist'].remove_row(i)
                self.labels['networklist'].show()
                del self.networks[ssid]
                del self.labels['networks'][ssid]
                return
            i = i+1
        return

    def remove_network_wid(self, widget, ssid):
        self.remove_network(ssid)

    def remove_wifi_network(self, widget, ssid):
        self._screen.wifi.delete_network(ssid)
        self.remove_network(ssid)
        self.check_missing_networks()

    def scan_callback(self, new_networks, old_networks):
        for net in old_networks:
            self.remove_network(net, False)
        for net in new_networks:
            self.add_network(net, False)
        self.content.show_all()

    def show_add_network(self, widget, ssid):
        _ = self.lang.gettext
        for child in self.content.get_children():
            self.content.remove(child)

        if "add_network" in self.labels:
            del self.labels['add_network']

        self.labels['add_network'] = Gtk.VBox()
        self.labels['add_network'].set_valign(Gtk.Align.START)

        box = Gtk.Box(spacing=5)
        box.set_size_request(self._gtk.get_content_width(), self._gtk.get_content_height() -
                self._screen.keyboard_height - 20)
        box.set_hexpand(True)
        box.set_vexpand(False)
        self.labels['add_network'].add(box)

        l = self._gtk.Label("%s %s:" % (_("PSK for"), ssid))
        l.set_hexpand(False)
        entry = Gtk.Entry()
        entry.set_hexpand(True)

        save = self._gtk.ButtonImage("sd",_("Save"),"color3")
        save.set_hexpand(False)
        save.connect("clicked", self.add_new_network, ssid, True)


        self.labels['network_psk'] = entry
        box.pack_start(l, False, False, 5)
        box.pack_start(entry, True, True, 5)
        box.pack_start(save, False, False, 5)

        self.show_create = True
        self.labels['network_psk'].set_text('')
        self.content.add(self.labels['add_network'])
        self.content.show()
        self._screen.show_keyboard()
        self.labels['network_psk'].grab_focus_without_selecting()

    def update_all_networks(self):
        for network in list(self.networks):
            self.update_network_info(network)
        return True

    def update_network_info(self, ssid):
        _ = self.lang.gettext

        if ssid not in self.networks or ssid not in self.labels['networks']:
            return
        netinfo = self._screen.wifi.get_network_info(ssid)
        if netinfo == None:
            logging.debug("Couldn't get netinfo for update")
            return

        connected = ""
        if netinfo['connected'] == True:
            stream = os.popen('hostname -f')
            hostname = stream.read().strip()
            ifadd = netifaces.ifaddresses(self.interface)
            ipv4 = ""
            ipv6 = ""
            if netifaces.AF_INET in ifadd and len(ifadd[netifaces.AF_INET]) > 0:
                ipv4 = "<b>%s:</b> %s " % (_("IPv4"), ifadd[netifaces.AF_INET][0]['addr'])
            if netifaces.AF_INET6 in ifadd and len(ifadd[netifaces.AF_INET6]) > 0:
                ipv6 = ipv6 = "<b>%s:</b> %s " % (_("IPv6"), ifadd[netifaces.AF_INET6][0]['addr'].split('%')[0])
            connected = "<b>%s</b>\n<b>%s:</b> %s\n%s%s\n" % (_("Connected"),_("Hostname"),hostname, ipv4, ipv6)
        elif "psk" in netinfo:
            connected = "Password saved."
        freq = "2.4 GHz" if netinfo['frequency'][0:1] == "2" else "5 Ghz"

        self.labels['networks'][ssid]['info'].set_markup("%s%s <small>%s %s %s  %s%s</small>" % ( connected,
            "" if netinfo['encryption'] == "off" else netinfo['encryption'].upper(),
            freq, _("Channel"), netinfo['channel'], netinfo['signal_level_dBm'], _("dBm")
            ))
        self.labels['networks'][ssid]['info'].show_all()

    def update_single_network_info(self):
        _ = self.lang.gettext

        stream = os.popen('hostname -f')
        hostname = stream.read().strip()
        ifadd = netifaces.ifaddresses(self.interface)
        ipv4 = ""
        ipv6 = ""
        if netifaces.AF_INET in ifadd and len(ifadd[netifaces.AF_INET]) > 0:
            ipv4 = "<b>%s:</b> %s " % (_("IPv4"), ifadd[netifaces.AF_INET][0]['addr'])
        if netifaces.AF_INET6 in ifadd and len(ifadd[netifaces.AF_INET6]) > 0:
            ipv6 = ipv6 = "<b>%s:</b> %s " % (_("IPv6"), ifadd[netifaces.AF_INET6][0]['addr'].split('%')[0])
        connected = "<b>%s</b>\n\n<small><b>%s</b></small>\n<b>%s:</b> %s\n%s\n%s\n" % (self.interface, _("Connected"),_("Hostname"),
            hostname, ipv4, ipv6)

        self.labels['networkinfo'].set_markup(connected)
        self.labels['networkinfo'].show_all()
