import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.JobStatusPanel")

def create_panel(*args):
    return JobStatusPanel(*args)

class JobStatusPanel(ScreenPanel):
    is_paused = False
    filename = None

    def initialize(self, panel_name):
        _ = self.lang.gettext
        grid = KlippyGtk.HomogeneousGrid()

        self.labels['progress'] = KlippyGtk.ProgressBar("printing-progress-bar")
        #self.labels['progress'].set_vexpand(True)
        #self.labels['progress'].set_valign(Gtk.Align.CENTER)
        self.labels['progress'].set_show_text(False)
        #self.labels['progress'].set_margin_top(10)
        self.labels['progress'].set_margin_end(20)
        self.labels['progress_text'] = Gtk.Label()
        self.labels['progress_text'].get_style_context().add_class("printing-progress-text")
        overlay = Gtk.Overlay()
        overlay.add(self.labels['progress'])
        overlay.add_overlay(self.labels['progress_text'])

        self.labels['file'] = KlippyGtk.ImageLabel("file","",20,"printing-status-label")
        self.labels['time_label'] = KlippyGtk.ImageLabel("speed-step",_("Time Elapsed"),20,"printing-status-label")
        self.labels['time'] = KlippyGtk.Label(_("Time Elapsed"),"printing-status-label")
        self.labels['time_left_label'] = KlippyGtk.ImageLabel("speed-step",_("Time Left"),20,"printing-status-label")
        self.labels['time_left'] = KlippyGtk.Label(_("Time Left"),"printing-status-label")
        timegrid = Gtk.Grid()
        timegrid.attach(self.labels['time_label']['b'], 0, 0, 1, 1)
        timegrid.attach(self.labels['time'], 0, 1, 1, 1)
        timegrid.attach(self.labels['time_left_label']['b'], 1, 0, 1, 1)
        timegrid.attach(self.labels['time_left'], 1, 1, 1, 1)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info.props.valign = Gtk.Align.CENTER
        info.set_hexpand(True)
        info.set_vexpand(True)
        #info.add(self.labels['file']['b'])
        #info.add(self.labels['time']['b'])
        #info.add(self.labels['time_left']['b'])

        #grid.attach(info,2,0,2,1)

        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pbox.pack_start(self.labels['file']['b'], False, True, 0)
        pbox.pack_end(timegrid, False, False, 0)
        #pbox.pack_end(self.labels['progress'], False, False, 0)
        pbox.pack_end(overlay, False, False, 0)

        grid.attach(pbox, 1, 0, 3, 2)

        self.labels['extruder'] = KlippyGtk.ButtonImage("extruder-1", KlippyGtk.formatTemperatureString(0, 0))
        self.labels['extruder'].set_sensitive(False)
        grid.attach(self.labels['extruder'], 0, 0, 1, 1)

        self.labels['heater_bed'] = KlippyGtk.ButtonImage("bed", KlippyGtk.formatTemperatureString(0, 0))
        self.labels['heater_bed'].set_sensitive(False)
        grid.attach(self.labels['heater_bed'], 0, 1, 1, 1)

        self.labels['resume'] = KlippyGtk.ButtonImage("resume",_("Resume"),"color1")
        self.labels['resume'].connect("clicked",self.resume)
        self.labels['pause'] = KlippyGtk.ButtonImage("pause",_("Pause"),"color1" )
        self.labels['pause'].connect("clicked",self.pause)

        if self._printer.get_stat('pause_resume','is_paused') == True:
            self.is_paused = True
            grid.attach(self.labels['resume'], 0, 2, 1, 1)
        else:
            grid.attach(self.labels['pause'], 0, 2, 1, 1)

        self.labels['cancel'] = KlippyGtk.ButtonImage("stop",_("Cancel"),"color2")
        self.labels['cancel'].connect("clicked", self.cancel)
        grid.attach(self.labels['cancel'], 1, 2, 1, 1)
        self.labels['estop'] = KlippyGtk.ButtonImage("decrease",_("Emergency Stop"),"color4")
        self.labels['estop'].connect("clicked", self.emergency_stop)
        grid.attach(self.labels['estop'], 2, 2, 1, 1)
        self.labels['control'] = KlippyGtk.ButtonImage("control",_("Control"),"color3")
        self.labels['control'].connect("clicked", self._screen._go_to_submenu, "")
        grid.attach(self.labels['control'], 3, 2, 1, 1)

        self.panel = grid

        self._screen.add_subscription(panel_name)

    def resume(self, widget):
        self.disable_button("pause","cancel")
        self._screen._ws.klippy.print_resume(self._response_callback, "enable_button", "pause", "cancel")
        self._screen.show_all()

    def pause(self, widget):
        self.disable_button("resume","cancel")
        self._screen._ws.klippy.print_pause(self._response_callback, "enable_button", "resume", "cancel")
        self._screen.show_all()

    def cancel(self, widget):
        _ = self.lang.gettext

        dialog = KlippyGtk.ConfirmDialog(
            self._screen,
            _("Are you sure you wish to cancel this print?"),
            [
                {
                    "name": _("Cancel Print"),
                    "response": Gtk.ResponseType.OK
                },
                {
                    "name": _("Go Back"),
                    "response": Gtk.ResponseType.CANCEL
                }
            ],
            self.cancel_confirm
        )
        self.disable_button("pause","cancel")

    def cancel_confirm(self, widget, response_id):
        widget.destroy()

        if response_id == Gtk.ResponseType.CANCEL:
            self.enable_button("pause","cancel")
            return

        self._screen._ws.klippy.print_cancel(self._response_callback, "enable_button", "pause", "cancel")

    def _response_callback(self, response, method, params, func, *args):
        if func == "enable_button":
            self.enable_button(*args)

    def enable_button(self, *args):
        for arg in args:
            self.labels[arg].set_sensitive(True)

    def disable_button(self, *args):
        for arg in args:
            self.labels[arg].set_sensitive(False)


    def process_update(self, data):
        self.update_temp("heater_bed",
            self._printer.get_dev_stat("heater_bed","temperature"),
            self._printer.get_dev_stat("heater_bed","target")
        )
        for x in self._printer.get_tools():
            self.update_temp(x,
                self._printer.get_dev_stat(x,"temperature"),
                self._printer.get_dev_stat(x,"target")
            )

        vsd = self._printer.get_stat("print_stats")
        if "filename" in vsd and self.filename != vsd['filename']:
            if vsd['filename'] != "":
                self.filename = KlippyGtk.formatFileName(vsd['filename'])
                self.update_image_text("file", self.filename)
            else:
                file = "Unknown"
                self.update_image_text("file", "Unknown")


        progress = 0 if self._printer.get_stat('virtual_sdcard','progress') == 0 else (vsd['print_duration'] /
            self._printer.get_stat('virtual_sdcard','progress') - vsd['print_duration'])

        self.update_text("time", str(KlippyGtk.formatTimeString(vsd['print_duration'])))
        self.update_text("time_left", str(KlippyGtk.formatTimeString(
            progress
        )))

        self.update_progress(self._printer.get_stat('virtual_sdcard','progress'))

        if "pause_resume" in data:
            if self.is_paused == True and data['pause_resume']['is_paused'] == False:
                self.is_paused = False
                self.panel.attach(self.labels['pause'], 0, 2, 1, 1)
                self.panel.remove(self.labels['resume'])
                self.panel.show_all()
            if self.is_paused == False and data['pause_resume']['is_paused'] == True:
                self.is_paused = True
                self.panel.attach(self.labels['resume'], 0, 2, 1, 1)
                self.panel.remove(self.labels['pause'])
                self.panel.show_all()



    def update_image_text(self, label, text):
        if label in self.labels and 'l' in self.labels[label]:
            self.labels[label]['l'].set_text(text)

    def update_text(self, label, text):
        if label in self.labels:
            self.labels[label].set_text(text)

    def update_progress (self, progress):
        self.labels['progress'].set_fraction(progress)
        self.labels['progress_text'].set_text("%s%%" % (str(int(progress*100))))

    def update_temp(self, dev, temp, target):
        if dev in self.labels:
            self.labels[dev].set_label(KlippyGtk.formatTemperatureString(temp, target))
