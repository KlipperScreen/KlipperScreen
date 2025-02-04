import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from datetime import datetime
from ks_includes.screen_panel import ScreenPanel
from ks_includes.KlippyGtk import find_widget
from ks_includes.widgets.flowboxchild_extended import PrintListItem


def format_label(widget):
    label = find_widget(widget, Gtk.Label)
    if label is not None:
        label.set_line_wrap_mode(Pango.WrapMode.CHAR)
        label.set_line_wrap(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_lines(3)


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or (_("Print") if self._printer.extrudercount > 0 else _("Gcodes"))
        super().__init__(screen, title)
        sortdir = self._config.get_main_config().get("print_sort_dir", "name_asc")
        sortdir = sortdir.split('_')
        self.sort_items = {
            "name": _("Name"),
            "date": _("Date"),
            "size": _("Size"),
        }
        if sortdir[0] not in self.sort_items or sortdir[1] not in ["asc", "desc"]:
            sortdir = ["name", "asc"]
        self.sort_current = [sortdir[0], 0 if sortdir[1] == "asc" else 1]  # 0 for asc, 1 for desc
        self.sort_icon = ["arrow-up", "arrow-down"]
        self.source = ""
        self.time_24 = self._config.get_main_config().getboolean("24htime", True)
        self.showing_rename = False
        self.loading = False
        self.cur_directory = 'gcodes'
        self.list_button_size = self._gtk.img_scale * self.bts

        self.headerbox = Gtk.Box(hexpand=True, vexpand=False)
        n = 0
        for name, val in self.sort_items.items():
            s = self._gtk.Button(None, val, f"color{n % 4 + 1}", .5, Gtk.PositionType.RIGHT, 1)
            s.get_style_context().add_class("buttons_slim")
            if name == self.sort_current[0]:
                s.set_image(self._gtk.Image(self.sort_icon[self.sort_current[1]], self._gtk.img_scale * self.bts))
            s.connect("clicked", self.change_sort, name)
            self.labels[f'sort_{name}'] = s
            self.headerbox.add(s)
            n += 1

        self.refresh = self._gtk.Button("refresh", style=f"color{n % 4 + 1}", scale=self.bts)
        self.refresh.get_style_context().add_class("buttons_slim")
        self.refresh.connect('clicked', self._refresh_files)
        n += 1
        self.headerbox.add(self.refresh)

        self.switch_mode = self._gtk.Button("fine-tune", style=f"color{n % 4 + 1}", scale=self.bts)
        self.switch_mode.get_style_context().add_class("buttons_slim")
        self.switch_mode.connect('clicked', self.switch_view_mode)
        n += 1
        self.headerbox.add(self.switch_mode)

        self.loading_msg = _('Loading...')
        self.labels['path'] = Gtk.Label(label=self.loading_msg, vexpand=True, no_show_all=True)
        self.labels['path'].show()
        self.thumbsize = self._gtk.img_scale * self._gtk.button_image_scale * 2.5
        logging.info(f"Thumbsize: {self.thumbsize:.1f}")

        self.flowbox = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                   column_spacing=0, row_spacing=0)
        list_mode = self._config.get_main_config().get("print_view", 'thumbs')
        logging.info(list_mode)
        self.list_mode = list_mode == 'list'
        if self.list_mode:
            self.flowbox.set_min_children_per_line(1)
            self.flowbox.set_max_children_per_line(1)
        else:
            columns = 3 if self._screen.vertical_mode else 4
            self.flowbox.set_min_children_per_line(columns)
            self.flowbox.set_max_children_per_line(columns)

        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.add(self.flowbox)

        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.main.add(self.headerbox)
        self.main.add(self.labels['path'])
        self.main.add(self.scroll)
        self.content.add(self.main)
        self.set_loading(True)
        self._screen._ws.klippy.get_dir_info(self.load_files, self.cur_directory)

    def switch_view_mode(self, widget):
        self.list_mode ^= True
        logging.info(f"lista {self.list_mode}")
        if self.list_mode:
            self.flowbox.set_min_children_per_line(1)
            self.flowbox.set_max_children_per_line(1)
        else:
            columns = 3 if self._screen.vertical_mode else 4
            self.flowbox.set_min_children_per_line(columns)
            self.flowbox.set_max_children_per_line(columns)
        self._config.set("main", "print_view", 'list' if self.list_mode else 'thumbs')
        self._config.save_user_config_options()
        self._refresh_files()

    def activate(self):
        if self.cur_directory != "gcodes":
            self.change_dir()
        self._screen.files.add_callback(self._callback)

    def deactivate(self):
        self._screen.files.remove_callback(self._callback)

    def create_item(self, item):
        fbchild = PrintListItem()
        fbchild.set_date(item['modified'])
        fbchild.set_size(item['size'])
        if 'dirname' in item:
            if item['dirname'].startswith("."):
                return
            name = item['dirname']
            path = f"{self.cur_directory}/{name}"
            fbchild.set_as_dir(True)
        elif 'filename' in item:
            if (item['filename'].startswith(".") or
                    os.path.splitext(item['filename'])[1] not in {'.gcode', '.gco', '.g'}):
                return
            name = item['filename']
            path = f"{self.cur_directory}/{name}"
            path = path.replace('gcodes/', '')
        else:
            logging.error(f"Unknown item {item}")
            return
        basename = os.path.splitext(name)[0]
        fbchild.set_path(path)
        fbchild.set_name(basename.casefold())
        if self.list_mode:
            label = Gtk.Label(label=basename, hexpand=True, vexpand=False)
            format_label(label)
            info = Gtk.Label(
                hexpand=True, halign=Gtk.Align.START, xalign=0,
                wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
            )
            info.get_style_context().add_class("print-info")
            info.set_markup(self.get_info_str(item, path))
            delete = Gtk.Button(hexpand=False, vexpand=False, can_focus=False, always_show_image=True)
            delete.get_style_context().add_class("color1")
            delete.set_image(self._gtk.Image("delete", self.list_button_size, self.list_button_size))
            rename = Gtk.Button(hexpand=False, vexpand=False, can_focus=False, always_show_image=True)
            rename.get_style_context().add_class("color2")
            rename.set_image(self._gtk.Image("files", self.list_button_size, self.list_button_size))
            itemname = Gtk.Label(hexpand=True, halign=Gtk.Align.START, ellipsize=Pango.EllipsizeMode.END)
            itemname.get_style_context().add_class("print-filename")
            itemname.set_markup(f"<big><b>{basename}</b></big>")
            icon = Gtk.Button()
            row = Gtk.Grid(hexpand=True, vexpand=False, valign=Gtk.Align.CENTER)
            row.get_style_context().add_class("frame-item")
            if self._screen.width >= 400:
                row.attach(icon, 0, 0, 1, 2)
            row.attach(itemname, 1, 0, 3, 1)
            row.attach(info, 1, 1, 1, 1)
            row.attach(rename, 2, 1, 1, 1)
            row.attach(delete, 3, 1, 1, 1)
            if 'filename' in item:
                icon.connect("clicked", self.confirm_print, path)
                image_args = (path, icon, self.thumbsize / 2, True, "file")
                delete.connect("clicked", self.confirm_delete_file, f"gcodes/{path}")
                rename.connect("clicked", self.show_rename, f"gcodes/{path}")
                action_icon = "printer" if self._printer.extrudercount > 0 else "load"
                action = self._gtk.Button(action_icon, style="color3")
                action.connect("clicked", self.confirm_print, path)
                action.set_hexpand(False)
                action.set_vexpand(False)
                action.set_halign(Gtk.Align.END)
                if self._screen.width >= 400:
                    row.attach(action, 4, 0, 1, 2)
                else:
                    icon.get_style_context().add_class("color3")
                    row.attach(icon, 4, 0, 1, 2)
            elif 'dirname' in item:
                icon.connect("clicked", self.change_dir, path)
                image_args = (None, icon, self.thumbsize / 2, True, "folder")
                delete.connect("clicked", self.confirm_delete_directory, path)
                rename.connect("clicked", self.show_rename, path)
                action = self._gtk.Button("load", style="color3")
                action.connect("clicked", self.change_dir, path)
                action.set_hexpand(False)
                action.set_vexpand(False)
                action.set_halign(Gtk.Align.END)
                row.attach(action, 4, 0, 1, 2)
            else:
                return
            fbchild.add(row)
        else:  # Thumbnail view
            icon = self._gtk.Button(label=basename)
            if 'filename' in item:
                icon.connect("clicked", self.confirm_print, path)
                image_args = (path, icon, self.thumbsize, False, "file")
            elif 'dirname' in item:
                icon.connect("clicked", self.change_dir, path)
                image_args = (None, icon, self.thumbsize, False, "folder")
            else:
                return
            fbchild.add(icon)
        self.image_load(*image_args)
        return fbchild

    def show_path(self):
        self.labels['path'].set_vexpand(False)
        if self.cur_directory == 'gcodes':
            self.labels['path'].hide()
        else:
            self.labels['path'].set_text(self.cur_directory)
            self.labels['path'].show()

    def image_load(self, filepath, widget, size=-1, small=True, iconname=None):
        pixbuf = self.get_file_image(filepath, size, size, small)
        if pixbuf is not None:
            widget.set_image(Gtk.Image.new_from_pixbuf(pixbuf))
        elif iconname is not None:
            widget.set_image(self._gtk.Image(iconname, size, size))
        format_label(widget)

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
        if self.cur_directory != 'gcodes':
            self.change_dir(None, os.path.dirname(self.cur_directory))
            return True
        return False

    def change_dir(self, widget=None, directory='gcodes'):
        if directory == '':
            directory = 'gcodes'
        if directory != self.cur_directory:
            logging.info(f'Changing directory to: {directory}')
            self.cur_directory = directory
        self.show_path()
        self._refresh_files()

    def change_sort(self, widget, key):
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

        self.set_sort()

        self._config.set("main", "print_sort_dir", f'{key}_{"asc" if self.sort_current[1] == 0 else "desc"}')
        self._config.save_user_config_options()

    def set_sort(self):
        reverse = self.sort_current[1] != 0
        if self.sort_current[0] == "name":
            self.flowbox.set_sort_func(self.sort_names, reverse)
        elif self.sort_current[0] == "date":
            self.flowbox.set_sort_func(self.sort_dates, reverse)
        elif self.sort_current[0] == "size":
            self.flowbox.set_sort_func(self.sort_sizes, reverse)

    @staticmethod
    def sort_names(a: PrintListItem, b: PrintListItem, reverse):
        if a.get_is_dir() - b.get_is_dir() != 0:
            return a.get_is_dir() - b.get_is_dir()
        if a.get_name() < b.get_name():
            return 1 if reverse else -1
        if a.get_name() > b.get_name():
            return -1 if reverse else 1
        return 0

    @staticmethod
    def sort_sizes(a: PrintListItem, b: PrintListItem, reverse):
        if a.get_is_dir() - b.get_is_dir() != 0:
            return a.get_is_dir() - b.get_is_dir()
        return b.get_size() - a.get_size() if reverse else a.get_size() - b.get_size()

    @staticmethod
    def sort_dates(a: PrintListItem, b: PrintListItem, reverse):
        if a.get_is_dir() - b.get_is_dir() != 0:
            return a.get_is_dir() - b.get_is_dir()
        return b.get_date() - a.get_date() if reverse else a.get_date() - b.get_date()

    def confirm_print(self, widget, filename):
        action = _("Print") if self._printer.extrudercount > 0 else _("Start")

        buttons = [
            {"name": _("Delete"), "response": Gtk.ResponseType.REJECT, "style": 'dialog-error'},
            {"name": action, "response": Gtk.ResponseType.OK, "style": 'dialog-primary'},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-secondary'}
        ]

        label = Gtk.Label(
            hexpand=True, vexpand=True, lines=2,
            wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
            ellipsize=Pango.EllipsizeMode.END
        )
        label.set_markup(f"<b>{filename}</b>")

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        main_box.pack_start(label, False, False, 0)

        orientation = Gtk.Orientation.VERTICAL if self._screen.vertical_mode else Gtk.Orientation.HORIZONTAL
        inside_box = Gtk.Box(orientation=orientation, vexpand=True)

        if self._screen.vertical_mode:
            width = self._screen.width * .9
            height = (self._screen.height - self._gtk.dialog_buttons_height - self._gtk.font_size * 5) * .45
        else:
            width = self._screen.width * .5
            height = (self._screen.height - self._gtk.dialog_buttons_height - self._gtk.font_size * 6)
        pixbuf = self.get_file_image(filename, width, height)
        if pixbuf is not None:
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image_button = self._gtk.Button()
            image_button.set_image(image)
            image_button.connect("clicked", self.show_fullscreen_thumbnail, filename)
            inside_box.pack_start(image_button, True, True, 0)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        fileinfo = Gtk.Label(
            label=self.get_file_info_extended(filename), use_markup=True, ellipsize=Pango.EllipsizeMode.END
        )
        info_box.pack_start(fileinfo, True, True, 0)

        inside_box.pack_start(info_box, True, True, 0)
        main_box.pack_start(inside_box, True, True, 0)
        self._gtk.Dialog(f'{action} {filename}', buttons, main_box, self.confirm_print_response, filename)

    def confirm_print_response(self, dialog, response_id, filename):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        elif response_id == Gtk.ResponseType.OK:
            logging.info(f"Starting print: {filename}")
            self._screen._ws.klippy.print_start(filename)
        elif response_id == Gtk.ResponseType.REJECT:
            self.confirm_delete_file(None, f"gcodes/{filename}")

    def get_info_str(self, item, path):
        info = ""
        if "modified" in item:
            info += _("Modified")
            if self.time_24:
                info += f':<b> {datetime.fromtimestamp(item["modified"]):%Y/%m/%d %H:%M}</b>\n'
            else:
                info += f':<b> {datetime.fromtimestamp(item["modified"]):%Y/%m/%d %I:%M %p}</b>\n'
        if "size" in item:
            info += _("Size") + f': <b>{self.format_size(item["size"])}</b>\n'
        if 'filename' in item:
            info += self.get_file_info(path)
        return info

    def get_file_info(self, path):
        info = ""
        fileinfo = self._screen.files.get_file_info(path)
        if "layer_height" in fileinfo:
            info += _("Layer Height") + f': <b>{fileinfo["layer_height"]}</b> ' + _("mm") + '\n'
        if "filament_type" in fileinfo:
            info += _("Filament") + f': <b>{fileinfo["filament_type"]}</b>\n'
        if "filament_name" in fileinfo:
            info += f'<b>{fileinfo["filament_name"]}</b>\n'
        if "estimated_time" in fileinfo:
            info += _("Estimated Time") + f': <b>{self.format_time(fileinfo["estimated_time"])}</b>'
        return info

    def get_file_info_extended(self, filename):
        fileinfo = self._screen.files.get_file_info(filename)
        info = ""
        if "modified" in fileinfo:
            info += _("Modified")
            if self.time_24:
                info += f':<b> {datetime.fromtimestamp(fileinfo["modified"]):%Y/%m/%d %H:%M}</b>\n'
            else:
                info += f':<b> {datetime.fromtimestamp(fileinfo["modified"]):%Y/%m/%d %I:%M %p}</b>\n'
        if "layer_height" in fileinfo:
            info += _("Layer Height") + f': <b>{fileinfo["layer_height"]}</b> ' + _("mm") + '\n'
        if "filament_type" in fileinfo or "filament_name" in fileinfo:
            info += _("Filament") + ':\n'
        if "filament_type" in fileinfo:
            info += f'    <b>{fileinfo["filament_type"]}</b>\n'
        if "filament_name" in fileinfo:
            info += f'    <b>{fileinfo["filament_name"]}</b>\n'
        if "filament_weight_total" in fileinfo:
            info += f'    <b>{fileinfo["filament_weight_total"]:.2f}</b> ' + _("g") + '\n'
        if "nozzle_diameter" in fileinfo:
            info += _("Nozzle diameter") + f': <b>{fileinfo["nozzle_diameter"]}</b> ' + _("mm") + '\n'
        if "slicer" in fileinfo:
            info += (
                _("Slicer") +
                f': <b>{fileinfo["slicer"]} '
                f'{fileinfo["slicer_version"] if "slicer_version" in fileinfo else ""}</b>\n'
            )
        if "size" in fileinfo:
            info += _("Size") + f': <b>{self.format_size(fileinfo["size"])}</b>\n'
        if "estimated_time" in fileinfo:
            info += _("Estimated Time") + f': <b>{self.format_time(fileinfo["estimated_time"])}</b>\n'
        if "job_id" in fileinfo:
            history = self._screen.apiclient.send_request(f"server/history/job?uid={fileinfo['job_id']}")
            if history and history['job']['status'] == "completed":
                info += _("Last Duration") + f": <b>{self.format_time(history['job']['print_duration'])}</b>"
        return info

    def load_files(self, result, method, params):
        start = datetime.now()
        self.set_loading(True)
        if not result.get("result") or not isinstance(result["result"], dict):
            logging.info(result)
            return
        items = [self.create_item(item) for item in [*result["result"]["dirs"], *result["result"]["files"]]]
        for item in filter(None, items):
            self.flowbox.add(item)
        self.set_sort()
        self.set_loading(False)
        logging.info(f"Loaded in {(datetime.now() - start).total_seconds():.3f} seconds")

    def delete_from_list(self, path):
        logging.info(f"deleting {path}")
        for item in self.flowbox.get_children():
            if item.get_path() in {path, f"gcodes/{path}"}:
                logging.info("found removing")
                self.flowbox.remove(item)
                return True

    def add_item_from_callback(self, action, data):
        item = data['item']
        if 'source_item' in data:
            self.delete_from_list(data['source_item']['path'])
        else:
            self.delete_from_list(item['path'])
        path = os.path.join("gcodes", item["path"])
        if self.cur_directory != os.path.dirname(path):
            return
        if action in {"create_dir", "move_dir"}:
            item.update({"path": path, "dirname": os.path.split(item["path"])[1]})
        else:
            item.update({"path": path, "filename": os.path.split(item["path"])[1]})
        fbchild = self.create_item(item)
        if fbchild:
            self.flowbox.add(fbchild)
            self.flowbox.invalidate_sort()
            self.flowbox.show_all()

    def _callback(self, action, data):
        logging.info(f"{action}: {data}")
        if action in {"create_dir", "create_file"}:
            self.add_item_from_callback(action, data)
        elif action == "delete_file":
            self.delete_from_list(data['item']["path"])
        elif action == "delete_dir":
            self.delete_from_list(os.path.join("gcodes", data['item']["path"]))
        elif action in {"modify_file", "move_file", "move_dir"}:
            if "path" in data['item'] and data['item']["path"].startswith("gcodes/"):
                data['item']["path"] = data['item']["path"][7:]
            self.add_item_from_callback(action, data)

    def _refresh_files(self, *args):
        logging.info("Refreshing")
        self.set_loading(True)
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)
        self._screen._ws.klippy.get_dir_info(self.load_files, self.cur_directory)

    def set_loading(self, loading):
        self.loading = loading
        for child in self.headerbox.get_children():
            child.set_sensitive(not loading)
        self._gtk.Button_busy(self.refresh, loading)
        if loading:
            self.labels['path'].set_text(self.loading_msg)
            self.labels['path'].show()
            return
        self.show_path()
        self.content.show_all()

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

    def show_fullscreen_thumbnail(self, widget, filename):
        pixbuf = self.get_file_image(filename, self._screen.width * .9, self._screen.height * .75)
        if pixbuf is None:
            return
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        image.set_vexpand(True)
        self._gtk.Dialog(filename, None, image, self.close_fullscreen_thumbnail)

    def close_fullscreen_thumbnail(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
