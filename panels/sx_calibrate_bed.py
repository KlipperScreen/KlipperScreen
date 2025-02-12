import logging
import threading
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Bed Calibration")
        super().__init__(screen, title)

        self.menu = ['screws-adjust']

        self.started: bool = False
        self.screws_adjusted = 0

        self.buttons = {
            'START': self._gtk.Button("resume", _("Start"), "color1"),
            'CANCEL': self._gtk.Button("cancel", _("Abort"), "color2"),
            'NOW_ADJUSTED': self._gtk.Button("arrow-right", _("This screw is now Adjusted"), "color4"),
            'ALREADY_ADJUSTED': self._gtk.Button("arrow-right", _("This screw is already Adjusted"), "color4"),
            'FINISH': self._gtk.Button("complete", _("Finish"), "color2"),
        }
        self.buttons['START'].connect("clicked", self.screws_tilt_calculate)
        self.buttons['CANCEL'].connect("clicked", self.abort)
        self.buttons['NOW_ADJUSTED'].connect("clicked", self.adjusted)
        self.buttons['ALREADY_ADJUSTED'].connect("clicked", self.accept)
        self.buttons['FINISH'].connect("clicked", self.finish)

        self.off_state()

        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)

        grid.attach(self.buttons['START'], 0, 0, 1, 3)
        grid.attach(self.buttons['CANCEL'], 1, 2, 1, 1)
        grid.attach(self.buttons['FINISH'], 2, 2, 1, 1)
        grid.attach(self.buttons['NOW_ADJUSTED'], 1, 0, 2, 1)
        grid.attach(self.buttons['ALREADY_ADJUSTED'], 1, 1, 2, 1)

        self.labels['screws-adjust'] = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        self.labels['screws-adjust'].attach(grid, 0, 0, 1, 3)

        self.content.add(self.labels['screws-adjust'])

    def abort(self, widget):
        self.off_state()
        logging.info("Aborting screws adjust")
        self._screen._ws.klippy.gcode_script("ABORT")
        self._screen._menu_go_back()

    def off_state(self):
        self.started = False
        self.buttons['START'].set_sensitive(True)
        self.buttons['FINISH'].set_sensitive(False)
        self.buttons['CANCEL'].set_sensitive(False)
        self.buttons['NOW_ADJUSTED'].set_sensitive(False)
        self.buttons['ALREADY_ADJUSTED'].set_sensitive(False)

    def check_finish(self):
        return self.started and self.screws_adjusted == 3

    def accept(self, widget):
        """Screw is already adjusted"""
        if self.started:
            self.screws_adjusted += 1
            self._screen._ws.klippy.gcode_script("ACCEPT")
            if self.check_finish():
                self.buttons['NOW_ADJUSTED'].set_sensitive(False)
                self.buttons['ALREADY_ADJUSTED'].set_sensitive(False)
                self.buttons['CANCEL'].set_sensitive(False)
                self.buttons['FINISH'].set_sensitive(True)
                return

    def adjusted(self, widget):
        """Screw has been adjusted"""
        if self.started:
            self.screws_adjusted = 0
            self._screen._ws.klippy.gcode_script("ADJUSTED")

    def home(self):
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script(KlippyGcodes.HOME_ALL)
        if self._printer.config_section_exists("z_tilt"):
            self._screen._ws.klippy.gcode_script("Z_TILT_ADJUST")

    def allow_screws_btn(self):
        self.buttons['CANCEL'].set_sensitive(True)
        self.buttons['NOW_ADJUSTED'].set_sensitive(True)
        self.buttons['ALREADY_ADJUSTED'].set_sensitive(True)

    def screws_tilt_calculate(self, widget):
        self._screen._ws.klippy.gcode_script("BED_SCREWS_ADJUST")
        self.started = True
        self.buttons['START'].set_sensitive(False)

        # Fallback if notify_busy: False is not emmited
        timer = threading.Timer(39.0, self.allow_screws_btn)
        timer.start()

    def finish(self, button):
        self.off_state()
        self._screen._ws.klippy.gcode_script("G28")
        self._screen._menu_go_back()

    def process_update(self, action, data):
        if action == "notify_busy":
            if not self.started or self.check_finish():
                return
            
            is_busy: bool = data

            if is_busy:
                self.buttons['NOW_ADJUSTED'].set_sensitive(False)
                self.buttons['ALREADY_ADJUSTED'].set_sensitive(False)
                self.buttons['CANCEL'].set_sensitive(False)
            else:
                self.buttons['NOW_ADJUSTED'].set_sensitive(True)
                self.buttons['ALREADY_ADJUSTED'].set_sensitive(True)
                self.buttons['CANCEL'].set_sensitive(True)