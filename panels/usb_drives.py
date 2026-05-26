import base64
import logging
import os
import shutil
import subprocess
import threading
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, Gio, GLib, Gtk, Pango
from ks_includes.screen_panel import ScreenPanel

_MODE_MAIN = "main"
_MODE_DRIVE_SELECT = "drive_select"
_MODE_EJECT = "eject"
_MODE_FILES = "files"


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("USB Drives")
        super().__init__(screen, title)

        self._mode = _MODE_MAIN
        self._direction = None       # "from" (USB→printer) or "to" (printer→USB)
        self._available_drives = []  # [(name, path, mount), ...]
        self._usb_dest = None        # selected USB mount path

        self._vol_monitor = Gio.VolumeMonitor.get()
        self._mount_sigs = [
            self._vol_monitor.connect("mount-added", lambda *a: GLib.idle_add(self._on_mount_change)),
            self._vol_monitor.connect("mount-removed", lambda *a: GLib.idle_add(self._on_mount_change)),
        ]

        self._scroll = self._gtk.ScrolledWindow()
        self._file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._scroll.add(self._file_box)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.pack_start(self._scroll, True, True, 0)
        self.content.add(main_box)

        self._show_main()

    #  USB Drive Detection

    def _on_mount_change(self):
        if self._mode == _MODE_DRIVE_SELECT:
            self._show_drive_select()
        elif self._mode == _MODE_EJECT:
            self._show_eject_screen()

    def _usb_mounts(self):
        mounts = []
        for mount in self._vol_monitor.get_mounts():
            vol = mount.get_volume()
            if vol is None:
                continue
            drv = vol.get_drive()
            if drv is None or not drv.is_removable():
                continue
            root = mount.get_root()
            if root is None:
                continue
            path = root.get_path()
            if path is None:
                continue
            mounts.append((mount.get_name() or os.path.basename(path) or _("USB Drive"), path, mount))
        if not mounts:
            user = os.environ.get("USER") or os.environ.get("LOGNAME") or "pi"
            for base in (f"/media/{user}", f"/run/media/{user}"):
                if os.path.isdir(base):
                    for name in sorted(os.listdir(base)):
                        full = os.path.join(base, name)
                        if os.path.ismount(full):
                            mounts.append((name, full, None))
        return mounts

    #  Main Menu

    def _show_main(self):
        self._mode = _MODE_MAIN
        self._direction = None
        self._clear_file_box()

        from_btn = self._make_dir_button(
            "usb-pen-drive-icon", "arrow-right", "sd",
            _("Copy From USB"), "color1",
        )
        from_btn.connect("clicked", self._on_copy_from)

        to_btn = self._make_dir_button(
            "sd", "arrow-right", "usb-pen-drive-icon",
            _("Copy To USB"), "color3",
        )
        to_btn.connect("clicked", self._on_copy_to)

        eject_btn = self._gtk.Button("arrow-up", _("Eject USB Drive"), "color2", scale=self.bts)
        eject_btn.set_vexpand(True)
        eject_btn.connect("clicked", self._on_eject_from_main)

        self._file_box.pack_start(from_btn, True, True, 5)
        self._file_box.pack_start(to_btn, True, True, 5)
        self._file_box.pack_start(eject_btn, True, True, 5)
        self._file_box.show_all()

    def _make_dir_button(self, src_icon, arrow_icon, dst_icon, label_text, style):
        sz = self._gtk.img_scale * self.bts * 1.5
        icon_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        icon_box.set_halign(Gtk.Align.CENTER)
        for name in (src_icon, arrow_icon, dst_icon):
            icon_box.pack_start(self._gtk.Image(name, sz, sz), False, False, 2)

        lbl = Gtk.Label(label=label_text)
        lbl.get_style_context().add_class("button_label")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vbox.set_valign(Gtk.Align.CENTER)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(icon_box, False, False, 0)
        vbox.pack_start(lbl, False, False, 0)

        btn = Gtk.Button(hexpand=True, vexpand=True)
        btn.get_style_context().add_class(style)
        btn.add(vbox)
        return btn

    #  Safety Logic

    def _on_copy_from(self, *_args):
        self._direction = "from"
        self._enter_with_drive_check()

    def _on_copy_to(self, *_args):
        self._direction = "to"
        src = self._dest_path()
        if not src:
            self._screen.show_popup_message(_("Printer storage path is not configured"), level=2)
            return
        if not os.path.isdir(src):
            self._screen.show_popup_message(_("Printer storage path not found:\n") + src, level=2)
            return
        self._enter_with_drive_check()

    def _enter_with_drive_check(self):
        drives = self._usb_mounts()
        if not drives:
            self._screen.show_popup_message(_("No USB drives detected"), level=2)
            return
        self._available_drives = drives
        if len(drives) == 1:
            self._usb_dest = drives[0][1]
            self._show_files()
        else:
            self._show_drive_select()

    def _on_eject_from_main(self, *_args):
        drives = self._usb_mounts()
        if not drives:
            self._screen.show_popup_message(_("No USB drives detected"), level=2)
            return
        if len(drives) == 1:
            name, path, mount = drives[0]
            self._confirm_eject(path, mount, name)
        else:
            self._show_eject_screen()

    #  Drive Picker

    def _show_drive_select(self):
        self._mode = _MODE_DRIVE_SELECT
        self._clear_file_box()
        drives = self._usb_mounts()
        self._available_drives = drives
        if not drives:
            lbl = Gtk.Label(label=_("No USB drives detected"),
                            vexpand=True, valign=Gtk.Align.CENTER)
            self._file_box.add(lbl)
        else:
            for name, path, mount in drives:
                self._add_drive_row(name, path, mount)
        self._file_box.show_all()

    def _add_drive_row(self, name, path, mount):
        sz = self._gtk.img_scale * self.bts
        img = self._gtk.Image("usb-pen-drive-icon", sz, sz)
        name_lbl = Gtk.Label(label=name, xalign=0, hexpand=True,
                             ellipsize=Pango.EllipsizeMode.END)

        inner = Gtk.Box(spacing=5)
        inner.get_style_context().add_class("frame-item")
        inner.pack_start(img, False, False, 3)
        inner.pack_start(name_lbl, True, True, 0)

        evbox = Gtk.EventBox()
        evbox.set_above_child(True)
        evbox.add(inner)
        evbox.connect("button-release-event", self._on_drive_selected, path)

        eject_btn = self._gtk.Button("arrow-up", _("Eject"), "color3", scale=self.bts)
        eject_btn.connect("clicked", lambda *_: self._confirm_eject(path, mount, name))

        outer = Gtk.Box(spacing=2)
        outer.pack_start(evbox, True, True, 0)
        outer.pack_end(eject_btn, False, False, 0)
        self._file_box.add(outer)

    def _show_eject_screen(self):
        self._mode = _MODE_EJECT
        self._clear_file_box()
        drives = self._usb_mounts()
        if not drives:
            lbl = Gtk.Label(label=_("No USB drives detected"),
                            vexpand=True, valign=Gtk.Align.CENTER)
            self._file_box.add(lbl)
        else:
            for name, path, mount in drives:
                self._add_eject_row(name, path, mount)
        self._file_box.show_all()

    def _add_eject_row(self, name, path, mount):
        sz = self._gtk.img_scale * self.bts
        img = self._gtk.Image("usb-pen-drive-icon", sz, sz)
        name_lbl = Gtk.Label(label=name, xalign=0, hexpand=True,
                             ellipsize=Pango.EllipsizeMode.END)

        row = Gtk.Box(spacing=5)
        row.get_style_context().add_class("frame-item")
        row.pack_start(img, False, False, 3)
        row.pack_start(name_lbl, True, True, 0)

        eject_btn = self._gtk.Button("arrow-up", _("Eject"), "color2", scale=self.bts)
        eject_btn.connect("clicked", lambda *_: self._confirm_eject(path, mount, name))

        outer = Gtk.Box(spacing=2)
        outer.pack_start(row, True, True, 0)
        outer.pack_end(eject_btn, False, False, 0)
        self._file_box.add(outer)

    def _on_drive_selected(self, _evbox, event, path):
        if event.button != 1:
            return True
        self._usb_dest = path
        self._show_files()
        return True

    #  List Files

    def _dest_path(self):
        if self._files and self._files.gcodes_path:
            return self._files.gcodes_path
        if self._printer:
            section = self._printer.get_config_section("virtual_sdcard")
            if section and "path" in section:
                return os.path.expanduser(section["path"])
        return None

    def _show_files(self):
        self._mode = _MODE_FILES
        self._clear_file_box()

        scan_path = self._usb_dest if self._direction == "from" else self._dest_path()

        try:
            entries = sorted(
                (e for e in os.scandir(scan_path) if e.is_file(follow_symlinks=False)),
                key=lambda e: e.name.lower(),
            )
        except OSError as exc:
            self._screen.show_popup_message(str(exc), level=2)
            return

        if not entries:
            lbl = Gtk.Label(label=_("No files found"),
                            vexpand=True, valign=Gtk.Align.CENTER)
            self._file_box.add(lbl)
            self._file_box.show_all()
            return

        for entry in entries:
            self._add_file_row(entry.name, entry.path)
        self._file_box.show_all()

    def _add_file_row(self, name, path):
        sz = self._gtk.img_scale * self.bts
        img = self._gtk.Image("file", sz, sz)
        name_lbl = Gtk.Label(label=name, xalign=0, hexpand=True,
                             ellipsize=Pango.EllipsizeMode.END)

        row = Gtk.Box(spacing=5)
        row.get_style_context().add_class("frame-item")
        row.pack_start(img, False, False, 3)
        row.pack_start(name_lbl, True, True, 0)

        evbox = Gtk.EventBox()
        evbox.add(row)
        evbox.ks_path = path
        evbox.connect("button-release-event", self._on_file_tap)

        self._file_box.add(evbox)

    def _on_file_tap(self, evbox, event):
        if event.button != 1:
            return True
        self._show_confirm_dialog([evbox.ks_path])
        return True

    #  Disk Eject / UnMount

    def _confirm_eject(self, path, mount, name=""):
        label = name or os.path.basename(path) or _("USB Drive")
        content = Gtk.Label(label=label, hexpand=True, vexpand=True,
                            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        buttons = [
            {"name": _("Eject"), "response": Gtk.ResponseType.OK, "style": "color1"},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": "color2"},
        ]
        self._gtk.Dialog(
            _("Eject Drive?"), buttons, content,
            self._do_eject, path, mount,
        )

    def _do_eject(self, dialog, response, path, mount):
        self._gtk.remove_dialog(dialog)
        if response != Gtk.ResponseType.OK:
            return
        if mount is None:
            for m in self._vol_monitor.get_mounts():
                root = m.get_root()
                if root and root.get_path() == path:
                    mount = m
                    break
        if mount is not None:
            mount.unmount_with_operation(
                Gio.MountUnmountFlags.NONE, None, None, self._eject_done, None,
            )
        else:
            threading.Thread(target=self._eject_fallback, args=(path,), daemon=True).start()

    def _eject_done(self, mount, result, _user_data):
        try:
            mount.unmount_with_operation_finish(result)
            GLib.idle_add(self._eject_ui_done, None)
        except Exception as exc:
            GLib.idle_add(self._eject_ui_done, str(exc))

    def _eject_fallback(self, path):
        try:
            subprocess.run(["umount", path], check=True, capture_output=True, timeout=10)
            GLib.idle_add(self._eject_ui_done, None)
        except Exception as exc:
            GLib.idle_add(self._eject_ui_done, str(exc))

    def _eject_ui_done(self, error):
        if error:
            self._screen.show_popup_message(_("Could not eject drive:\n") + error, level=2)
        else:
            self._screen.show_popup_message(_("Drive ejected safely"), level=1)
        if self._mode == _MODE_DRIVE_SELECT:
            self._show_drive_select()
        elif self._mode == _MODE_EJECT:
            self._show_eject_screen()
        return False

    #  Copy Magic

    def _show_confirm_dialog(self, items):
        sz = int(self._gtk.img_scale * self.bts * 1.5)
        file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        for path in sorted(items, key=os.path.basename):
            name = os.path.basename(path)
            row = Gtk.Box(spacing=8)
            row.get_style_context().add_class("frame-item")

            thumb = self._get_file_thumbnail(path, sz)
            if thumb is not None:
                row.pack_start(Gtk.Image.new_from_pixbuf(thumb), False, False, 3)
            else:
                row.pack_start(self._gtk.Image("file", sz, sz), False, False, 3)

            row.pack_start(
                Gtk.Label(label=name, xalign=0, hexpand=True,
                          ellipsize=Pango.EllipsizeMode.END),
                True, True, 0,
            )
            file_box.add(row)

        scroll = self._gtk.ScrolledWindow()
        scroll.add(file_box)

        buttons = [
            {"name": _("Copy"), "response": Gtk.ResponseType.OK, "style": "color1"},
            {"name": _("Nope!"), "response": Gtk.ResponseType.CANCEL, "style": "color2"},
        ]
        self._gtk.Dialog(
            _("Confirm Copy"), buttons, scroll,
            self._on_confirm_copy, items,
        )

    def _get_file_thumbnail(self, path, size):
        if self._direction == "to":
            gcodes_path = self._dest_path()
            if gcodes_path:
                try:
                    rel = os.path.relpath(path, gcodes_path)
                    if self._files.has_thumbnail(rel):
                        loc = self._files.get_thumbnail_location(rel)
                        if loc is not None:
                            if loc[0] == "file":
                                return self._gtk.PixbufFromFile(loc[1], size, size)
                            if loc[0] == "http":
                                return self._gtk.PixbufFromHttp(loc[1], size, size)
                except Exception:
                    pass
        if path.lower().endswith((".gcode", ".g", ".gc", ".gco")):
            return self._extract_gcode_thumbnail(path, size)
        return None

    def _extract_gcode_thumbnail(self, filepath, size):
        try:
            best_data = None
            best_area = 0
            in_thumb = False
            cur_data = []
            cur_area = 0
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                header = fh.read(65536)
            for line in header.splitlines():
                if not line.startswith(";"):
                    if best_data:
                        break
                    continue
                content = line[1:].strip()
                if content.startswith("thumbnail begin"):
                    in_thumb = True
                    cur_data = []
                    parts = content.split()
                    try:
                        w, h = map(int, parts[2].split("x"))
                        cur_area = w * h
                    except Exception:
                        cur_area = 0
                elif content == "thumbnail end":
                    if cur_data and cur_area > best_area:
                        best_data = list(cur_data)
                        best_area = cur_area
                    in_thumb = False
                elif in_thumb:
                    cur_data.append(content)
            if best_data:
                raw = base64.b64decode("".join(best_data))
                stream = Gio.MemoryInputStream.new_from_data(raw, None)
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                    stream, size, size, True, None
                )
                stream.close_async(2)
                return pixbuf
        except Exception as exc:
            logging.debug(f"Thumbnail extraction failed for {filepath}: {exc}")
        return None

    def _on_confirm_copy(self, dialog, response, items):
        self._gtk.remove_dialog(dialog)
        if response != Gtk.ResponseType.OK:
            return
        dest = self._dest_path() if self._direction == "from" else self._usb_dest
        if not dest:
            self._screen.show_popup_message(_("Could not determine destination path"), level=2)
            return
        threading.Thread(target=self._copy_worker, args=(items, dest), daemon=True).start()

    def _copy_worker(self, items, dest):
        copied, errors = 0, []
        for src in items:
            try:
                shutil.copy2(src, os.path.join(dest, os.path.basename(src)))
                copied += 1
            except Exception as exc:
                logging.error(f"USB copy error {src!r}: {exc}")
                errors.append(str(exc))
        GLib.idle_add(self._copy_done, copied, errors)

    def _copy_done(self, copied, errors):
        if errors:
            msg = _("Copy completed with errors:\n") + "\n".join(errors[:3])
            self._screen.show_popup_message(msg, level=2)
        else:
            msg = ngettext("Copied {n} file", "Copied {n} files", copied).format(n=copied)
            self._screen.show_popup_message(msg, level=1)
        return False

    #  Nav

    def _clear_file_box(self):
        for child in self._file_box.get_children():
            self._file_box.remove(child)

    def back(self):
        if self._mode == _MODE_FILES:
            if len(self._available_drives) > 1:
                self._show_drive_select()
            else:
                self._show_main()
            return True
        if self._mode in (_MODE_DRIVE_SELECT, _MODE_EJECT):
            self._show_main()
            return True
        return False

    #  Activate / Deactivate

    def activate(self):
        pass

    def deactivate(self):
        for sig in self._mount_sigs:
            try:
                self._vol_monitor.disconnect(sig)
            except Exception:
                pass
        self._mount_sigs.clear()
