import logging
import mpv

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from contextlib import suppress
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Camera")
        super().__init__(screen, title)
        self.mpv = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for i, cam in enumerate(self._printer.cameras):
            if not cam["enabled"]:
                continue
            logging.info(cam)
            cam[cam["name"]] = self._gtk.Button(
                image_name="camera", label=cam["name"], style=f"color{i % 4 + 1}",
                scale=self.bts, position=Gtk.PositionType.LEFT, lines=1
            )
            cam[cam["name"]].set_hexpand(True)
            cam[cam["name"]].set_vexpand(True)
            cam[cam["name"]].connect("clicked", self.play, cam)
            box.add(cam[cam["name"]])

        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(box)
        self.content.add(self.scroll)
        self.content.show_all()

    def activate(self):
        # if only 1 cam start playing fullscreen
        if len(self._printer.cameras) == 1:
            cam = next(iter(self._printer.cameras))
            if cam['enabled']:
                self.play(None, cam)

    def deactivate(self):
        if self.mpv:
            self.mpv.terminate()
            self.mpv = None

    def play(self, widget, cam):
        url = cam['stream_url']
        if url.startswith('/'):
            logging.info("camera URL is relative")
            endpoint = self._screen.apiclient.endpoint.split(':')
            url = f"{endpoint[0]}:{endpoint[1]}{url}"
        if '/webrtc' in url:
            self._screen.show_popup_message(_('WebRTC is not supported by the backend trying Stream'))
            url = url.replace('/webrtc', '/stream')
        vf_list = []
        if cam["flip_horizontal"]:
            vf_list.append("hflip")
        if cam["flip_vertical"]:
            vf_list.append("vflip")
        if cam["rotation"] != 0:
            vf_list.append(f"rotate:{cam['rotation'] * 3.14159 / 180}")
        logging.info(f"video filters: {vf_list}")

        if self.mpv:
            self.mpv.terminate()
        self.mpv = mpv.MPV(fullscreen=True, log_handler=self.log, vo='gpu,wlshm,xv,x11')

        self.mpv.vf = ','.join(vf_list)

        with suppress(Exception):
            self.mpv.profile = 'sw-fast'

        # LOW LATENCY PLAYBACK
        with suppress(Exception):
            self.mpv.profile = 'low-latency'
        self.mpv.untimed = True
        self.mpv.audio = 'no'

        @self.mpv.on_key_press('MBTN_LEFT' or 'MBTN_LEFT_DBL')
        def clicked():
            self.mpv.quit(0)

        logging.debug(f"Camera URL: {url}")
        self.mpv.play(url)

        try:
            self.mpv.wait_for_playback()
        except mpv.ShutdownError:
            logging.info('Exiting Fullscreen')
        except Exception as e:
            logging.exception(e)
        self.mpv.terminate()
        self.mpv = None
        if len(self._printer.cameras) == 1:
            self._screen._menu_go_back()

    def log(self, loglevel, component, message):
        if (
            'unable to decode' in message  # skip proprietary app fields errors
            or 'No Xvideo support found' in message  # will fall back to other vo automatically
            or 'GBM' in message  # will fall back to other vo automatically
            or 'open TTY for VT control' in message  # not important to notify in the UI
            or 'youtube-dl' in message  # needed for some streams, not relevant for our case
        ):
            return
        if loglevel == 'error':
            self._screen.show_popup_message(f'{message}')
        logging.debug(f'[{loglevel}] {component}: {message}')
