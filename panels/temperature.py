import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from KlippyGcodes import KlippyGcodes
from panels.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.TemperaturePanel")

class TemperaturePanel(ScreenPanel):
    active_heater = "extruder"
    tempdeltas = ["1","5","10","25"]
    tempdelta = "10"

    def initialize(self, panel_name):
        _ = self.lang.gettext

        grid = KlippyGtk.HomogeneousGrid()

        eq_grid = KlippyGtk.HomogeneousGrid()
        i = 0
        for x in self._printer.get_tools():
            if i > 3:
                break
            elif i == 0:
                primary_tool = x
            self.labels[x] = KlippyGtk.ToggleButtonImage("extruder-"+str(i+1), KlippyGtk.formatTemperatureString(0, 0))
            self.labels[x].connect('clicked', self.select_heater, x)
            if i == 0:
                self.labels[x].set_active(True)
            eq_grid.attach(self.labels[x], i%2, i/2, 1, 1)
            i += 1

        print ("Primary tool: " + primary_tool)
        self.labels[primary_tool].get_style_context().add_class('button_active')

        self.labels["heater_bed"] = KlippyGtk.ToggleButtonImage("bed", KlippyGtk.formatTemperatureString(0, 0))
        self.labels["heater_bed"].connect('clicked', self.select_heater, "heater_bed")
        width = 2 if i > 1 else 1
        eq_grid.attach(self.labels["heater_bed"], 0, i/2+1, width, 1)

        self.labels["control_grid"] = KlippyGtk.HomogeneousGrid()

        self.labels["increase"] = KlippyGtk.ButtonImage("increase", _("Increase"), "color1")
        self.labels["increase"].connect("clicked",self.change_target_temp, "+")
        self.labels["decrease"] = KlippyGtk.ButtonImage("decrease", _("Decrease"), "color3")
        self.labels["decrease"].connect("clicked",self.change_target_temp, "-")
        self.labels["npad"] = KlippyGtk.ButtonImage("settings", _("Number Pad"), "color2")
        self.labels["npad"].connect("clicked", self.show_numpad)

        tempgrid = Gtk.Grid()
        j = 0;
        for i in self.tempdeltas:
            self.labels['deg'+ i] = KlippyGtk.ToggleButton(i)
            self.labels['deg'+ i].connect("clicked", self.change_temp_delta, i)
            ctx = self.labels['deg'+ i].get_style_context()
            if j == 0:
                ctx.add_class("tempbutton_top")
            elif j == len(self.tempdeltas)-1:
                ctx.add_class("tempbutton_bottom")
            else:
                ctx.add_class("tempbutton")
            if i == "10":
                ctx.add_class("distbutton_active")
            tempgrid.attach(self.labels['deg'+ i], 0, j, 1, 1)
            j += 1

        self.labels["deg" + self.tempdelta].set_active(True)

        self.labels["control_grid"].attach(tempgrid, 2, 0, 1, 2)
        self.labels["control_grid"].attach(self.labels["increase"], 3, 0, 1, 1)
        self.labels["control_grid"].attach(self.labels["decrease"], 3, 1, 1, 1)
        self.labels["control_grid"].attach(self.labels["npad"], 2, 2, 1, 1)

        b = KlippyGtk.ButtonImage('back', _('Back'))
        b.connect("clicked", self._screen._menu_go_back)
        self.labels["control_grid"].attach(b, 3, 2, 1, 1)


        grid.attach(eq_grid, 0, 0, 1, 1)
        grid.attach(self.labels["control_grid"], 1, 0, 1, 1)

        self.panel = grid

        self._screen.add_subscription(panel_name)

        self.update_temp("heater_bed",35,40)

    def change_temp_delta(self, widget, tempdelta):
        if self.tempdelta == tempdelta:
            return
        logging.info("### tempdelta " + str(tempdelta))

        ctx = self.labels["deg" + str(self.tempdelta)].get_style_context()
        ctx.remove_class("distbutton_active")

        self.tempdelta = tempdelta
        ctx = self.labels["deg" + self.tempdelta].get_style_context()
        ctx.add_class("distbutton_active")
        for i in self.tempdeltas:
            if i == self.tempdeltas:
                continue
            self.labels["deg" + str(i)].set_active(False)

    def show_numpad(self, widget):
        _ = self.lang.gettext

        numpad = KlippyGtk.HomogeneousGrid()

        keys = [
            ['1','numpad_tleft'],
            ['2','numpad_top'],
            ['3','numpad_tright'],
            ['4','numpad_left'],
            ['5','numpad_button'],
            ['6','numpad_right'],
            ['7','numpad_left'],
            ['8','numpad_button'],
            ['9','numpad_right'],
            ['B','numpad_bleft'],
            ['0','numpad_bottom'],
            ['E','numpad_bright']
        ]
        for i in range(len(keys)):
            id = 'button_' + str(keys[i][0])
            if keys[i][0] == "B":
                self.labels[id] = KlippyGtk.ButtonImage("backspace")
            elif keys[i][0] == "E":
                self.labels[id] = KlippyGtk.ButtonImage("complete", None, None, 40, 40)
            else:
                self.labels[id] = Gtk.Button(keys[i][0])
            self.labels[id].connect('clicked', self.update_entry, keys[i][0])
            ctx=self.labels[id].get_style_context()
            ctx.add_class(keys[i][1])
            numpad.attach(self.labels[id], i%3, i/3, 1, 1)

        self.labels["keypad"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.labels['entry'] = Gtk.Entry()
        self.labels['entry'].props.xalign = 0.5
        ctx = self.labels['entry'].get_style_context()
        ctx.add_class('temperature_entry')

        b = KlippyGtk.ButtonImage('back', _('Close'))
        b.connect("clicked", self.hide_numpad)

        #numpad.attach(b, 0, 5, 3, 1)
        #numpad.attach(self.labels['entry'], 0, 0, 3, 1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(self.labels['entry'])
        box.add(numpad)
        box.add(b)

        self.labels["keypad"] = numpad

        self.panel.remove_column(1)
        #self.panel.attach(self.labels["keypad"], 1, 0, 1, 1)
        self.panel.attach(box, 1, 0, 1, 1)
        self.panel.show_all()

    def hide_numpad(self, widget):
        self.panel.remove_column(1)
        self.panel.attach(self.labels["control_grid"], 1, 0, 1, 1)
        self.panel.show_all()


    def select_heater (self, widget, heater):
        if self.active_heater == heater:
            return


        self.labels[self.active_heater].get_style_context().remove_class('button_active')
        self.active_heater = heater
        self.labels[heater].get_style_context().add_class("button_active")

        if "entry" in self.labels:
            self.labels['entry'].set_text("")
        logging.info("### Active heater " + self.active_heater)

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
        return

    def change_target_temp(self, widget, dir):
        target = self._printer.get_dev_stat(self.active_heater, "target")
        if dir == "+":
            target += int(self.tempdelta)
            if target > KlippyGcodes.MAX_EXT_TEMP:
                target = KlippyGcodes.MAX_EXT_TEMP
        else:
            target -= int(self.tempdelta)
            if target < 0:
                target = 0

        self._printer.set_dev_stat(self.active_heater, "target", target)

        if self.active_heater == "heater_bed":
            self._screen._ws.klippy.gcode_script( KlippyGcodes.set_bed_temp(
                target
            ))
        else:
            self._screen._ws.klippy.gcode_script( KlippyGcodes.set_ext_temp(
                target,
                self._printer.get_tool_number(self.active_heater)
            ))

    def update_entry(self, widget, digit):
        text = self.labels['entry'].get_text()
        if digit == 'B':
            if len(text) < 1:
                return
            self.labels['entry'].set_text(text[0:-1])
        elif digit == 'E':
            if self.active_heater == "heater_bed":
                temp = int(text)
                temp = 0 if temp < 0 or temp > KlippyGcodes.MAX_BED_TEMP else temp
                self._screen._ws.klippy.gcode_script(KlippyGcodes.set_bed_temp(temp))
            else:
                temp = int(text)
                temp = 0 if temp < 0 or temp > KlippyGcodes.MAX_EXT_TEMP else temp
                self._screen._ws.klippy.gcode_script( KlippyGcodes.set_ext_temp(
                    temp,
                    self._printer.get_tool_number(self.active_heater)
                ))
            self._printer.set_dev_stat(self.active_heater, "target", temp)
            self.labels['entry'].set_text("")
        else:
            if len(text) >= 3:
                return
            self.labels['entry'].set_text(text + digit)
