import mpv
import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return CameraPanel(*args)


class CameraPanel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.mpv = None
        self.da = Gtk.DrawingArea()
        self.da.set_hexpand(True)
        self.da.set_vexpand(True)
        fs = self._gtk.Button("move", _("Fullscreen"), None, self.bts, Gtk.PositionType.LEFT, 1)
        fs.connect("clicked", self.play)
        fs.set_hexpand(True)
        fs.set_vexpand(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(self.da)
        box.add(fs)
        self.content.add(box)
        self.content.show_all()
        self.url = self.ks_printer_cfg.get("camera_url", "http://127.0.0.1/webcam/?action=stream").replace('"', '')
        # wayland has no primary monitor with that we can detect it
        self.wayland = Gdk.Display.get_default().get_primary_monitor() is None
        # gpu output driver doesn't work on a pi3 and the autoselected sdl doesn't size correctly
        # consider adding a software switch to enable the gpu backend if set by the user
        self.vo = 'wlshm' if self.wayland else 'x11'
        logging.debug(f"Camera URL: {self.url} vo: {self.vo} wayland: {self.wayland}")

    def activate(self):
        self.play()

    def deactivate(self):
        if self.mpv:
            self.mpv.terminate()
            self.mpv = None

    def play(self, fs=None):
        if self.mpv:
            self.mpv.terminate()
            self.mpv = None
        # Create mpv after show or the 'window' property will be None
        try:
            self.mpv = mpv.MPV(
                log_handler=self.log,
                vo=self.vo,
                profile='sw-fast',
            )
        except ValueError:
            self.mpv = mpv.MPV(
                log_handler=self.log,
                vo=self.vo,
            )
        # On wayland mpv cannot be embedded at least for now
        # https://github.com/mpv-player/mpv/issues/9654
        # if fs or self.wayland:
        self.mpv.fullscreen = True

        @self.mpv.on_key_press('MBTN_LEFT' or 'MBTN_LEFT_DBL')
        def clicked():
            self.mpv.quit(0)
        # else:
        #     self.mpv.wid = f'{self.da.get_property("window").get_xid()}'
        #
        #     @self.mpv.on_key_press('MBTN_LEFT' or 'MBTN_LEFT_DBL')
        #     def clicked():
        #         self._screen.show_popup_message(self.url, level=1)
        self.mpv.play(self.url)
        # if fs or self.wayland:
        try:
            self.mpv.wait_for_playback()
        except mpv.ShutdownError:
            logging.info('Exiting Fullscreen')
        except Exception as e:
            logging.exception(e)
        self.mpv.terminate()
        self.mpv = None
        self._screen._menu_go_back()

    @staticmethod
    def log(loglevel, component, message):
        logging.debug(f'[{loglevel}] {component}: {message}')
