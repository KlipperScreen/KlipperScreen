import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk

class IdleStatusPanel:
    _screen = None
    labels = {}

    def __init__(self, screen):
        self._screen = screen
        print "init"


    # def initialize(self):
    #     box1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    #     image = Gtk.Image()
    #     #TODO: update file reference
    #     image.set_from_file("/opt/printer/OctoScreen/styles/z-bolt/images/bed.svg")
    #     label = Gtk.Label()
    #     label.set_text("0C / 0C")
    #     self.bed_temp_label = label
    #     box1.add(image)
    #     box1.add(self.bed_temp_label)
    #
    #     return box1
    def initialize(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)

        for i in range(self._screen.number_tools):
            self.labels["tool" + str(i)] = KlippyGtk.ButtonImage("extruder-"+str(i+1), "0C / 0C")
            grid.attach(self.labels["tool" + str(i)], 0, 0, 1, 1)

        self.labels['bed'] = KlippyGtk.ButtonImage("bed", "0C / 0C")
        grid.attach(self.labels['bed'], 0, 1, 1, 1)
        #box.add(KlippyGtk.ButtonImage("bed", "0C / 0C"))

        box.add(grid)
        return box

    def update_temp(self, dev, temp, target):
        if self.labels.has_key(dev):
            self.labels[dev].set_label(KlippyGtk.formatTemperatureString(temp, target))
