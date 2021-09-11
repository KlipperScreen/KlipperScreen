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

        conf = self._config.get_printer_config(self._screen.connected_printer)
        logging.info("conf: %s" % conf)
        protocol = conf.get("webcam_protocol", "http")
        ip = conf["webcam_host"] if "webcam_host" in conf else (
            conf["moonraker_host"] if "moonraker_host" in conf else "127.0.0.1")
        port = conf.get("webcam_port", "80")
        uri = conf.get("webcam_url", "webcam/?action=stream")

        self.url = "%s://%s:%s/%s" % (protocol, ip, port, uri)
        logging.debug("Webcam URL: " + self.url)

    def activate(self):
        videoPlayer = VLCWidget(self._screen.width - 160, self._screen.height - 120)
        videoPlayer.player.set_mrl(self.url)
        videoPlayer.player.play()

        self.videoPlayer = videoPlayer
        self.content.add(videoPlayer)

    def deactivate(self):
        self.content.remove(self.videoPlayer)
        self.videoPlayer = None
