# -*- coding: utf-8 -*-
import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
from datetime import datetime

from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return PrintPanel(*args)

class PrintPanel(ScreenPanel):
    cur_directory = "gcodes"
    dir_panels = {}
    filelist = {'gcodes': {'directories': [], 'files': []}}

    def initialize(self, panel_name):
        _ = self.lang.gettext
        self.labels['directories'] = {}
        self.labels['files'] = {}
        self.sort_items = {
            "name": _("Name"),
            "date": _("Date")
        }
        self.sort_char = ["↑", "↓"]

        sortdir = self._config.get_main_config_option("print_sort_dir", "name_asc")
        sortdir = sortdir.split('_')
        if sortdir[0] not in ["name", "date"] or sortdir[1] not in ["asc", "desc"]:
            sortdir = ["name", "asc"]
        self.sort_current = [sortdir[0], 0 if sortdir[1] == "asc" else 1]  # 0 for asc, 1 for desc

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        sort = Gtk.Label()
        sort.set_text(_("Sort by: "))
        sbox = Gtk.Box(spacing=0)
        sbox.set_vexpand(False)
        sbox.add(sort)
        i = 1
        for name, val in self.sort_items.items():
            s = self._gtk.Button(val, "color%s" % (i % 4))
            s.set_label(val)
            if name == sortdir[0]:
                s.set_label("%s %s" % (s.get_label(), self.sort_char[self.sort_current[1]]))
            s.connect("clicked", self.change_sort, name)
            self.labels['sort_%s' % name] = s
            sbox.add(s)
            i += 1

        refresh = self._gtk.ButtonImage("refresh", None, None, .5)
        refresh.connect('clicked', self._refresh_files)
        sbox.add(refresh)
        sbox.set_hexpand(True)
        sbox.set_vexpand(False)

        pbox = Gtk.Box(spacing=0)
        pbox.set_hexpand(True)
        pbox.set_vexpand(False)
        self.labels['path'] = Gtk.Label("  /")
        pbox.add(self.labels['path'])
        self.labels['path_box'] = pbox

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_vexpand(True)
        box.pack_start(sbox, False, False, 0)
        box.pack_start(pbox, False, False, 0)
        box.pack_start(scroll, True, True, 0)

        self.dir_panels['gcodes'] = Gtk.Grid()
        self.files = {}
        self.directories = {}

        GLib.idle_add(self.reload_files)

        scroll.add(self.dir_panels['gcodes'])
        self.scroll = scroll
        self.content.add(box)
        self._screen.files.add_file_callback(self._callback)

    def activate(self):
        if self.cur_directory != "gcodes":
            self.change_dir(None, "gcodes")

    def add_directory(self, directory, show=True):
        parent_dir = '/'.join(directory.split('/')[:-1])
        if directory not in self.filelist:
            self.filelist[directory] = {'directories': [], 'files': [], 'modified': 0}
            self.filelist[parent_dir]['directories'].append(directory)

        if directory not in self.labels['directories']:
            frame = Gtk.Frame()
            frame.get_style_context().add_class("frame-item")

            name = Gtk.Label()
            name.set_markup("<big><b>%s</b></big>" % (directory.split("/")[-1]))
            name.set_hexpand(True)
            name.set_halign(Gtk.Align.START)
            name.set_line_wrap(True)
            name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

            info = Gtk.Label()
            info.set_halign(Gtk.Align.START)

            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            labels.add(name)
            labels.add(info)
            labels.set_vexpand(True)
            labels.set_valign(Gtk.Align.CENTER)
            labels.set_halign(Gtk.Align.START)

            actions = self._gtk.ButtonImage("load", None, "color3")
            actions.connect("clicked", self.change_dir, directory)
            actions.set_hexpand(False)
            actions.set_halign(Gtk.Align.END)

            file = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            file.set_hexpand(True)
            file.set_vexpand(False)

            icon = self._gtk.Image("folder", 1)

            file.add(icon)
            file.add(labels)
            file.add(actions)
            frame.add(file)

            self.directories[directory] = frame

            self.labels['directories'][directory] = {
                "icon": icon,
                "info": info,
                "name": name
            }

            self.dir_panels[directory] = Gtk.Grid()

        reverse = False if self.sort_current[1] == 0 else True
        if self.sort_current[0] == "date":
            dirs = sorted(self.filelist[parent_dir]['directories'], reverse=reverse,
                          key=lambda item: self.filelist[item]['modified'])
        else:
            dirs = sorted(self.filelist[parent_dir]['directories'], reverse=reverse)
        pos = dirs.index(directory)

        self.dir_panels[parent_dir].insert_row(pos)
        self.dir_panels[parent_dir].attach(self.directories[directory], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[parent_dir].show_all()

    def add_file(self, filepath, show=True):
        _ = self.lang.gettext

        fileinfo = self._screen.files.get_file_info(filepath)
        if fileinfo is None:
            return

        dir = ("gcodes/%s" % filepath).split('/')[:-1]
        directory = '/'.join(dir)
        filename = filepath.split('/')[-1]
        for i in range(1, len(dir)):
            curdir = "/".join(dir[0:i])
            newdir = "/".join(dir[0:i+1])
            if newdir not in self.filelist[curdir]['directories']:
                self.add_directory(newdir)

        if filename not in self.filelist[directory]['files']:
            for i in range(1, len(dir)):
                curdir = "/".join(dir[0:i+1])
                if curdir != "gcodes" and fileinfo['modified'] > self.filelist[curdir]['modified']:
                    self.filelist[curdir]['modified'] = fileinfo['modified']
                    self.labels['directories'][curdir]['info'].set_markup(
                        "<small>%s: <b>%s</b></small>" %
                        (_("Modified"), datetime.fromtimestamp(fileinfo['modified']).strftime("%Y-%m-%d %H:%M")))
            self.filelist[directory]['files'].append(filename)

        if filepath not in self.files:
            frame = Gtk.Frame()
            frame.get_style_context().add_class("frame-item")

            name = Gtk.Label()
            name.set_markup("<big><b>%s</b></big>" % (os.path.splitext(filename)[0].replace("_", " ")))
            name.set_hexpand(True)
            name.set_halign(Gtk.Align.START)
            name.set_line_wrap(True)
            name.set_line_wrap_mode(Pango.WrapMode.CHAR)

            info = Gtk.Label()
            info.set_halign(Gtk.Align.START)
            info.set_markup(self.get_file_info_str(filepath))
            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            labels.add(name)
            labels.add(info)
            labels.set_vexpand(True)
            labels.set_valign(Gtk.Align.CENTER)
            labels.set_halign(Gtk.Align.START)

            actions = self._gtk.ButtonImage("print", None, "color3")
            actions.connect("clicked", self.confirm_print, filepath)
            actions.set_hexpand(False)
            actions.set_halign(Gtk.Align.END)

            file = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            file.set_hexpand(True)
            file.set_vexpand(False)

            icon = Gtk.Image()
            pixbuf = self.get_file_image(filepath)
            if pixbuf is not None:
                icon.set_from_pixbuf(pixbuf)
            else:
                icon = self._gtk.Image("file", 1.6)

            file.add(icon)
            file.add(labels)
            if os.path.splitext(filename)[1] in [".gcode", ".g", ".gco"]:
                file.add(actions)
            frame.add(file)

            self.files[filepath] = frame
            self.labels['files'][filepath] = {
                "icon": icon,
                "info": info,
                "name": name
            }

        reverse = False if self.sort_current[1] == 0 else True
        if self.sort_current[0] == "date":
            files = sorted(
                self.filelist[directory]['files'], reverse=reverse,
                key=lambda item: self._screen.files.get_file_info(("%s/%s" % (directory, item))[7:])['modified']
            )
        else:
            files = sorted(self.filelist[directory]['files'], reverse=reverse)
        pos = files.index(filename)
        pos += len(self.filelist[directory]['directories'])

        self.dir_panels[directory].insert_row(pos)
        self.dir_panels[directory].attach(self.files[filepath], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[directory].show_all()

    def back(self):
        if len(self.cur_directory.split('/')) > 1:
            self.change_dir(None, '/'.join(self.cur_directory.split('/')[:-1]))
            return True
        return False

    def change_dir(self, widget, directory):
        if directory not in self.dir_panels:
            return
        logging.debug("Changing dir to %s" % directory)

        for child in self.scroll.get_children():
            self.scroll.remove(child)
        self.cur_directory = directory
        self.labels['path'].set_text("  /%s" % self.cur_directory[7:])

        self.scroll.add(self.dir_panels[directory])
        self.content.show_all()

    def change_sort(self, widget, key):
        if self.sort_current[0] == key:
            self.sort_current[1] = (self.sort_current[1] + 1) % 2
        else:
            oldkey = self.sort_current[0]
            logging.info("Changing %s to %s" % ('sort_%s' % oldkey, self.sort_items[self.sort_current[0]]))
            self.labels['sort_%s' % oldkey].set_label("%s" % self.sort_items[oldkey])
            self.labels['sort_%s' % oldkey].show_all()
            self.sort_current = [key, 0]
        self.labels['sort_%s' % key].set_label("%s %s" % (self.sort_items[key], self.sort_char[self.sort_current[1]]))
        self.labels['sort_%s' % key].show()
        GLib.idle_add(self.reload_files)

        self._config.set("main", "print_sort_dir", "%s_%s" % (key, "asc" if self.sort_current[1] == 0 else "desc"))
        self._config.save_user_config_options()

    def confirm_print(self, widget, filename):
        _ = self.lang.gettext
        buttons = [
            {"name": _("Print"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        label = Gtk.Label()
        label.set_markup("<b>%s</b>\n" % (filename))
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = Gtk.Grid()
        grid.add(label)
        grid.set_size_request(self._screen.width - 60, -1)

        pixbuf = self.get_file_image(filename, 8, 3.2)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            grid.attach_next_to(image, label, Gtk.PositionType.BOTTOM, 1, 3)

        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)

        self._gtk.Dialog(self._screen, buttons, grid, self.confirm_print_response, filename)

    def confirm_print_response(self, widget, response_id, filename):
        widget.destroy()

        if response_id == Gtk.ResponseType.CANCEL:
            return

        logging.info("Starting print: %s" % (filename))
        self._screen._ws.klippy.print_start(filename)

    def delete_file(self, filename):
        dir_parts = ("gcodes/%s" % filename).split('/')[:-1]
        directory = '/'.join(dir_parts)
        self.filelist[directory]["files"].pop(self.filelist[directory]["files"].index(filename.split('/')[-1]))
        i = len(dir_parts)
        while i > 1:
            cur_dir = '/'.join(dir_parts[0:i])
            if len(self.filelist[cur_dir]['directories']) > 0 or len(self.filelist[cur_dir]['files']) > 0:
                break
            par_dir = '/'.join(cur_dir.split('/')[:-1])

            if self.cur_directory == cur_dir:
                self.change_dir(None, par_dir)

            del self.filelist[cur_dir]
            self.filelist[par_dir]['directories'].pop(self.filelist[par_dir]['directories'].index(cur_dir))
            self.dir_panels[par_dir].remove(self.directories[cur_dir])
            del self.directories[cur_dir]
            del self.labels['directories'][cur_dir]
            self.dir_panels[par_dir].show_all()
            i -= 1

        self.dir_panels[directory].remove(self.files[filename])
        self.dir_panels[directory].show_all()
        self.files.pop(filename)

    def get_file_info_str(self, filename):
        _ = self.lang.gettext

        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo is None:
            return

        return "<small>%s: <b>%s</b>\n%s: <b>%s</b>\n%s: <b>%s</b></small>" % (
            _("Uploaded"),
            datetime.fromtimestamp(fileinfo['modified']).strftime("%Y-%m-%d %H:%M"),
            _("Size"),
            self.formatsize(fileinfo['size']),
            _("Print Time"),
            self.get_print_time(filename)
        )

    def formatsize(self, size):
        size = float(size)
        suffixes = ["kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
        for i, suffix in enumerate(suffixes, start=2):
            unit = 1024 ** i
            if size < unit:
                return ("%.1f %s") % ((1024 * size / unit), suffix)

    def get_print_time(self, filename):
        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo is None:
            return

        if "estimated_time" in fileinfo:
            print_time = fileinfo['estimated_time']
            print_str = ""

            # Figure out how many days
            print_val = int(print_time/86400)
            if print_val > 0:
                print_str = "%sd " % print_val

            # Take remainder from days and divide by hours
            print_val = int((print_time % 86400)/3600)
            if print_val > 0:
                print_str = "%s%sh " % (print_str, print_val)

            print_val = int(((print_time % 86400) % 3600)/60)
            print_str = "%s%sm" % (print_str, print_val)
            return print_str
        return "Unavailable"

    def reload_files(self, widget=None):
        self.filelist = {'gcodes': {'directories': [], 'files': []}}
        for dirpan in self.dir_panels:
            for child in self.dir_panels[dirpan].get_children():
                self.dir_panels[dirpan].remove(child)

        flist = sorted(self._screen.files.get_file_list(), key=lambda item: '/' in item)
        for file in flist:
            GLib.idle_add(self.add_file, file)

    def update_file(self, filename):
        if filename not in self.labels['files']:
            logging.debug("Cannot update file, file not in labels: %s" % filename)
            return

        logging.info("Updating file %s" % filename)
        self.labels['files'][filename]['info'].set_markup(self.get_file_info_str(filename))

        # Update icon
        pixbuf = self.get_file_image(filename)
        if pixbuf is not None:
            self.labels['files'][filename]['icon'].set_from_pixbuf(pixbuf)

    def _callback(self, newfiles, deletedfiles, updatedfiles=[]):
        logging.debug("newfiles: %s", newfiles)
        for file in newfiles:
            self.add_file(file)
        logging.debug("deletedfiles: %s", deletedfiles)
        for file in deletedfiles:
            self.delete_file(file)
        logging.debug("updatefiles: %s", updatedfiles)
        for file in updatedfiles:
            self.update_file(file)

    def _refresh_files(self, widget):
        self._files.refresh_files()

    def process_update(self, action, data):
        if action == "notify_gcode_response":
            if "unknown" in data.lower():
                self._screen.show_popup_message("%s" % data)
        return
