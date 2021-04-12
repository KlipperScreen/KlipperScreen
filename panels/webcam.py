import gi
import logging
import vlc
import os

gi.require_version("Gtk", "3.0")
gi.require_version('GdkX11', '3.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gtk, Gdk, GLib, GdkX11, Gst

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

Gst.init(None)
Gst.init_check(None)

def get_window_pointer(window):
    """ Use the window.__gpointer__ PyCapsule to get the C void* pointer to the window
    """
    # get the c gpointer of the gdk window
    ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
    ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object]
    return ctypes.pythonapi.PyCapsule_GetPointer(window.__gpointer__, None)

def create_panel(*args):
    return WebcamPanel(*args)

instance = vlc.Instance("--no-xlib")

class VLCWidget(Gtk.DrawingArea):
    """Simple VLC widget.
    Its player can be controlled through the 'player' attribute, which
    is a vlc.MediaPlayer() instance.
    """
    __gtype_name__ = 'VLCWidget'

    def __init__(self, width, height):
        Gtk.DrawingArea.__init__(self)
        self.player = instance.media_player_new()
        def handle_embed(*args):
            self.player.set_xwindow(self.get_window().get_xid())
            return True
        self.connect("realize", handle_embed)
        self.set_size_request(width, height)

class WebcamPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext

        ip = "127.0.0.1"
        connectedPrinterName = self._screen.connected_printer
        for printer in self._screen._config.get_printers():
            printerName = list(printer)[0]

            if printerName != connectedPrinterName:
                continue
            ip = printer[printerName]["moonraker_host"]
            break

        uri = "/webcam/?action=stream"
        url = "http://" + ip + uri

        logging.debug("Webcam URL: " + url)

        videoPlayer = VLCWidget(self._screen.width - 100, self._screen.height - 100)
        videoPlayer.player.set_mrl(url)
        videoPlayer.player.play()

        self.content.add(videoPlayer)
