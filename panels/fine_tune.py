import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from KlippyGcodes import KlippyGcodes
from panels.screen_panel import ScreenPanel

class FineTune(ScreenPanel):
    user_selecting = False

    delta = 1
    deltas = ['1','5','10','25']

    def initialize(self, panel_name):
        # Create gtk items here
        grid = KlippyGtk.HomogeneousGrid()


        self.labels['z+'] = KlippyGtk.ButtonImage("move-z+", "Z+ .05mm", "color1")
        self.labels['zoffset'] = Gtk.Label("Z Offset: 0.00mm")
        self.labels['z-'] = KlippyGtk.ButtonImage("move-z-", "Z- .05mm", "color1")

        grid.attach(self.labels['z+'], 0, 0, 1, 1)
        grid.attach(self.labels['z-'], 0, 2, 1, 1)

        self.labels['fan+'] = KlippyGtk.ButtonImage("fan-on", "Increase Fan", "color2")
        self.labels['fanspeed'] = Gtk.Label("Fan: 100%")
        self.labels['fan-'] = KlippyGtk.ButtonImage("fan-off", "Decrease Fan", "color2")
        grid.attach(self.labels['fan+'], 1, 0, 1, 1)
        grid.attach(self.labels['fanspeed'], 1, 1, 1, 1)
        grid.attach(self.labels['fan-'], 1, 2, 1, 1)

        self.labels['speed+'] = KlippyGtk.ButtonImage("speed-step", "Increase Speed", "color3")
        self.labels['speedfactor'] = Gtk.Label("Speed: 100%")
        self.labels['speed-'] = KlippyGtk.ButtonImage("speed-step", "Decrease Speed", "color3")
        grid.attach(self.labels['speed+'], 2, 0, 1, 1)
        grid.attach(self.labels['speedfactor'], 2, 1, 1, 1)
        grid.attach(self.labels['speed-'], 2, 2, 1, 1)

        self.labels['extrude+'] = KlippyGtk.ButtonImage("extrude", "Increase Extrusion", "color4")
        self.labels['extrudefactor'] = Gtk.Label("Extrusion: 100%")
        self.labels['extrude-'] = KlippyGtk.ButtonImage("retract", "Decrease Extrusion", "color4")
        grid.attach(self.labels['extrude+'], 3, 0, 1, 1)
        grid.attach(self.labels['extrudefactor'], 3, 1, 1, 1)
        grid.attach(self.labels['extrude-'], 3, 2, 1, 1)



        deltgrid = Gtk.Grid()
        j = 0;
        for i in self.deltas:
            self.labels[i] = KlippyGtk.ToggleButton(i)
            self.labels[i].connect("clicked", self.change_delta, i)
            ctx = self.labels[i].get_style_context()
            if j == 0:
                ctx.add_class("distbutton_top")
            elif j == len(self.deltas)-1:
                ctx.add_class("distbutton_bottom")
            else:
                ctx.add_class("distbutton")
            if i == "1":
                ctx.add_class("distbutton_active")
            deltgrid.attach(self.labels[i], j, 0, 1, 1)
            j += 1

        self.labels["1"].set_active(True)

        grid.attach(deltgrid, 1, 3, 2, 1)




        b = KlippyGtk.ButtonImage('back', 'Back')
        b.connect("clicked", self._screen._menu_go_back)
        grid.attach(b,3,3,1,1)

        self.panel = grid
        #self._screen.add_subscription(panel_name)

    def process_update(self, data):
        return
        if "fan" in data and "speed" in data["fan"] and self.user_selecting == False:
            self.labels["scale"].disconnect_by_func(self.select_fan_speed)
            self.labels["scale"].set_value(float(int(float(data["fan"]["speed"]) * 100)))
            self.labels["scale"].connect("value-changed", self.select_fan_speed)

    def change_delta(self, widget, delta):
        if self.delta == delta:
            return
        logging.info("### Delta " + str(delta))

        ctx = self.labels[str(self.delta)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.delta = delta
        ctx = self.labels[self.delta].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.deltas:
            if i == self.delta:
                continue
            self.labels[str(i)].set_active(False)


    def select_fan_speed(self, widget):
        if self.user_selecting == True:
            return

        self.user_selecting = True
        self.panel.attach(self.labels["apply"], 3, 0, 1, 1)
        self.panel.attach(self.labels["cancel"], 0, 0, 1, 1)
        self._screen.show_all()

    def cancel_select_fan_speed(self, widget):
        self.user_selecting = False
        self.panel.remove(self.labels["apply"])
        self.panel.remove(self.labels["cancel"])


    def set_fan_speed(self, widget):
        self._screen._ws.send_method("post_printer_gcode_script", {"script": KlippyGcodes.set_fan_speed(self.labels['scale'].get_value())})
        self.cancel_select_fan_speed(widget)

    def set_fan_on(self, widget, fanon):
        speed = 100 if fanon == True else 0
        self.labels["scale"].set_value(speed)
        self._screen._ws.send_method("post_printer_gcode_script", {"script": KlippyGcodes.set_fan_speed(speed)})
