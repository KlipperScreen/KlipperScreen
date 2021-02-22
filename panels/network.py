import gi
import logging
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
    interface = "wlan0"

    def initialize(self, menu):
        _ = self.lang.gettext
        grid = self._gtk.HomogeneousGrid()
        grid.set_hexpand(True)

        # Get Hostname
        stream = os.popen('hostname -A')
        hostname = stream.read()
        # Get IP Address
        stream = os.popen('hostname -I')
        ip = stream.read()

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
        box.pack_start(sbox, False, False, 0)
        box.pack_start(scroll, True, True, 0)

        self.labels['networklist'] = Gtk.Grid()
        self.files = {}

        GLib.idle_add(self.load_networks)

        scroll.add(self.labels['networklist'])

        #self.labels['networkinfo'] = Gtk.Label(
        #    _("Network Info") + "\n\n%s%s" % (hostname, ip)
        #)
        #self.labels['networkinfo'].get_style_context().add_class('temperature_entry')
        #grid.attach(self.labels['networkinfo'], 1, 0, 1, 1)

        self.content.add(box)

    def load_networks(self):
        networks = self._screen.wifi.get_networks()
        for net in networks:
            self.add_network(net, False)

        self.content.show_all()

    def add_network(self, essid, show=True):
        _ = self.lang.gettext

        netinfo = self._screen.wifi.get_network_info(essid)
        if netinfo == None:
            return
        
        # For now, only add connected network
        if "connected" not in netinfo:
            return

        frame = Gtk.Frame()
        frame.set_property("shadow-type",Gtk.ShadowType.NONE)
        frame.get_style_context().add_class("frame-item")


        name = Gtk.Label()
        name.set_markup("<big><b>%s</b></big>" % (essid))
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        stream = os.popen('ip add show dev %s' % self.interface)
        content = stream.read()
        ipv4_re = re.compile(r'inet ([0-9\.]+)/[0-9]+', re.MULTILINE)
        ipv6_re = re.compile(r'inet6 ([a-fA-F0-9:\.]+)/[0-9+]', re.MULTILINE)
        match = ipv4_re.search(content)
        ipv4 = ""
        if match:
            ipv4 = "<b>%s:</b> %s " % (_("IPv4"), match.group(1))
        match = ipv6_re.search(content)
        ipv6 = ""
        if match:
            ipv6 = "<b>%s:</b> %s " % (_("IPv6"), match.group(1))


        stream = os.popen('hostname -f')
        hostname = stream.read().strip()

        connected = ""
        if "connected" in netinfo:
            connected = "<b>%s</b>\n<b>%s:</b> %s\n%s%s\n" % (_("Connected"),_("Hostname"),hostname, ipv4, ipv6)
        elif "psk" in netinfo:
            connected = "Password saved."
        freq = "2.4 GHz" if netinfo['frequency'][0:1] == "2" else "5 Ghz"
        info = Gtk.Label()
        info.set_markup("%s%s <small>%s %s %s  %s%s</small>" % ( connected,
            "" if netinfo['encryption'] == "off" else netinfo['encryption'].upper(),
            freq, _("Channel"), netinfo['channel'], netinfo['signal_level_dBm'], _("dBm")
            ))
        info.set_halign(Gtk.Align.START)
        #info.set_markup(self.get_file_info_str(essid))
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)
        labels.add(info)
        labels.set_vexpand(True)
        labels.set_valign(Gtk.Align.CENTER)
        labels.set_halign(Gtk.Align.START)

        actions = self._gtk.ButtonImage("print",None,"color3")
        #actions.connect("clicked", self.confirm_print, essid)
        actions.set_hexpand(False)
        actions.set_halign(Gtk.Align.END)

        network = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        network.set_hexpand(True)
        network.set_vexpand(False)

        network.add(labels)
        if not "connected" in netinfo:
            network.add(actions)

        self.networks[essid] = frame
        frame.add(network)

        reverse = False
        nets = sorted(self.networks, reverse=reverse)
        pos = nets.index(essid)
        if "connected" in netinfo:
            pos = 0
        elif self._screen.wifi.is_connected():
            pos += 1

        self.labels['networks'][essid] = {
            "info": info,
            "name": name,
            "row": network
        }

        self.labels['networklist'].insert_row(pos)
        self.labels['networklist'].attach(self.networks[essid], 0, pos, 1, 1)
        if show == True:
            self.labels['networklist'].show_all()
