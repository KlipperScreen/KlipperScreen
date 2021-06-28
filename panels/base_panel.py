import datetime
import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from jinja2 import Environment, Template

from ks_includes.KlippyGtk import KlippyGtk
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

class BasePanel(ScreenPanel):
    def __init__(self, screen, title, back=True, action_bar=True, printer_name=True):
        super().__init__(screen, title, back, action_bar, printer_name)
        self.current_panel = None
        self.time_min = -1
        self.time_format = self._config.get_main_config_option("24htime")

        self.buttons_showing = {
            'back': False if back else True
        }

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)

        action_bar_width = self._gtk.get_action_bar_width() if action_bar == True else 0

        self.control_grid = self._gtk.HomogeneousGrid()
        self.control_grid.set_size_request(action_bar_width - 2, self._screen.height)
        self.control_grid.get_style_context().add_class('action_bar')

        button_scale = self._gtk.get_header_image_scale()
        logging.debug("Button scale: %s" % button_scale)

        self.control['back'] = self._gtk.ButtonImage('back', None, None, button_scale[0], button_scale[1])
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = self._gtk.ButtonImage('main', None, None, button_scale[0], button_scale[1])
        self.control['home'].connect("clicked", self.menu_return, True)

        #if back == True:
        #    self.control_grid.attach(self.control['back'], 0, 0, 1, 1)
        #    self.control_grid.attach(self.control['home'], 0, 1, 1, 1)
        #else:
        for i in range(2):
            self.control['space%s' % i] = Gtk.Label("")
            self.control_grid.attach(self.control['space%s' % i], 0, i, 1, 1)

        if len(self._config.get_printers()) > 1:
            self.control['printer_select'] = self._gtk.ButtonImage(
                'shuffle', None, None, button_scale[0], button_scale[1])
            self.control['printer_select'].connect("clicked", self._screen.show_printer_select)
        else:
            self.control['printer_select'] = Gtk.Label("")
        self.control_grid.attach(self.control['printer_select'], 0, 2, 1, 1)

        self.control['estop'] = self._gtk.ButtonImage('emergency', None, None, button_scale[0], button_scale[1])
        self.control['estop'].connect("clicked", self.emergency_stop)
        self.control_grid.attach(self.control['estop'], 0, 3, 1, 1)

        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except:
            logging.debug("Error parsing jinja for title: %s" % title)

        self.titlelbl = Gtk.Label()
        self.titlelbl.set_size_request(self._screen.width - action_bar_width, self.title_spacing)
        self.titlelbl.set_hexpand(True)
        self.titlelbl.set_halign(Gtk.Align.CENTER)
        self.titlelbl.set_valign(Gtk.Align.CENTER)
        self.set_title(title)

        self.content = Gtk.VBox(spacing=0)
        self.content.set_size_request(self._screen.width - action_bar_width, self._screen.height - self.title_spacing)

        if action_bar == True:
            self.layout.put(self.control_grid, 0, 0)

        self.control['time_box'] = Gtk.Box()
        self.control['time_box'].set_halign(Gtk.Align.END)
        self.control['time_box'].set_size_request(0, self.title_spacing)
        self.control['time'] = Gtk.Label("00:00 AM")
        self.control['time'].set_size_request(0, self.title_spacing)
        self.control['time'].set_halign(Gtk.Align.END)
        self.control['time'].set_valign(Gtk.Align.CENTER)
        self.control['time_box'].pack_end(self.control['time'], True, 0, 0)

        self.control['temp_box'] = Gtk.Box()
        self.control['temp_box'].set_vexpand(True)
        self.control['temp_box'].set_size_request(0, self.title_spacing)

        self.layout.put(self.control['temp_box'], action_bar_width, 0)
        self.layout.put(self.titlelbl, action_bar_width, 0)
        self.layout.put(self.control['time_box'], action_bar_width, 0)
        self.layout.put(self.content, action_bar_width, self.title_spacing)

    def initialize(self, panel_name):
        # Create gtk items here
        return

    def show_heaters(self):
        for child in self.control['temp_box'].get_children():
            self.control['temp_box'].remove(child)

        i = 0
        for extruder in self._printer.get_tools():
            self.labels[extruder + '_box'] = Gtk.Box(spacing=0)
            self.labels[extruder] = Gtk.Label(label="")
            #self.labels[extruder].get_style_context().add_class("printing-info")
            if i <= 4:
                ext_img = self._gtk.Image("extruder-%s.svg" % i, None, .4, .4)
                self.labels[extruder + '_box'].pack_start(ext_img, True, 3, 3)
            self.labels[extruder + '_box'].pack_start(self.labels[extruder], True, 3, 3)
            i += 1
        self.current_extruder = self._printer.get_stat("toolhead","extruder")
        self.control['temp_box'].pack_start(self.labels["%s_box" % self.current_extruder], True, 5, 5)

        if self._printer.has_heated_bed():
            heater_bed = self._gtk.Image("bed.svg", None, .4, .4)
            self.labels['heater_bed'] = Gtk.Label(label="20 C")
            #self.labels['heater_bed'].get_style_context().add_class("printing-info")
            heater_bed_box = Gtk.Box(spacing=0)
            heater_bed_box.pack_start(heater_bed, True, 5, 5)
            heater_bed_box.pack_start(self.labels['heater_bed'], True, 3, 3)
            self.control['temp_box'].pack_end(heater_bed_box, True, 3, 3)


    def activate(self):
        size = self.control['time_box'].get_allocation().width
        self.layout.remove(self.control['time_box'])
        self.control['time_box'].set_size_request(size, self.title_spacing)
        self.layout.put(self.control['time_box'], self._screen.width - size - 5, 0)

        GLib.timeout_add_seconds(1, self.update_time)
        self.update_time()

    def add_content(self, panel):
        self.current_panel = panel
        self.set_title(panel.get_title())
        self.content.add(panel.get_content())

    def back(self, widget):
        if self.current_panel == None:
            return

        if self._screen.is_keyboard_showing():
            self._screen.remove_keyboard()

        if hasattr(self.current_panel, "back"):
            if not self.current_panel.back():
                self._screen._menu_go_back()
        else:
            self._screen._menu_go_back()

    def get(self):
        return self.layout

    def process_update(self, action, data):
        if action != "notify_status_update" or self._printer == None:
            return

        if self._printer.has_heated_bed():
            self.labels["heater_bed"].set_label("%02d°" % self._printer.get_dev_stat("heater_bed","temperature"))
        for x in self._printer.get_tools():
            self.labels[x].set_label("%02d°" % self._printer.get_dev_stat(x,"temperature"))

        if "toolhead" in data and "extruder" in data["toolhead"]:
            if data["toolhead"]["extruder"] != self.current_extruder:
                self.control['temp_box'].remove(self.labels["%s_box" % self.current_extruder])
                self.current_extruder = data["toolhead"]["extruder"]
                self.control['temp_box'].pack_start(self.labels["%s_box" % self.current_extruder], True, 3, 3)
                self.control['temp_box'].show_all()


    def remove(self, widget):
        self.content.remove(widget)

    def show_back(self, show=True):
        if show == True and self.buttons_showing['back'] == False:
            self.control_grid.remove(self.control_grid.get_child_at(0,0))
            self.control_grid.attach(self.control['back'], 0, 0, 1, 1)
            self.control_grid.remove(self.control_grid.get_child_at(0,1))
            self.control_grid.attach(self.control['home'], 0, 1, 1, 1)
            self.buttons_showing['back'] = True
        elif show == False and self.buttons_showing['back'] == True:
            for i in range(0,2):
                self.control_grid.remove(self.control_grid.get_child_at(0,i))
                self.control_grid.attach(self.control['space%s' % i], 0, i, 1, 1)
            self.buttons_showing['back'] = False
        self.control_grid.show()

    def set_title(self, title):
        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except:
            logging.debug("Error parsing jinja for title: %s" % title)

        self.titlelbl.set_label("%s | %s" % (self._screen.connected_printer, title))

    def show_back_buttons(self):
        self.control_grid.attach(self.control['back'], 0, 0, 1, 1)
        self.control_grid.attach(self.control['home'], 0, 1, 1, 1)

    def update_time(self):
        now = datetime.datetime.now()
        confopt = self._config.get_main_config_option("24htime")
        if now.minute != self.time_min or self.time_format != confopt:
            if confopt == "True":
                self.control['time'].set_text(now.strftime("%H:%M"))
            else:
                self.control['time'].set_text(now.strftime("%I:%M %p"))
        return True
