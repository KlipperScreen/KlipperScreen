import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk

class JobStatusPanel:
    _screen = None
    labels = {}

    def __init__ (self, screen):
        self._screen = screen

    def initialize(self):
        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)

        self.labels['progress'] = KlippyGtk.ProgressBar("printing-progress-bar")
        self.labels['progress'].set_vexpand(True)
        self.labels['progress'].set_valign(Gtk.Align.CENTER)
        self.labels['progress'].set_show_text(True)
        self.labels['progress'].set_margin_top(10)
        self.labels['progress'].set_margin_end(20)

        self.labels['file'] = KlippyGtk.ImageLabel("file","",20,"printing-status-label")
        self.labels['time'] = KlippyGtk.ImageLabel("speed-step","time",20,"printing-status-label")
        self.labels['time_left'] = KlippyGtk.ImageLabel("speed-step","time_left",20,"printing-status-label")
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info.props.valign = Gtk.Align.CENTER
        info.set_hexpand(True)
        info.set_vexpand(True)
        info.add(self.labels['file']['b'])
        info.add(self.labels['time']['b'])
        #info.add(self.labels['time_left']['b'])

        grid.attach(info,2,0,2,1)

        grid.attach(self.labels['progress'], 2, 1, 2, 1)

        self.labels['tool0'] = KlippyGtk.ButtonImage("extruder-1", KlippyGtk.formatTemperatureString(0, 0))
        self.labels['tool0'].set_sensitive(False)
        grid.attach(self.labels['tool0'], 0, 0, 1, 1)
        #self.labels['tool1'] = KlippyGtk.ButtonImage("extruder-2", KlippyGtk.formatTemperatureString(0, 0))
        #self.labels['tool1'].set_sensitive(False)
        #grid.attach(self.labels['tool1'], 1, 0, 1, 1)
        self.labels['bed'] = KlippyGtk.ButtonImage("bed", KlippyGtk.formatTemperatureString(0, 0))
        self.labels['bed'].set_sensitive(False)
        grid.attach(self.labels['bed'], 0, 2, 1, 1)

        self.labels['resume'] = KlippyGtk.ButtonImage("resume","Resume","color1")
        self.labels['resume'].connect("clicked",self.resume)
        #grid.attach(self.labels['play'], 1, 2, 1, 1)
        self.labels['pause'] = KlippyGtk.ButtonImage("pause","Pause","color1" )
        self.labels['pause'].connect("clicked",self.pause)
        grid.attach(self.labels['pause'], 1, 2, 1, 1)
        self.labels['stop'] = KlippyGtk.ButtonImage("stop","Stop","color2")
        grid.attach(self.labels['stop'], 2, 2, 1, 1)
        self.labels['control'] = KlippyGtk.ButtonImage("control","Control","color3")
        grid.attach(self.labels['control'], 3, 2, 1, 1)

        self.grid = grid

        return self.grid
        #m.Grid().Attach(m.createInfoBox(), 3, 0, 2, 1)
    	#m.Grid().Attach(m.createProgressBar(), 3, 1, 2, 1)
    	#m.Grid().Attach(m.createPauseButton(), 2, 2, 1, 1)
    	#m.Grid().Attach(m.createStopButton(), 3, 2, 1, 1)
    	#m.Grid().Attach(m.createMenuButton(), 4, 2, 1, 1)
    	#m.Grid().Attach(m.createCompleteButton(), 2, 2, 3, 1)

    def get(self):
            return self.grid

    def resume(self, widget):
        self.grid.attach(self.labels['pause'], 1, 2, 1, 1)
        self.grid.remove(self.labels['resume'])
        self._screen.show_all()

    def pause(self, widget):
        self.grid.attach(self.labels['resume'], 1, 2, 1, 1)
        self.grid.remove(self.labels['pause'])
        self._screen.show_all()


    def update_image_text(self, label, text):
        if label in self.labels and 'l' in self.labels[label]:
            self.labels[label]['l'].set_text(text)

    def update_progress (self, progress):
        #progress = round(progress,2)
        #whole = (progress%1) * 100

        self.labels['progress'].set_fraction(progress)
        #self.labels['progress'].set_text(str(int(whole)) + "%")

    def update_temp(self, dev, temp, target):
        if self.labels.has_key(dev):
            self.labels[dev].set_label(KlippyGtk.formatTemperatureString(temp, target))
