import gi
import humanize
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from KlippyGtk import KlippyGtk
from KlippyGcodes import KlippyGcodes
from panels.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.PrintPanel")

class PrintPanel(ScreenPanel):
    def initialize(self, panel_name):
        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.pack_start(scroll, True, True, 0)


        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.set_hexpand(True)
        bar.set_vexpand(False)
        bar.set_halign(Gtk.Align.END)
        bar.set_margin_top(5)
        bar.set_margin_bottom(5)
        bar.set_margin_end(5)
        refresh = KlippyGtk.ButtonImage('refresh', None, None, 60, 60)
        refresh.connect("clicked", self.reload_files)
        bar.add(refresh)

        back = KlippyGtk.ButtonImage('back', None, None, 60, 60)
        back.connect("clicked", self._screen._menu_go_back)
        bar.add(back)

        box.pack_end(bar, False, False, 0)


        self.labels['filelist'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['filelist'].set_vexpand(True)

        #self.labels['filelist'] = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
        #self.labels['filelist'].set_vexpand(True)
        self.labels['filelist'] = Gtk.Grid()

        self.files = {}
        self.reload_files()

        scroll.add(self.labels['filelist'])


        self.panel = box

        self._screen.files.add_file_callback(self._callback)


        return

    def add_file(self, filename):

        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo == None:
            return

        frame = Gtk.Frame()
        frame.set_property("shadow-type",Gtk.ShadowType.NONE)


        name = Gtk.Label()
        n = 50
        name.set_markup("<big>%s</big>" % ("\n".join([filename[i:i+n] for i in range(0, len(filename), n)])))
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)

        info = Gtk.Label("Uploaded: blah - Size: blah")
        info.set_halign(Gtk.Align.START)
        info.set_markup("<small>Uploaded: <b>%s</b> - Size: <b>%s</b></small>" % (
            fileinfo['modified'],
            humanize.naturalsize(fileinfo['size'])
        ))
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        labels.add(name)
        labels.add(info)
        labels.set_vexpand(True)
        labels.set_valign(Gtk.Align.CENTER)
        labels.set_halign(Gtk.Align.START)

        actions = KlippyGtk.ButtonImage("print",None,"color3")
        actions.connect("clicked", self.confirm_print, filename)
        actions.set_hexpand(False)
        actions.set_halign(Gtk.Align.END)

        file = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        file.set_margin_top(1)
        file.set_margin_end(15)
        file.set_margin_start(15)
        file.set_margin_bottom(1)
        file.set_hexpand(True)
        file.set_vexpand(False)
        file.add(KlippyGtk.Image("file", False, 35, 35))
        file.add(labels)
        file.add(actions)
        frame.add(file)

        self.files[filename] = frame
        files = sorted(self.files)
        pos = files.index(filename)

        self.labels['filelist'].insert_row(pos)
        self.labels['filelist'].attach(self.files[filename], 0, pos, 1, 1)
        self.labels['filelist'].show_all()

    def delete_file(self, filename):
        files = sorted(self.files)
        pos = files.index(filename)
        self.labels['filelist'].remove_row(pos)
        self.labels['filelist'].show_all()
        self.files.pop(filename)

    def reload_files(self, widget=None):
        for child in self.labels['filelist'].get_children():
            self.labels['filelist'].remove(child)
        self.labels['filelist'].show_all()

        for file in self._screen.files.get_file_list():
            #TODO: Change priority on this
            GLib.idle_add(self.add_file, file)

    def _callback(self, newfiles, deletedfiles):
        logger.debug("newfiles: %s", newfiles)
        for file in newfiles:
            self.add_file(file)
        logger.debug("deletedfiles: %s", deletedfiles)
        for file in deletedfiles:
            self.delete_file(file)

    def confirm_print(self, widget, filename):
        dialog = KlippyGtk.ConfirmDialog(
            self._screen,
            "Are you sure you want to print <b>%s</b>?" % (filename),
            [
                {
                    "name": "Print",
                    "response": Gtk.ResponseType.OK
                },
                {
                    "name": "Cancel",
                    "response": Gtk.ResponseType.CANCEL
                }
            ],
            self.confirm_print_response,
            filename
        )

    def confirm_print_response(self, widget, response_id, filename):
        widget.destroy()

        if response_id == Gtk.ResponseType.CANCEL:
            return

        logging.info("Starting print: %s" % (filename))
        self._screen._ws.klippy.print_start(filename)
