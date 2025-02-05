import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Mechanical Calibration")
        super().__init__(screen, title)

        self.menu = ['mcalibrate']

        grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        
        self.above_text = Gtk.Label(f'\n{_("Adjust the screws of the secondary extruder, on the right side.")}')
        self.below_text = Gtk.Label(f'\n{_("After completing the procedure, press the button to finish.")}\n')

        self.content.add(self.above_text)
        self.content.add(self.below_text)

        self.start_btn = self._gtk.Button("screw-adjust", f'  {_("Start")}', "color2", 1, Gtk.PositionType.LEFT)
        self.finish_btn = self._gtk.Button("complete", f'  {_("Finish")}', "color3", 1, Gtk.PositionType.LEFT)
        self.finish_btn.set_sensitive(False)
        self.start_btn.connect("clicked", self.start_calibration)
        self.finish_btn.connect("clicked", self.finish_calibration)
        grid.attach(self.start_btn, 0, 1, 1, 2)
        grid.attach(self.finish_btn, 0, 3, 1, 2)

        self.labels['mcalibrate'] = Gtk.Grid(row_homogeneous=True, column_homogeneous=True)
        self.labels['mcalibrate'].attach(grid, 0, 0, 1, 2)

        self.content.add(self.labels['mcalibrate'])

    def start_calibration(self, button):
        self._screen._ws.klippy.gcode_script("EXTRUDER_SCREW_PLACEMENT")

    def finish_calibration(self, button):
        self._screen._ws.klippy.gcode_script("IDEX_OFFSET Z=0")
        self._screen._ws.klippy.gcode_script("G28 Z")
        self._screen._ws.klippy.gcode_script("M84")
        self.start_btn.set_label(f'  {_("Start")}')
        self.start_btn.set_sensitive(True)
        self.finish_btn.set_sensitive(False)        
        self._screen._menu_go_back()

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            if data == "// entrou no EXTRUDER_SCREW_PLACEMENT":
                self.start_btn.set_sensitive(False)

            if data == "// finalizou o EXTRUDER_SCREW_PLACEMENT":
                self._screen._confirm_send_action(
                    None,
                    "Iniciar a calibração mecânica?",
                    "printer.gcode.script",
                    {"script": "PROBE_CALIBRATE_AUTOMATIC"}
                )
                self.start_btn.set_label(f'  {_("Restart")}')
                self.start_btn.set_sensitive(True)

            if data == "// entrou no PROBE_CALIBRATE_AUTOMATIC":
                self.start_btn.set_sensitive(False)
                self.finish_btn.set_sensitive(False)                

            if data == "// finalizou o PROBE_CALIBRATE_AUTOMATIC":
                self._screen._confirm_send_action(
                    None,
                    "Finalizar a calibração mecânica?",
                    "printer.gcode.script",
                    {"script": "ACTION_RESPOND_INFO M='finalizou a calibração'"}
                )
                self.start_btn.set_label(f'  {_("Restart")}')
                self.start_btn.set_sensitive(True)

            if data == "// finalizou a calibração":
                self.finish_calibration(None)