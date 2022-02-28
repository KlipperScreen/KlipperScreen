# -*- coding: utf-8 -*-
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
        self.title_spacing = self._gtk.font_size * 2
        self.time_update = None
        self.buttons_showing = {
            'back': False if back else True,
            'macros_shortcut': False,
            'printer_select': False
        }

        self.layout = Gtk.Layout()
        self.layout.set_size(self._screen.width, self._screen.height)

        action_bar_width = self._gtk.get_action_bar_width() if action_bar is True else 0
        action_bar_height = self._gtk.get_action_bar_height() if action_bar is True else 0

        self.control_grid = self._gtk.HomogeneousGrid()
        self.control_grid.set_size_request(action_bar_width, action_bar_height)
        self.control_grid.get_style_context().add_class('action_bar')

        button_scale = self._gtk.get_header_image_scale()
        logging.debug("Button scale: %s" % button_scale)

        self.control['back'] = self._gtk.ButtonImage('back', None, None, button_scale[0], button_scale[1])
        self.control['back'].connect("clicked", self.back)
        self.control['home'] = self._gtk.ButtonImage('main', None, None, button_scale[0], button_scale[1])
        self.control['home'].connect("clicked", self.menu_return, True)

        if len(self._config.get_printers()) > 1:
            self.control['printer_select'] = self._gtk.ButtonImage(
                'shuffle', None, None, button_scale[0], button_scale[1])
            self.control['printer_select'].connect("clicked", self._screen.show_printer_select)

        self.control['macro_shortcut'] = self._gtk.ButtonImage(
            'custom-script', None, None, button_scale[0], button_scale[1])
        self.control['macro_shortcut'].connect("clicked", self.menu_item_clicked, "gcode_macros", {
            "name": "Macros",
            "panel": "gcode_macros"
        })

        self.control['estop'] = self._gtk.ButtonImage('emergency', None, None, button_scale[0], button_scale[1])
        self.control['estop'].connect("clicked", self.emergency_stop)

        self.locations = {
            'macro_shortcut': 2,
            'printer_select': 2
        }
        button_range = 3
        if len(self._config.get_printers()) > 1:
            self.locations['macro_shortcut'] = 3
            if self._config.get_main_config_option('side_macro_shortcut') == "True":
                button_range = 4

        for i in range(button_range):
            self.control['space%s' % i] = Gtk.Label("")
            if self._screen.vertical_mode:
                self.control_grid.attach(self.control['space%s' % i], i, 0, 1, 1)
            else:
                self.control_grid.attach(self.control['space%s' % i], 0, i, 1, 1)
        if self._screen.vertical_mode:
            self.control_grid.attach(self.control['estop'], 4, 0, 1, 1)
        else:
            self.control_grid.attach(self.control['estop'], 0, 4, 1, 1)

        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except Exception:
            logging.debug("Error parsing jinja for title: %s" % title)

        self.titlelbl = Gtk.Label()
        self.titlelbl.set_hexpand(True)
        self.titlelbl.set_halign(Gtk.Align.CENTER)
        self.set_title(title)

        self.hmargin = 5
        self.content = Gtk.VBox(spacing=0)
        if self._screen.vertical_mode:
            self.content.set_size_request(self._screen.width - self.hmargin * 2,
                                          self._screen.height - self.title_spacing - action_bar_height)
        else:
            self.content.set_size_request(self._screen.width - action_bar_width - self.hmargin,
                                          self._screen.height - self.title_spacing)

        if action_bar is True:
            if self._screen.vertical_mode:
                self.layout.put(self.control_grid, 0, self._screen.height - action_bar_height)
            else:
                self.layout.put(self.control_grid, 0, 0)

        self.control['time_box'] = Gtk.Box()
        self.control['time_box'].set_halign(Gtk.Align.END)
        self.control['time'] = Gtk.Label("00:00 AM")
        self.control['time_box'].pack_end(self.control['time'], True, True, 0)

        self.control['temp_box'] = Gtk.Box()

        self.titlebar = Gtk.Grid()
        self.titlelbl.set_vexpand(True)
        self.titlebar.set_valign(Gtk.Align.CENTER)
        if self._screen.vertical_mode:
            self.titlebar.set_size_request(self._screen.width - self.hmargin, self.title_spacing)
        else:
            self.titlebar.set_size_request(self._screen.width - action_bar_width - self.hmargin, self.title_spacing)
        self.titlebar.attach(self.control['temp_box'], 0, 0, 1, 1)
        self.titlebar.attach(self.titlelbl, 1, 0, 1, 1)
        self.titlebar.attach(self.control['time_box'], 2, 0, 1, 1)

        if self._screen.vertical_mode:
            self.layout.put(self.titlebar, self.hmargin, 0)
            self.layout.put(self.content, self.hmargin, self.title_spacing)
        else:
            self.layout.put(self.titlebar, action_bar_width, 0)
            self.layout.put(self.content, action_bar_width + self.hmargin, self.title_spacing)


    def initialize(self, panel_name):
        self.update_time()
        return

    def show_heaters(self, show=True):
        for child in self.control['temp_box'].get_children():
            self.control['temp_box'].remove(child)

        if show is False:
            return

        h = 0
        if self._printer.get_tools():
            for i, extruder in enumerate(self._printer.get_tools()):
                self.labels[extruder + '_box'] = Gtk.Box(spacing=0)
                self.labels[extruder] = Gtk.Label(label="200º")
                if i <= 4:
                    ext_img = self._gtk.Image("extruder-%s.svg" % i, None, .4, .4)
                    self.labels[extruder + '_box'].pack_start(ext_img, True, True, 3)
                self.labels[extruder + '_box'].pack_start(self.labels[extruder], True, True, 0)
            self.current_extruder = self._printer.get_stat("toolhead", "extruder")
            self.control['temp_box'].pack_start(self.labels["%s_box" % self.current_extruder], True, True, 3)
            h += 1

        if self._printer.has_heated_bed():
            heater_bed = self._gtk.Image("bed.svg", None, .4, .4)
            self.labels['heater_bed'] = Gtk.Label(label="100º")
            heater_bed_box = Gtk.Box(spacing=0)
            heater_bed_box.pack_start(heater_bed, True, True, 5)
            heater_bed_box.pack_start(self.labels['heater_bed'], True, True, 0)
            self.control['temp_box'].pack_end(heater_bed_box, True, True, 3)
            h += 1

        heater_gen_img = self._gtk.Image("heat-up.svg", None, .4, .4)
        for heater in self._printer.get_heaters():
            if h > 3 and self._screen.width <= 480:
                break
            elif h > 4 and self._screen.width <= 800:
                break
            elif h > 5:
                break
            elif heater.startswith("heater_generic"):
                self.labels[heater + '_box'] = Gtk.Box(spacing=0)
                self.labels[heater] = Gtk.Label(label="100º")
                self.labels[heater + '_box'].pack_start(heater_gen_img, True, True, 3)
                self.labels[heater + '_box'].pack_start(self.labels[heater], True, True, 0)
                self.control['temp_box'].pack_start(self.labels["%s_box" % heater], True, True, 3)
                h += 1

    def activate(self):
        if self.time_update is None:
            self.time_update = GLib.timeout_add_seconds(1, self.update_time)

    def add_content(self, panel):
        self.current_panel = panel
        self.set_title(panel.get_title())
        self.content.add(panel.get_content())

    def back(self, widget):
        if self.current_panel is None:
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
        if action != "notify_status_update" or self._printer is None:
            return

        for x in self._printer.get_tools():
            self.labels[x].set_label("%d°" % round(self._printer.get_dev_stat(x, "temperature")))
        for heater in self._printer.get_heaters():
            if heater == "heater_bed" or heater.startswith("heater_generic"):
                self.labels[heater].set_label("%d°" % round(self._printer.get_dev_stat(heater, "temperature")))

        if "toolhead" in data and "extruder" in data["toolhead"]:
            if data["toolhead"]["extruder"] != self.current_extruder:
                self.control['temp_box'].remove(self.labels["%s_box" % self.current_extruder])
                self.current_extruder = data["toolhead"]["extruder"]
                self.control['temp_box'].pack_start(self.labels["%s_box" % self.current_extruder], True, True, 3)
                self.control['temp_box'].show_all()


    def remove(self, widget):
        self.content.remove(widget)

    def show_back(self, show=True):
        if show is True and self.buttons_showing['back'] is False:
            self.control_grid.remove(self.control_grid.get_child_at(0, 0))
            self.control_grid.attach(self.control['back'], 0, 0, 1, 1)
            if self._screen.vertical_mode:
                self.control_grid.remove(self.control_grid.get_child_at(1, 0))
                self.control_grid.attach(self.control['home'], 1, 0, 1, 1)
            else:
                self.control_grid.remove(self.control_grid.get_child_at(0, 1))
                self.control_grid.attach(self.control['home'], 0, 1, 1, 1)
            self.buttons_showing['back'] = True
        elif show is False and self.buttons_showing['back'] is True:
            for i in range(0, 2):
                if self._screen.vertical_mode:
                    self.control_grid.remove(self.control_grid.get_child_at(i, 0))
                    self.control_grid.attach(self.control['space%s' % i], i, 0, 1, 1)
                else:
                    self.control_grid.remove(self.control_grid.get_child_at(0, i))
                    self.control_grid.attach(self.control['space%s' % i], 0, i, 1, 1)
            self.buttons_showing['back'] = False
        self.control_grid.show()

    def show_macro_shortcut(self, show=True, mod_row=False):
        if show == "True":
            show = True

        if show is True and self.buttons_showing['macros_shortcut'] is False:
            if len(self._config.get_printers()) > 1 and mod_row is True:
                if self._screen.vertical_mode:
                    self.control_grid.insert_column(self.locations['macro_shortcut'])
                else:
                    self.control_grid.insert_row(self.locations['macro_shortcut'])
            else:
                if self._screen.vertical_mode:
                    self.control_grid.remove(self.control_grid.get_child_at(self.locations['macro_shortcut'], 0))
                else:
                    self.control_grid.remove(self.control_grid.get_child_at(0, self.locations['macro_shortcut']))
            if 'space%s' % self.locations['macro_shortcut'] in self.control:
                self.control_grid.remove(self.control['space%s' % self.locations['macro_shortcut']])
            if self._screen.vertical_mode:
                self.control_grid.attach(self.control['macro_shortcut'], self.locations['macro_shortcut'], 0, 1, 1)
            else:
                self.control_grid.attach(self.control['macro_shortcut'], 0, self.locations['macro_shortcut'], 1, 1)
            self.buttons_showing['macros_shortcut'] = True
        elif show is not True and self.buttons_showing['macros_shortcut'] is True:
            if ('space%s' % self.locations['macro_shortcut']) not in self.control:
                self.control['space%s' % self.locations['macro_shortcut']] = Gtk.Label("")
            if len(self._config.get_printers()) > 1 and mod_row is True:
                if self._screen.vertical_mode:
                    self.control_grid.remove(self.control_grid.get_child_at(self.locations['macro_shortcut'], 0))
                    self.control_grid.remove_column(self.locations['macro_shortcut'])
                else:
                    self.control_grid.remove(self.control_grid.get_child_at(0, self.locations['macro_shortcut']))
                    self.control_grid.remove_row(self.locations['macro_shortcut'])
                self.control_grid.remove(self.control['macro_shortcut'])
            else:
                if self._screen.vertical_mode:
                    self.control_grid.remove(self.control_grid.get_child_at(self.locations['macro_shortcut'], 0))
                else:
                    self.control_grid.remove(self.control_grid.get_child_at(0, self.locations['macro_shortcut']))
            if ('space%s' % self.locations['macro_shortcut']) not in self.control:
                self.control['space%s' % self.locations['macro_shortcut']] = Gtk.Label("")
            if self._screen.vertical_mode:
                self.control_grid.attach(self.control['space%s' % self.locations['macro_shortcut']],
                                         self.locations['macro_shortcut'], 0, 1, 1)
            else:
                self.control_grid.attach(self.control['space%s' % self.locations['macro_shortcut']],
                                         0, self.locations['macro_shortcut'], 1, 1)
            self.buttons_showing['macros_shortcut'] = False
        self._screen.show_all()

    def show_printer_select(self, show=True):
        if len(self._config.get_printers()) <= 1:
            return

        if show and self.buttons_showing['printer_select'] is False:
            logging.info("Turning on printer_select button")
            if self._screen.vertical_mode:
                self.control_grid.remove(self.control_grid.get_child_at(self.locations['printer_select'], 0))
                self.control_grid.attach(self.control['printer_select'], self.locations['printer_select'], 0, 1, 1)
            else:
                self.control_grid.remove(self.control_grid.get_child_at(0, self.locations['printer_select']))
                self.control_grid.attach(self.control['printer_select'], 0, self.locations['printer_select'], 1, 1)
            self.buttons_showing['printer_select'] = True
        elif show is False and self.buttons_showing['printer_select']:
            logging.info("Turning off printer_select button")
            if self._screen.vertical_mode:
                self.control_grid.remove(self.control_grid.get_child_at(self.locations['printer_select'], 0))
                self.control_grid.attach(self.control['space%s' % self.locations['printer_select']],
                                         self.locations['printer_select'], 0, 1, 1)
            else:
                self.control_grid.remove(self.control_grid.get_child_at(0, self.locations['printer_select']))
                self.control_grid.attach(self.control['space%s' % self.locations['printer_select']],
                                         0, self.locations['printer_select'], 1, 1)

            self.buttons_showing['printer_select'] = False
        self._screen.show_all()

    def set_title(self, title):
        try:
            env = Environment(extensions=["jinja2.ext.i18n"])
            env.install_gettext_translations(self.lang)
            j2_temp = env.from_string(title)
            title = j2_temp.render()
        except Exception:
            logging.debug("Error parsing jinja for title: %s" % title)

        self.titlelbl.set_label("%s | %s" % (self._screen.connected_printer, title))

    def show_back_buttons(self):
        self.control_grid.attach(self.control['back'], 0, 0, 1, 1)
        if self._screen.vertical_mode:
            self.control_grid.attach(self.control['home'], 1, 0, 1, 1)
        else:
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
