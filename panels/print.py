# -*- coding: utf-8 -*-
import gi
import humanize
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from datetime import datetime

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen.PrintPanel")

def create_panel(*args):
    return PrintPanel(*args)

class PrintPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.labels['files'] = {}
        self.sort_items = {
            "name": _("Name"),
            "date": _("Date")
        }
        self.sort_char = ["↑","↓"]

        sortdir = self._config.get_main_config_option("print_sort_dir","name_asc")
        sortdir = sortdir.split('_')
        if sortdir[0] not in ["name","date"] or sortdir[1] not in ["asc","desc"]:
            sortdir = ["name","asc"]
        self.sort_current = [sortdir[0], 0 if sortdir[1] == "asc" else 1] # 0 for asc, 1 for desc

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)

        sort = Gtk.Label()
        sort.set_text(_("Sort by: "))
        sbox = Gtk.Box(spacing=0)
        sbox.set_vexpand(False)
        sbox.add(sort)
        i = 1
        for name, val in self.sort_items.items():
            s = self._gtk.Button(val, "color%s" % (i%4))
            s.set_label(val)
            if name == sortdir[0]:
                s.set_label("%s %s" % (s.get_label(), self.sort_char[self.sort_current[1]]))
            s.connect("clicked", self.change_sort, name)
            self.labels['sort_%s' % name] = s
            sbox.add(s)
            i += 1
        sbox.set_hexpand(True)
        sbox.set_vexpand(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.pack_start(sbox, False, False, 0)
        box.pack_start(scroll, True, True, 0)

        self.labels['filelist'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.labels['filelist'].set_vexpand(True)

        self.labels['filelist'] = Gtk.Grid()
        self.files = {}

        GLib.idle_add(self.reload_files)

        scroll.add(self.labels['filelist'])
        self.content.add(box)
        self._screen.files.add_file_callback(self._callback)


        return

    def add_file(self, filename, show=True):
        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo == None:
            return

        frame = Gtk.Frame()
        frame.set_property("shadow-type",Gtk.ShadowType.NONE)
        frame.get_style_context().add_class("frame-item")


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

        actions = self._gtk.ButtonImage("print",None,"color3")
        actions.connect("clicked", self.confirm_print, filename)
        actions.set_hexpand(False)
        actions.set_halign(Gtk.Align.END)

        file = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        file.set_hexpand(True)
        file.set_vexpand(False)

        icon = self._gtk.Image("file.svg", False, 1.6, 1.6)
        pixbuf = self.get_file_image(filename)
        if pixbuf != None:
            icon.set_from_pixbuf(pixbuf)

        file.add(icon)
        file.add(labels)
        file.add(actions)
        frame.add(file)

        self.files[filename] = frame

        reverse = False if self.sort_current[1] == 0 else True
        if self.sort_current[0] == "date":
            files = sorted(self.files, reverse=reverse,
                key=lambda item: self._screen.files.get_file_info(item)['modified'])
        else:
            files = sorted(self.files, reverse=reverse)
        pos = files.index(filename)

        self.labels['files'][filename] = {
            "icon": icon,
            "info": info,
            "name": name
        }

        self.labels['filelist'].insert_row(pos)
        self.labels['filelist'].attach(self.files[filename], 0, pos, 1, 1)
        if show == True:
            self.labels['filelist'].show_all()

    def change_sort(self, widget, key):
        if self.sort_current[0] == key:
            self.sort_current[1] = (self.sort_current[1] + 1) % 2
        else:
            oldkey = self.sort_current[0]
            logger.info("Changing %s to %s" % ('sort_%s' % oldkey, self.sort_items[self.sort_current[0]]))
            self.labels['sort_%s' % oldkey].set_label("%s" % self.sort_items[oldkey])
            self.labels['sort_%s' % oldkey].show_all()
            self.sort_current = [key, 0]
        self.labels['sort_%s' % key].set_label("%s %s" % (self.sort_items[key], self.sort_char[self.sort_current[1]]))
        self.labels['sort_%s' % key].show()

        GLib.idle_add(self.reload_files)

    def get_file_info_str(self, filename):
        _ = self.lang.gettext

        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo == None:
            return

        return "<small>%s: <b>%s</b> - %s: <b>%s</b>\n%s: <b>%s</b></small>" % (
            _("Uploaded"),
            datetime.fromtimestamp(fileinfo['modified']).strftime("%Y-%m-%d %H:%M"),
            _("Size"),
            humanize.naturalsize(fileinfo['size']),
            _("Print Time"),
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
            self.add_file(file, False)

        self.labels['filelist'].show_all()

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
        _ = self.lang.gettext
        buttons = [
            {"name":_("Print"), "response": Gtk.ResponseType.OK},
            {"name":_("Cancel"),"response": Gtk.ResponseType.CANCEL}
        ]

        label = Gtk.Label()
        label.set_markup("%s <b>%s</b>%s" % (_("Are you sure you want to print"), filename, _("?")))
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = Gtk.Grid()
        grid.add(label)
        grid.set_size_request(self._screen.width - 60, -1)

        pixbuf = self.get_file_image(filename, 8, 3.2)
        if pixbuf != None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            grid.attach_next_to(image, label, Gtk.PositionType.BOTTOM, 1, 3)

        #table.attach(label, 0, 1, 0, 1, Gtk.AttachOptions.SHRINK | Gtk.AttachOptions.FILL)
        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)

        dialog = self._gtk.Dialog(self._screen, buttons, grid, self.confirm_print_response,  filename)

    def confirm_print_response(self, widget, response_id, filename):
        widget.destroy()

        if response_id == Gtk.ResponseType.CANCEL:
            return

        logging.info("Starting print: %s" % (filename))
        self._screen._ws.klippy.print_start(filename)
