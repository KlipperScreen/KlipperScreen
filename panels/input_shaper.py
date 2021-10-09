import gi
import re

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return InputShaperPanel(*args)


# X and Y frequencies
XY_FREQ = [
    {'name': 'X Frequency', 'config': 'shaper_freq_x', 'min': 0, 'max': 133},
    {'name': 'Y Frequency', 'config': 'shaper_freq_y', 'min': 0, 'max': 133},
]
SHAPERS = ['zv', 'mzv', 'zvd', 'ei', '2hump_ei', '3hump_ei']

class InputShaperPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.CALIBRATE_TEXT = self.lang.gettext('Auto-calibrate and Save')

        self.has_sensor = False

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        grid.set_vexpand(True)
        grid.set_hexpand(True)
        grid.get_style_context().add_class("input-shaper")
        grid.set_column_spacing(20)

        input_grid = Gtk.Grid()
        input_grid.set_vexpand(True)

        self.freq_xy_adj = {}
        self.freq_xy_combo = {}

        manual_calibration_label = Gtk.Label()
        manual_calibration_label.set_markup('<big><b>Manual Calibration</b></big>')
        input_grid.attach(manual_calibration_label, 0, 0, 1, 1)

        disclaimer = Gtk.Label()
        disclaimer.set_markup('<small>NOTE: Manual calibration will only be used in runtime. Edit your printer.cfg to persist manual calibration changes.</small>')
        disclaimer.set_line_wrap(True)
        disclaimer.set_hexpand(True)
        disclaimer.set_vexpand(False)
        disclaimer.set_halign(Gtk.Align.START)
        input_grid.attach(disclaimer, 0, 1, 1, 1)

        for i, dim_freq in enumerate(XY_FREQ):
            frame = Gtk.Frame()
            frame.set_property("shadow-type", Gtk.ShadowType.NONE)
            frame.get_style_context().add_class("frame-item")

            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

            name = Gtk.Label()
            name.set_markup("<b>{}</b> (Hz)".format(dim_freq['name']))
            name.set_hexpand(True)
            name.set_vexpand(True)
            name.set_halign(Gtk.Align.START)
            name.set_valign(Gtk.Align.CENTER)
            name.set_line_wrap(True)

            self.freq_xy_adj[dim_freq['config']] = Gtk.Adjustment(0, dim_freq['min'], dim_freq['max'], 0.1)
            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.freq_xy_adj[dim_freq['config']])
            scale.set_digits(1)
            scale.set_hexpand(True)
            scale.set_has_origin(True)
            scale.get_style_context().add_class("option_slider")
            scale.connect("button-release-event", self.set_opt_value, dim_freq['config'])

            labels.add(name)
            labels.add(scale)

            shaper_grid = Gtk.Grid()
            shaper_grid.set_vexpand(True)
            name = Gtk.Label()
            name.set_markup("<b>{}</b>".format(dim_freq['name'].replace('Frequency', 'Shaper Type')))
            name.set_hexpand(True)
            name.set_vexpand(True)
            name.set_halign(Gtk.Align.START)
            name.set_valign(Gtk.Align.CENTER)
            name.set_line_wrap(True)
            name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            shaper_grid.attach(name, 0, 0, 1, 1)
            shaper_slug = dim_freq['config'].replace('_freq_', '_type_')
            self.freq_xy_combo[shaper_slug] = Gtk.ComboBoxText()
            for shaper in SHAPERS:
                self.freq_xy_combo[shaper_slug].append(shaper, shaper)
                self.freq_xy_combo[shaper_slug].set_active(0)
            shaper_grid.attach(self.freq_xy_combo[shaper_slug], 1, 0, 1, 1)
            labels.add(shaper_grid)

            dev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            dev.set_hexpand(True)
            dev.set_vexpand(False)
            dev.add(labels)
            frame.add(dev)
            input_grid.attach(frame, 0, i + 2, 1, 1)

        grid.attach(input_grid, 0, 0, 1, 1)

        auto_grid = Gtk.Grid()
        auto_grid.set_vexpand(True)

        auto_calibration_label = Gtk.Label()
        auto_calibration_label.set_markup('<big><b>Auto Calibration</b></big>')
        auto_grid.attach(auto_calibration_label, 0, 0, 1, 1)

        disclaimer = Gtk.Label('')
        disclaimer.set_markup('<small>NOTE: Autocalibration will autosave your changes. Your printer will restart at the end of calibration.</small>')
        disclaimer.set_line_wrap(True)
        disclaimer.set_hexpand(True)
        disclaimer.set_vexpand(False)
        disclaimer.set_halign(Gtk.Align.START)

        auto_grid.attach(disclaimer, 0, 1, 1, 1)

        self.calibrate_btn = self._gtk.ButtonImage("move", _('Finding ADXL345'), "color1", word_wrap=False)
        self.calibrate_btn.connect('clicked', self.start_calibration)
        self.calibrate_btn.set_sensitive(False)
        auto_grid.attach(self.calibrate_btn, 0, 2, 1, 1)

        grid.attach(auto_grid, 1, 0, 1, 1)

        self.status = Gtk.Label('Latest status:')
        self.status.set_hexpand(True)
        self.status.set_vexpand(False)
        self.status.set_halign(Gtk.Align.START)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        self.status.set_max_width_chars(68)
        self.status.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid.attach(self.status, 0, 2, 1, 1)

        self.content.add(grid)

    def start_calibration(self, *_):
        self._screen._ws.klippy.gcode_script('SHAPER_CALIBRATE HZ_PER_SEC=2')
        self.calibrate_btn.set_label(self.lang.gettext('Calibrating...'))
        self.calibrate_btn.set_sensitive(False)

    def set_opt_value(self, widget, opt, *args):
        shaper_freq_x = self.freq_xy_adj['shaper_freq_x'].get_value()
        shaper_freq_y = self.freq_xy_adj['shaper_freq_y'].get_value()
        shaper_type_x = self.freq_xy_combo['shaper_type_x'].get_active_text()
        shaper_type_y = self.freq_xy_combo['shaper_type_y'].get_active_text()

        self._screen._ws.klippy.gcode_script(
            'SET_INPUT_SHAPER SHAPER_FREQ_X={} SHAPER_TYPE_X={} SHAPER_FREQ_Y={} SHAPER_TYPE_Y={}'.format(
                shaper_freq_x, shaper_type_x, shaper_freq_y, shaper_type_y
            )
        )

    def save_config(self, *_):
        self._screen._ws.klippy.gcode_script(
            'SAVE_CONFIG'
        )

    def activate(self):
        self.get_updates()
        self._screen._ws.klippy.gcode_script(
            'ACCELEROMETER_QUERY'
        )

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            self.status.set_text('Status: {}'.format(data.replace('shaper_', '').replace('damping_', '')))
            if 'got 0' in data.lower():
                self.calibrate_btn.set_label(self.lang.gettext('Check ADXL345 Wiring'))
                self.calibrate_btn.set_sensitive(False)
            if 'Unknown command:"ACCELEROMETER_QUERY"'.lower() in data.lower():
                self.calibrate_btn.set_label(self.lang.gettext('ADXL Unconfigured'))
                self.calibrate_btn.set_sensitive(False)
            if 'must home' in data.lower():
                self.calibrate_btn.set_label(self.CALIBRATE_TEXT)
                self.calibrate_btn.set_sensitive(True)
            if 'adxl345 values' in data.lower():
                self.has_sensor = True
                self.calibrate_btn.set_sensitive(True)
                self.calibrate_btn.set_label(self.CALIBRATE_TEXT)
            if 'Recommended shaper_type_' in data:
                results = re.search(r'shaper_type_(?P<axis>[xy])\s*=\s*(?P<shaper_type>.*?), shaper_freq_.\s*=\s*(?P<shaper_freq>[0-9.]+)', data).groupdict()
                self.freq_xy_adj['shaper_freq_' + results['axis']].set_value(float(results['shaper_freq']))
                self.freq_xy_combo['shaper_type_' + results['axis']].set_active(SHAPERS.index(results['shaper_type']))
                if results['axis'] == 'y':
                    self.set_opt_value(None, None)
                    self.calibrate_btn.set_label(self.lang.gettext('Restarting...'))
                    self.save_config()

    def get_updates(self):
            config = self._screen.apiclient.send_request("printer/objects/query?configfile")
            input_shaper_config = config['result']['status']['configfile']['settings']['input_shaper']
            for _ in XY_FREQ:
                self.freq_xy_adj[_['config']].set_value(input_shaper_config[_['config']])
                shaper_slug = _['config'].replace('_freq_', '_type_')
                self.freq_xy_combo[shaper_slug].set_active(SHAPERS.index(input_shaper_config[shaper_slug]))
                self.freq_xy_combo[shaper_slug].connect("changed", self.set_opt_value, shaper_slug)