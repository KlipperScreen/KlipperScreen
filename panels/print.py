import gi
import humanize
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from datetime import datetime

from KlippyGtk import KlippyGtk
from KlippyGcodes import KlippyGcodes
from panels.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.PrintPanel")

class PrintPanel(ScreenPanel):
    def initialize(self, panel_name):
        self.labels['files'] = {}

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
        #bar.add(refresh)

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
        #n = 50
        #name.set_markup("<big>%s</big>" % ("\n".join([filename[i:i+n] for i in range(0, len(filename), n)])))
        name.set_markup("<big><b>%s</b></big>" % (filename))
        name.set_hexpand(True)
        name.set_halign(Gtk.Align.START)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        info = Gtk.Label("Uploaded: blah - Size: blah")
        info.set_halign(Gtk.Align.START)
        info.set_markup(self.get_file_info_str(filename))
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

        icon = KlippyGtk.Image("file", False, 100, 100)
        pixbuf = self.get_file_image(filename)
        if pixbuf != None:
            icon.set_from_pixbuf(pixbuf)

        file.add(icon)
        file.add(labels)
        file.add(actions)
        frame.add(file)

        self.files[filename] = frame
        files = sorted(self.files)
        pos = files.index(filename)

        self.labels['files'][filename] = {
            "icon": icon,
            "info": info,
            "name": name
        }

        self.labels['filelist'].insert_row(pos)
        self.labels['filelist'].attach(self.files[filename], 0, pos, 1, 1)
        self.labels['filelist'].show_all()

    def get_file_image(self, filename, width=100, height=100):
        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo == None:
            return None

        if "thumbnails" in fileinfo and len(fileinfo["thumbnails"]) > 0:
            thumbnail = fileinfo['thumbnails'][0]
            return KlippyGtk.PixbufFromFile("/tmp/.KS-thumbnails/%s-%s" % (fileinfo['filename'], thumbnail['size']),
                None, width, height)
        return None


    def get_file_info_str(self, filename):
        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo == None:
            return

        return "<small>Uploaded: <b>%s</b> - Size: <b>%s</b>\nPrint Time: <b>%s</b></small>" % (
            datetime.fromtimestamp(fileinfo['modified']).strftime("%Y-%m-%d %H:%M"),
            humanize.naturalsize(fileinfo['size']),
            self.get_print_time(filename)
        )

    def get_print_time (self, filename):
        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo == None:
            return

        if "estimated_time" in fileinfo:
            print_time = fileinfo['estimated_time']
            print_str = ""

            # Figure out how many days
            print_val = int(print_time/86400)
            if print_val > 0:
                print_str = "%sd " % print_val

            # Take remainder from days and divide by hours
            print_val = int((print_time%86400)/3600)
            if print_val > 0:
                print_str = "%s%sh " % (print_str, print_val)

            print_val = int(((print_time%86400)%3600)/60)
            print_str = "%s%sm" % (print_str, print_val)
            return print_str
        return "Unavailable"

    def update_file(self, filename):
        if filename not in self.labels['files']:
            return

        print("Updating file %s" % filename)
        self.labels['files'][filename]['info'].set_markup(self.get_file_info_str(filename))

        # Update icon
        pixbuf = self.get_file_image(filename)
        if pixbuf != None:
            self.labels['files'][filename]['icon'].set_from_pixbuf(pixbuf)

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

    def _callback(self, newfiles, deletedfiles, updatedfiles=[]):
        logger.debug("newfiles: %s", newfiles)
        for file in newfiles:
            self.add_file(file)
        logger.debug("deletedfiles: %s", deletedfiles)
        for file in deletedfiles:
            self.delete_file(file)
        logger.debug("updatefiles: %s", updatedfiles)
        for file in updatedfiles:
            self.update_file(file)

    def confirm_print(self, widget, filename):
        dialog = Gtk.Dialog()
        #TODO: Factor other resolutions in
        dialog.set_default_size(self._screen.width - 15, self._screen.height - 15)
        dialog.set_resizable(False)
        dialog.set_transient_for(self._screen)
        dialog.set_modal(True)

        dialog.add_button(button_text="Print", response_id=Gtk.ResponseType.OK)
        dialog.add_button(button_text="Cancel", response_id=Gtk.ResponseType.CANCEL)

        dialog.connect("response", self.confirm_print_response, filename)
        dialog.get_style_context().add_class("dialog")

        content_area = dialog.get_content_area()
        content_area.set_margin_start(15)
        content_area.set_margin_end(15)
        content_area.set_margin_top(15)
        content_area.set_margin_bottom(15)

        label = Gtk.Label()
        label.set_markup("Are you sure you want to print <b>%s</b>?" % (filename))
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.get_style_context().add_class("text")

        grid = Gtk.Grid()
        grid.add(label)
        grid.set_size_request(self._screen.width - 60, -1)

        pixbuf = self.get_file_image(filename, self._screen.width/2, self._screen.height/3)
        if pixbuf != None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_margin_top(20)
            grid.attach_next_to(image, label, Gtk.PositionType.BOTTOM, 1, 3)

        #table.attach(label, 0, 1, 0, 1, Gtk.AttachOptions.SHRINK | Gtk.AttachOptions.FILL)
        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        content_area.add(grid)
        dialog.resize(self._screen.width - 15, self._screen.height - 15)
        dialog.show_all()

    def confirm_print_response(self, widget, response_id, filename):
        widget.destroy()

        if response_id == Gtk.ResponseType.CANCEL:
            return

        logging.info("Starting print: %s" % (filename))
        self._screen._ws.klippy.print_start(filename)
