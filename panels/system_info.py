import subprocess
import logging
import platform
import getmac
import socket
import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):

        super().__init__(screen, title)
        self.menu = ['system_info']

        self.image = self._gtk.Image(f"settings", self._gtk.content_width * 4, self._gtk.content_height * .6)
        self.info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.info.pack_start(self.image, True, True, 8)

        self.content.add(self.info)

        self.text: str = f"""
        {_('Hostname')}: {socket.gethostname()}
        {_('Platform')}: {platform.platform()}
        {_('Version')}: {platform.release()}
        {_('System')}: {platform.system()}
        {_('Mac')}: {getmac.get_mac_address()}
        """

        self.labels['text'] = Gtk.Label(f"{self.text}")
        self.labels['text'].set_line_wrap(True)
        self.labels['text'].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.labels['text'].set_halign(Gtk.Align.CENTER)
        self.labels['text'].set_valign(Gtk.Align.CENTER)

        self.content.add(self.labels['text'])

        grid = Gtk.Grid()

        self.labels['system_info'] = Gtk.Grid()
        self.labels['system_info'].attach(grid, 0, 0, 2, 2)
        self.content.add(self.labels['system_info'])

    def get_mac_address(self, ip_address):
        arp_command = ['arp', '-n', ip_address]
        output = subprocess.check_output(arp_command).decode()
        mac_address = output.split()[3]
        return mac_address
