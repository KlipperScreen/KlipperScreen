# -*- coding: utf-8 -*-
import logging
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from datetime import datetime
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    cur_directory = "gcodes"
    dir_panels = {}
    filelist = {'gcodes': {'directories': [], 'files': []}}

    def __init__(self, screen, title):
        super().__init__(screen, title)
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
        self.files = {}
        self.directories = {}
        self.labels['directories'] = {}
        self.labels['files'] = {}
        self.source = ""
        self.time_24 = self._config.get_main_config().getboolean("24htime", True)
        self.space = '  ' if self._screen.width > 480 else '\n'
        logging.info(f"24h time is {self.time_24}")
        self.showing_rename = False

        sbox = Gtk.Box(hexpand=True, vexpand=False)
        for i, (name, val) in enumerate(self.sort_items.items(), start=1):
            s = self._gtk.Button(None, val, f"color{i % 4}", .5, Gtk.PositionType.RIGHT, 1)
            s.get_style_context().add_class("buttons_slim")
            if name == self.sort_current[0]:
                s.set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]], self._gtk.img_scale * self.bts))
            s.connect("clicked", self.change_sort, name)
            self.labels[f'sort_{name}'] = s
            sbox.add(s)
        self.refresh = self._gtk.Button("refresh", style="color4", scale=self.bts)
        self.refresh.get_style_context().add_class("buttons_slim")
        self.refresh.connect('clicked', self._refresh_files)
        sbox.add(self.refresh)

        self.labels['path'] = Gtk.Label(label=_('Loading...'), vexpand=True, no_show_all=True)
        self.labels['path'].show()

        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.main.add(sbox)
        self.main.add(self.labels['path'])

        self.dir_panels['gcodes'] = Gtk.Grid()
        self.show_loading()
        GLib.idle_add(self.load_files)
        self.scroll = self._gtk.ScrolledWindow()
        self.main.add(self.scroll)
        self.scroll.add(self.dir_panels['gcodes'])
        self._screen.files.add_file_callback(self._callback)
        self.content.add(self.main)

    def activate(self):
        if self.cur_directory != "gcodes":
            self.change_dir(None, "gcodes")
        self._refresh_files()

    def add_directory(self, directory):
        parent_dir = os.path.dirname(directory)
        modified = next(
            (
                x['modified']
                for x in self._files.directories
                if x['dirname'] == os.path.split(directory)[-1]
            ),
            0,
        )
        if directory not in self.filelist:
            self.filelist[directory] = {'directories': [], 'files': [], 'modified': modified}
            self.filelist[parent_dir]['directories'].append(directory)

        if directory not in self.labels['directories']:
            self._create_row(directory)
        reverse = self.sort_current[1] != 0
        dirs = sorted(
            self.filelist[parent_dir]['directories'],
            reverse=reverse, key=lambda item: self.filelist[item]['modified']
        ) if self.sort_current[0] == "date" else sorted(self.filelist[parent_dir]['directories'], reverse=reverse)

        pos = dirs.index(directory)

        self.dir_panels[parent_dir].insert_row(pos)
        self.dir_panels[parent_dir].attach(self.directories[directory], 0, pos, 1, 1)
        self.dir_panels[parent_dir].show_all()

    def add_file(self, filepath):
        fileinfo = self._screen.files.get_file_info(filepath)
        if fileinfo is None:
            return
        filename = os.path.basename(filepath)
        if filename.startswith("."):
            return
        directory = os.path.dirname(os.path.join("gcodes", filepath))
        d = directory.split(os.sep)
        for i in range(1, len(d)):
            curdir = os.path.join(*d[:i])
            newdir = os.path.join(*d[:i + 1])
            if newdir not in self.filelist[curdir]['directories']:
                if newdir.startswith("."):
                    return
                self.add_directory(newdir)

        if filename not in self.filelist[directory]['files']:
            for i in range(1, len(d)):
                curdir = os.path.join(*d[:i + 1])
                if self.time_24:
                    time = f":<b>{self.space}" \
                           f"{datetime.fromtimestamp(self.filelist[curdir]['modified']):%Y/%m/%d %H:%M}</b>"
                else:
                    time = f":<b>{self.space}" \
                           f"{datetime.fromtimestamp(self.filelist[curdir]['modified']):%Y/%m/%d %I:%M %p}</b>"
                info = _("Modified") + time
                info += "\n" + _("Size") + f':<b>{self.space}{self.format_size(fileinfo["size"])}</b>'
                self.labels['directories'][curdir]['info'].set_markup(info)
            self.filelist[directory]['files'].append(filename)

        if filepath not in self.files:
            self._create_row(filepath, filename)
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
        self.dir_panels[directory].show_all()

    def _create_row(self, fullpath, filename=None):
        name = Gtk.Label(hexpand=True, halign=Gtk.Align.START, wrap=True, wrap_mode=Pango.WrapMode.CHAR)
        name.get_style_context().add_class("print-filename")
        if filename:
            name.set_markup(f'<big><b>{os.path.splitext(filename)[0].replace("_", " ")}</b></big>')
        else:
            name.set_markup(f"<big><b>{os.path.split(fullpath)[-1]}</b></big>")

        info = Gtk.Label(hexpand=True, halign=Gtk.Align.START, wrap=True, wrap_mode=Pango.WrapMode.CHAR)
        info.get_style_context().add_class("print-info")

        delete = self._gtk.Button("delete", style="color1", scale=self.bts)
        delete.set_hexpand(False)
        rename = self._gtk.Button("files", style="color2", scale=self.bts)
        rename.set_hexpand(False)

        row = Gtk.Grid(hexpand=True, vexpand=False)
        row.get_style_context().add_class("frame-item")

        if filename:
            if os.path.splitext(filename)[1] in [".gcode", ".g", ".gco"]:
                action = self._gtk.Button("print", style="color3")
                action.connect("clicked", self.confirm_print, fullpath)
                action.set_hexpand(False)
                action.set_halign(Gtk.Align.END)
                row.attach(action, 4, 0, 1, 2)
            info.set_markup(self.get_file_info_str(fullpath))
            icon = Gtk.Button()
            icon.connect("clicked", self.confirm_print, fullpath)
            delete.connect("clicked", self.confirm_delete_file, f"gcodes/{fullpath}")
            rename.connect("clicked", self.show_rename, f"gcodes/{fullpath}")
            GLib.idle_add(self.image_load, fullpath)
            self.files[fullpath] = row
            self.labels['files'][fullpath] = {
                "icon": icon,
                "info": info,
                "name": name
            }
        else:
            action = self._gtk.Button("load", style="color3")
            action.connect("clicked", self.change_dir, fullpath)
            action.set_hexpand(False)
            action.set_halign(Gtk.Align.END)
            row.attach(action, 4, 0, 1, 2)
            icon = self._gtk.Button("folder")
            icon.connect("clicked", self.change_dir, fullpath)
            delete.connect("clicked", self.confirm_delete_directory, fullpath)
            rename.connect("clicked", self.show_rename, fullpath)
            self.directories[fullpath] = row
            self.labels['directories'][fullpath] = {
                "info": info,
                "name": name
            }
            self.dir_panels[fullpath] = Gtk.Grid()
        icon.set_hexpand(False)

        row.attach(icon, 0, 0, 1, 2)
        row.attach(name, 1, 0, 3, 1)
        row.attach(info, 1, 1, 1, 1)
        row.attach(rename, 2, 1, 1, 1)
        row.attach(delete, 3, 1, 1, 1)

    def image_load(self, filepath):
        pixbuf = self.get_file_image(filepath, small=True)
        if pixbuf is not None:
            self.labels['files'][filepath]['icon'].set_image(Gtk.Image.new_from_pixbuf(pixbuf))
        else:
            self.labels['files'][filepath]['icon'].set_image(self._gtk.Image("file"))
        return False

    def confirm_delete_file(self, widget, filepath):
        logging.debug(f"Sending delete_file {filepath}")
        params = {"path": f"{filepath}"}
        self._screen._confirm_send_action(
            None,
            _("Delete File?") + "\n\n" + filepath,
            "server.files.delete_file",
            params
        )

    def confirm_delete_directory(self, widget, dirpath):
        logging.debug(f"Sending delete_directory {dirpath}")
        params = {"path": f"{dirpath}", "force": True}
        self._screen._confirm_send_action(
            None,
            _("Delete Directory?") + "\n\n" + dirpath,
            "server.files.delete_directory",
            params
        )

    def back(self):
        if self.showing_rename:
            self.hide_rename()
            return True
        if os.path.dirname(self.cur_directory):
            self.change_dir(None, os.path.dirname(self.cur_directory))
            return True
        return False

    def change_dir(self, widget, directory):
        if directory not in self.dir_panels:
            return
        logging.debug(f"Changing dir to {directory}")

        for child in self.scroll.get_children():
            self.scroll.remove(child)
        self.cur_directory = directory

        self.scroll.add(self.dir_panels[directory])
        self.show_directory()
        self.content.show_all()

    def change_sort(self, widget, key):
        self.show_loading()
        if self.sort_current[0] == key:
            self.sort_current[1] = (self.sort_current[1] + 1) % 2
        else:
            oldkey = self.sort_current[0]
            logging.info(f"Changing from {oldkey} to {key}")
            self.labels[f'sort_{oldkey}'].set_image(None)
            self.labels[f'sort_{oldkey}'].show_all()
            self.sort_current = [key, 0]
        self.labels[f'sort_{key}'].set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]],
                                                             self._gtk.img_scale * self.bts))
        self.labels[f'sort_{key}'].show()
        GLib.idle_add(self.reload_files)

        self._config.set("main", "print_sort_dir", f'{key}_{"asc" if self.sort_current[1] == 0 else "desc"}')
        self._config.save_user_config_options()

    def confirm_print(self, widget, filename):

        buttons = [
            {"name": _("Print"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'}
        ]

        label = Gtk.Label(hexpand=True, vexpand=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        label.set_markup(f"<b>{filename}</b>\n")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(label)

        height = (self._screen.height - self._gtk.dialog_buttons_height - self._gtk.font_size) * .75
        pixbuf = self.get_file_image(filename, self._screen.width * .9, height)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            box.add(image)

        self._gtk.Dialog(_("Print") + f' {filename}', buttons, box, self.confirm_print_response, filename)

    def confirm_print_response(self, dialog, response_id, filename):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.info(f"Starting print: {filename}")
            self._screen._ws.klippy.print_start(filename)

    def delete_file(self, filename):
        directory = os.path.join("gcodes", os.path.dirname(filename)) if os.path.dirname(filename) else "gcodes"
        if directory not in self.filelist or os.path.basename(filename).startswith("."):
            return
        try:
            self.filelist[directory]["files"].pop(self.filelist[directory]["files"].index(os.path.basename(filename)))
        except Exception as e:
            logging.exception(e)
        dir_parts = directory.split(os.sep)
        i = len(dir_parts)
        while i > 1:
            cur_dir = os.path.join(*dir_parts[:i])
            if len(self.filelist[cur_dir]['directories']) > 0 or len(self.filelist[cur_dir]['files']) > 0:
                break
            parent_dir = os.path.dirname(cur_dir)

            if self.cur_directory == cur_dir:
                self.change_dir(None, parent_dir)

            del self.filelist[cur_dir]
            self.filelist[parent_dir]['directories'].pop(self.filelist[parent_dir]['directories'].index(cur_dir))
            self.dir_panels[parent_dir].remove(self.directories[cur_dir])
            del self.directories[cur_dir]
            del self.labels['directories'][cur_dir]
            self.dir_panels[parent_dir].show_all()
            i -= 1

        try:
            self.dir_panels[directory].remove(self.files[filename])
        except Exception as e:
            logging.exception(e)
        self.dir_panels[directory].show_all()
        self.files.pop(filename)

    def get_file_info_str(self, filename):

        fileinfo = self._screen.files.get_file_info(filename)
        if fileinfo is None:
            return
        info = _("Uploaded")
        if self.time_24:
            info += f':<b>{self.space}{datetime.fromtimestamp(fileinfo["modified"]):%Y/%m/%d %H:%M}</b>\n'
        else:
            info += f':<b>{self.space}{datetime.fromtimestamp(fileinfo["modified"]):%Y/%m/%d %I:%M %p}</b>\n'

        if "size" in fileinfo:
            info += _("Size") + f':{self.space}<b>{self.format_size(fileinfo["size"])}</b>\n'
        if "estimated_time" in fileinfo:
            info += _("Print Time") + f':{self.space}<b>{self.format_time(fileinfo["estimated_time"])}</b>'
        return info

    def reload_files(self, widget=None):
        self.filelist = {'gcodes': {'directories': [], 'files': []}}
        for dirpan in self.dir_panels:
            for column in range(3):
                self.dir_panels[dirpan].remove_column(column)
        self.load_files()

    def load_files(self):
        flist = sorted(self._screen.files.get_file_list(), key=lambda item: '/' in item)
        for file in flist:
            self.add_file(file)
        self.show_directory()

    def update_file(self, filename):
        if filename not in self.labels['files']:
            logging.debug(f"Cannot update file, file not in labels: {filename}")
            return

        self.labels['files'][filename]['info'].set_markup(self.get_file_info_str(filename))

        # Update icon
        GLib.idle_add(self.image_load, filename)

    def _callback(self, newfiles, deletedfiles, modifiedfiles):
        for file in newfiles:
            logging.info(f"adding {file}")
            self.add_file(file)
        for file in deletedfiles:
            logging.info(f"deleting {file}")
            self.delete_file(file)
        for file in modifiedfiles:
            logging.info(f"updating {file}")
            self.update_file(file)
        self._gtk.Button_busy(self.refresh, False)

    def _refresh_files(self, widget=None):
        self._gtk.Button_busy(self.refresh, True)
        self._files.refresh_files()

    def show_directory(self):
        self._gtk.Button_busy(self.refresh, False)
        self.labels['path'].set_vexpand(False)
        if self.cur_directory == 'gcodes':
            self.labels['path'].hide()
        else:
            self.labels['path'].set_text(self.cur_directory)
            self.labels['path'].show()

    def show_loading(self):
        self.labels['path'].set_text(_('Loading...'))
        self.labels['path'].show()
        self._gtk.Button_busy(self.refresh, True)

    def show_rename(self, widget, fullpath):
        self.source = fullpath
        logging.info(self.source)

        for child in self.content.get_children():
            self.content.remove(child)

        if "rename_file" not in self.labels:
            self._create_rename_box(fullpath)
        self.content.add(self.labels['rename_file'])
        self.labels['new_name'].set_text(fullpath[7:])
        self.labels['new_name'].grab_focus_without_selecting()
        self.showing_rename = True

    def _create_rename_box(self, fullpath):
        lbl = Gtk.Label(label=_("Rename/Move:"), halign=Gtk.Align.START, hexpand=False)
        self.labels['new_name'] = Gtk.Entry(text=fullpath, hexpand=True)
        self.labels['new_name'].connect("activate", self.rename)
        self.labels['new_name'].connect("focus-in-event", self._screen.show_keyboard)

        save = self._gtk.Button("complete", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.rename)

        box = Gtk.Box()
        box.pack_start(self.labels['new_name'], True, True, 5)
        box.pack_start(save, False, False, 5)

        self.labels['rename_file'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5,
                                             hexpand=True, vexpand=True, valign=Gtk.Align.CENTER)
        self.labels['rename_file'].pack_start(lbl, True, True, 5)
        self.labels['rename_file'].pack_start(box, True, True, 5)

    def hide_rename(self):
        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.main)
        self.content.show()
        self.showing_rename = False

    def rename(self, widget):
        params = {"source": self.source, "dest": f"gcodes/{self.labels['new_name'].get_text()}"}
        self._screen._send_action(
            widget,
            "server.files.move",
            params
        )
        self.back()
        GLib.timeout_add_seconds(2, self._refresh_files)
