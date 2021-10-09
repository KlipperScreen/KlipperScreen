import gi
import re
import subprocess

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
SCRIPT_PATH = '/home/pi/klipper/scripts/calibrate_shaper.py'

class InputShaperPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext

        self.has_sensor = False
        self.x_file = None
        self.y_file = None

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        grid.set_vexpand(True)
        grid.set_hexpand(True)
        grid.get_style_context().add_class("input-shaper")

        title = Gtk.Label()
        title.set_markup('<big>Input Shaper</big>')
        title.get_style_context()
        grid.attach(title, 0, 0, 1, 1)

        input_grid = Gtk.Grid()
        input_grid.set_hexpand(True)
        input_grid.set_vexpand(True)

        self.freq_xy_adj = {}
        self.freq_xy_combo = {}

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
            name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

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
            input_grid.attach(frame, i, 0, 1, 1)

        grid.attach(input_grid, 0, 1, 1, 1)

        self.calibrate_btn = self._gtk.ButtonImage("move", _('No ADXL345 Found'), "color1", word_wrap=False)
        self.calibrate_btn.connect('clicked', self.start_calibration)

        self.calibrate_btn.set_sensitive(False)
        grid.attach(self.calibrate_btn, 0, 2, 1, 1)

        self.status = Gtk.Label('Latest status:')
        grid.attach(self.status, 0, 3, 1, 1)
        self.status.set_hexpand(True)
        self.status.set_halign(Gtk.Align.START)

        self.content.add(grid)
        self._screen._ws.send_method("server.gcode_store", {"count": 100}, self.gcode_response)

    def start_calibration(self, *_):
        self._screen._ws.klippy.gcode_script('TEST_RESONANCES AXIS=X')
        self._screen._ws.klippy.gcode_script('TEST_RESONANCES AXIS=Y')
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

    def activate(self):
        self.get_updates()
        self._screen._ws.klippy.gcode_script(
            'ACCELEROMETER_QUERY'
        )

    def gcode_response(self, result, method, *_):
        print(method)
        if method != "server.gcode_store":
            return

        for resp in result['result']['gcode_store']:
            self.status.set_text('Status: {}'.format(resp['message']))

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            self.status.set_text('Status: {}'.format(data))
            if 'adxl345 values' in data.lower():
                self.has_sensor = True
                self.calibrate_btn.set_sensitive(True)
                self.calibrate_btn.set_label(self.lang.gettext('Calibrate Input Shaper'))
            if 'Resonances data written to' in data:
                filename = re.search(r'(?P<path>\/tmp\/resonances_(?P<axis>[xy]).*\.csv)', data).groupdict()
                setattr(self, '{}_file'.format(filename['axis']), filename['path'])
                if filename['axis'] == 'y':
                    self.calculate()

    def calculate(self):
        self.calibrate_btn.set_label(self.lang.gettext('Computing values...'))
        s = subprocess.run([SCRIPT_PATH, self.x_file, "-o", "/tmp/x.png"], stdout=subprocess.PIPE)
        details = re.search(r'shaper is (?P<shaper>.*) @ (?P<freq>[0-9.]+) Hz', s.stdout.decode('utf8')).groupdict()
        self.freq_xy_adj['shaper_freq_x'].set_value(float(details['freq']))
        self.freq_xy_combo['shaper_type_x'].set_active(SHAPERS.index(details['shaper']))

        s = subprocess.run([SCRIPT_PATH, self.y_file, "-o", "/tmp/y.png"], stdout=subprocess.PIPE)
        details = re.search(r'shaper is (?P<shaper>.*) @ (?P<freq>[0-9.]+) Hz', s.stdout.decode('utf8')).groupdict()
        self.freq_xy_adj['shaper_freq_y'].set_value(float(details['freq']))
        self.freq_xy_combo['shaper_type_y'].set_active(SHAPERS.index(details['shaper']))
        self.calibrate_btn.set_sensitive(True)
        self.calibrate_btn.set_label(self.lang.gettext('Calibrate Input Shaper'))
        self.set_opt_value(None, None)


    def get_updates(self):
            config = self._screen.apiclient.send_request("printer/objects/query?configfile")
            input_shaper_config = config['result']['status']['configfile']['settings']['input_shaper']
            for _ in XY_FREQ:
                self.freq_xy_adj[_['config']].set_value(input_shaper_config[_['config']])
                shaper_slug = _['config'].replace('_freq_', '_type_')
                self.freq_xy_combo[shaper_slug].set_active(SHAPERS.index(input_shaper_config[shaper_slug]))
                self.freq_xy_combo[shaper_slug].connect("changed", self.set_opt_value, shaper_slug)