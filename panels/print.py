# -*- coding: utf-8 -*-
import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from datetime import datetime

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return PrintPanel(*args)


class PrintPanel(ScreenPanel):
    cur_directory = "gcodes"
    dir_panels = {}
    filelist = {'gcodes': {'directories': [], 'files': []}}

    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)
        sortdir = self._config.get_main_config().get("print_sort_dir", "name_asc")
        sortdir = sortdir.split('_')
        if sortdir[0] not in ["name", "date"] or sortdir[1] not in ["asc", "desc"]:
            sortdir = ["name", "asc"]
        self.sort_current = [sortdir[0], 0 if sortdir[1] == "asc" else 1]  # 0 for asc, 1 for desc
        self.sort_items = {
            "name": _("Name"),
            "date": _("Date")
        }
        self.sort_icon = ["arrow-up", "arrow-down"]
        self.scroll = self._gtk.ScrolledWindow()
        self.files = {}
        self.directories = {}
        self.labels['directories'] = {}
        self.labels['files'] = {}

    def initialize(self, panel_name):
        sort = Gtk.Label(_("Sort:"))
        sbox = Gtk.Box(spacing=0)
        sbox.set_vexpand(False)
        sbox.pack_start(sort, False, False, 5)
        for i, (name, val) in enumerate(self.sort_items.items(), start=1):
            s = self._gtk.ButtonImage(None, val, f"color{i % 4}", .5, Gtk.PositionType.RIGHT, 1)
            if name == self.sort_current[0]:
                s.set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]], self._gtk.img_scale * .5))
            s.connect("clicked", self.change_sort, name)
            self.labels[f'sort_{name}'] = s
            sbox.add(s)
        refresh = self._gtk.ButtonImage("refresh", scale=.66)
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
        box.pack_start(self.scroll, True, True, 0)

        self.dir_panels['gcodes'] = Gtk.Grid()

        GLib.idle_add(self.reload_files)

        self.scroll.add(self.dir_panels['gcodes'])
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
            self._create_frame(directory)
        reverse = self.sort_current[1] != 0
        dirs = sorted(
            self.filelist[parent_dir]['directories'],
            reverse=reverse, key=lambda item: self.filelist[item]['modified']
        ) if self.sort_current[0] == "date" else sorted(self.filelist[parent_dir]['directories'], reverse=reverse)

        pos = dirs.index(directory)

        self.dir_panels[parent_dir].insert_row(pos)
        self.dir_panels[parent_dir].attach(self.directories[directory], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[parent_dir].show_all()

    def add_file(self, filepath, show=True):

        fileinfo = self._screen.files.get_file_info(filepath)
        if fileinfo is None:
            return

        d = f"gcodes/{filepath}".split('/')[:-1]
        directory = '/'.join(d)
        filename = filepath.split('/')[-1]
        if filename.startswith("."):
            return
        for i in range(1, len(d)):
            curdir = "/".join(d[:i])
            newdir = "/".join(d[:i + 1])
            if newdir not in self.filelist[curdir]['directories']:
                if d[i].startswith("."):
                    return
                self.add_directory(newdir)

        if filename not in self.filelist[directory]['files']:
            for i in range(1, len(d)):
                curdir = "/".join(d[:i + 1])
                if curdir != "gcodes" and fileinfo['modified'] > self.filelist[curdir]['modified']:
                    self.filelist[curdir]['modified'] = fileinfo['modified']
                    self.labels['directories'][curdir]['info'].set_markup(
                        '<small>' + _("Modified")
                        + f' <b>{datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %H:%M}</b></small>'
                    )

            self.filelist[directory]['files'].append(filename)

        if filepath not in self.files:
            self._create_frame_file(filename, filepath)
        reverse = self.sort_current[1] != 0
        files = sorted(
            self.filelist[directory]['files'],
            reverse=reverse,
            key=lambda item: self._screen.files.get_file_info(f"{directory}/{item}"[7:])['modified']
        ) if self.sort_current[0] == "date" else sorted(self.filelist[directory]['files'], reverse=reverse)

        pos = files.index(filename)
        pos += len(self.filelist[directory]['directories'])

        self.dir_panels[directory].insert_row(pos)
        self.dir_panels[directory].attach(self.files[filepath], 0, pos, 1, 1)
        if show is True:
            self.dir_panels[directory].show_all()

    def _create_frame(self, directory):
        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")

        name = Gtk.Label()
        name.set_markup(f"<big><b>{directory.split('/')[-1]}</b></big>")
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

        actions = self._gtk.ButtonImage("load", style="color3")
        actions.connect("clicked", self.change_dir, directory)
        actions.set_hexpand(False)
        actions.set_halign(Gtk.Align.END)

        file = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        file.set_hexpand(True)
        file.set_vexpand(False)

        icon = self._gtk.Image("folder")

        file.add(icon)
        file.add(labels)
        file.add(actions)
        frame.add(file)

        self.directories[directory] = frame

        self.labels['directories'][directory] = {
            "info": info,
            "name": name
        }

        self.dir_panels[directory] = Gtk.Grid()

    def _create_frame_file(self, filename, filepath):
        frame = Gtk.Frame()
        frame.get_style_context().add_class("frame-item")

        name = Gtk.Label()
        name.set_markup(f'<big><b>{os.path.splitext(filename)[0].replace("_", " ")}</b></big>')
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

        actions = self._gtk.ButtonImage("print", style="color3")
        actions.connect("clicked", self.confirm_print, filepath)
        actions.set_hexpand(False)
        actions.set_halign(Gtk.Align.END)

        file = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        file.set_hexpand(True)
        file.set_vexpand(False)

        icon = Gtk.Button()
        GLib.idle_add(self.image_load, filepath)
        icon.connect("clicked", self.confirm_delete_file, f"gcodes/{filepath}")

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

    def image_load(self, filepath):
        pixbuf = self.get_file_image(filepath, small=True)
        if pixbuf is not None:
            self.labels['files'][filepath]['icon'].set_image(Gtk.Image.new_from_pixbuf(pixbuf))
        else:
            self.labels['files'][filepath]['icon'].set_image(self._gtk.Image("file"))

    def confirm_delete_file(self, widget, filepath):
        logging.debug(f"Sending delete_file {filepath}")
        params = {"path": f"{filepath}"}
        self._screen._confirm_send_action(
            None,
            _("Delete File?") + "\n\n" + filepath,
            "server.files.delete_file",
            params
        )

    def back(self):
        if len(self.cur_directory.split('/')) > 1:
            self.change_dir(None, '/'.join(self.cur_directory.split('/')[:-1]))
            return True
        return False

    def change_dir(self, widget, directory):
        if directory not in self.dir_panels:
            return
        logging.debug(f"Changing dir to {directory}")

        for child in self.scroll.get_children():
            self.scroll.remove(child)
        self.cur_directory = directory
        self.labels['path'].set_text(f"  /{self.cur_directory[7:]}")

        self.scroll.add(self.dir_panels[directory])
        self.content.show_all()

    def change_sort(self, widget, key):
        if self.sort_current[0] == key:
            self.sort_current[1] = (self.sort_current[1] + 1) % 2
        else:
            oldkey = self.sort_current[0]
            logging.info(f"Changing sort_{oldkey} to {self.sort_items[self.sort_current[0]]}")
            self.labels[f'sort_{oldkey}'].set_image(None)
            self.labels[f'sort_{oldkey}'].show_all()
            self.sort_current = [key, 0]
        self.labels[f'sort_{key}'].set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]],
                                                             self._gtk.img_scale * .5))
        self.labels[f'sort_{key}'].show()
        GLib.idle_add(self.reload_files)

        self._config.set("main", "print_sort_dir", f'{key}_{"asc" if self.sort_current[1] == 0 else "desc"}')
        self._config.save_user_config_options()

    def confirm_print(self, widget, filename):

        buttons = [
            {"name": _("Print"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]

        label = Gtk.Label()
        label.set_markup(f"<b>{filename}</b>\n")
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_vexpand(True)
        label.set_valign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        grid = Gtk.Grid()
        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        grid.add(label)

        pixbuf = self.get_file_image(filename, self._screen.width * .9, self._screen.height * .6)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.set_vexpand(False)
            grid.attach_next_to(image, label, Gtk.PositionType.BOTTOM, 1, 1)

        self._gtk.Dialog(self._screen, buttons, grid, self.confirm_print_response, filename)

    def confirm_print_response(self, widget, response_id, filename):
        widget.destroy()

        if response_id == Gtk.ResponseType.CANCEL:
            return

        logging.info(f"Starting print: {filename}")
        self._screen._ws.klippy.print_start(filename)

    def delete_file(self, filename):
        dir_parts = f"gcodes/{filename}".split('/')[:-1]
        directory = '/'.join(dir_parts)
        if directory not in self.filelist or filename.split('/')[-1].startswith("."):
            return
        self.filelist[directory]["files"].pop(self.filelist[directory]["files"].index(filename.split('/')[-1]))
        i = len(dir_parts)
        while i > 1:
            cur_dir = '/'.join(dir_parts[:i])
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

        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo is None:
            return
        info = '<small>' + _("Uploaded") + f': <b>{datetime.fromtimestamp(fileinfo["modified"]):%Y-%m-%d %H:%M}</b>\n'

        if "size" in fileinfo:
            info += _("Size") + f': <b>{self.format_size(fileinfo["size"])}</b>\n'
        if "estimated_time" in fileinfo:
            info += _("Print Time") + f': <b>{self.format_time(fileinfo["estimated_time"])}</b>'
        info += "</small>"

        return info

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
            logging.debug(f"Cannot update file, file not in labels: {filename}")
            return

        logging.info(f"Updating file {filename}")
        self.labels['files'][filename]['info'].set_markup(self.get_file_info_str(filename))

        # Update icon
        GLib.idle_add(self.image_load, filename)

    def _callback(self, newfiles, deletedfiles, updatedfiles=None):
        logging.debug(f"newfiles: {newfiles}")
        for file in newfiles:
            self.add_file(file)
        logging.debug(f"deletedfiles: {deletedfiles}")
        for file in deletedfiles:
            self.delete_file(file)
        if updatedfiles is not None:
            logging.debug(f"updatefiles: {updatedfiles}")
            for file in updatedfiles:
                self.update_file(file)

    def _refresh_files(self, widget):
        self._files.refresh_files()

    def process_update(self, action, data):
        if action == "notify_gcode_response" and "unknown" in data.lower():
            self._screen.show_popup_message(data)
        return
