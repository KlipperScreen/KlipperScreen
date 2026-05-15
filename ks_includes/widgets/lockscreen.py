import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


class LockScreen:
    def __init__(self, screen):
        self.screen = screen
        self.lock_box = None
        self.unlock_box = None
        self.autolock_timeout = None
        self.autolock_time = 0

    def set_autolock_timeout(self, timeout):
        """Set the auto-lock timeout in seconds. 0 means disabled."""
        try:
            self.autolock_time = abs(int(timeout))
        except (ValueError, TypeError):
            self.autolock_time = 0
        self.reset_timeout()

    def reset_timeout(self, *args):
        """Reset the auto-lock timer. Called on user interaction."""
        if self.autolock_timeout is not None:
            GLib.source_remove(self.autolock_timeout)
            self.autolock_timeout = None
        if self.autolock_time > 0 and self.lock_box is None:
            self.autolock_timeout = GLib.timeout_add_seconds(self.autolock_time, self._auto_lock)

    def _auto_lock(self):
        """Called when the auto-lock timer expires."""
        self.autolock_timeout = None
        if self.lock_box is None:
            logging.info("Auto-locking screen")
            self.lock(None)
        return False

    def lock(self, widget):
        self.screen._menu_go_back(None, True)
        logging.info("Locked the screen")
        close = Gtk.Button()
        close.connect("clicked", self.unlock)
        self.lock_box = Gtk.Box(
            width_request=self.screen.width,
            height_request=self.screen.height,
            halign=Gtk.Align.CENTER,
        )
        self.lock_box.pack_start(close, True, True, 0)
        self.lock_box.get_style_context().add_class("lock")
        self.screen.overlay.add_overlay(self.lock_box)
        close.grab_focus()
        self.lock_box.show_all()

    def unlock(self, widget):
        if not self.unlock_box:
            self.unlock_box = self.create_unlock_box()
        self.screen.overlay.add_overlay(self.unlock_box)
        self.unlock_box.show_all()
        self.screen.overlay.get_children()[0].hide()

    def create_unlock_box(self):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            width_request=self.screen.width,
            height_request=self.screen.height,
            valign=Gtk.Align.CENTER,
        )
        entry = Gtk.Entry(hexpand=True, vexpand=False, placeholder_text=_("Password"))
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        entry.set_visibility(False)
        entry.connect("touch-event", self.screen.show_keyboard, box, self.relock)
        entry.connect("button-press-event", self.screen.show_keyboard, box, self.relock)
        entry.connect("activate", self.unlock_attempt, entry)
        entry.get_style_context().add_class("lockscreen_entry")
        entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
        entry.connect("icon-press", self.show_pass)
        ok = Gtk.Button(label=_("Unlock"))
        ok.connect("clicked", self.unlock_attempt, entry)
        ok.get_style_context().add_class("lockscreen_button")
        entry_row = Gtk.Box(hexpand=True, vexpand=True, valign=Gtk.Align.CENTER)
        entry_row.pack_start(entry, True, True, 0)
        entry_row.pack_start(ok, False, True, 0)
        box.pack_start(entry_row, True, True, 0)
        return box

    @staticmethod
    def show_pass(entry, icon_pos, event):
        entry.grab_focus()
        visible = not entry.get_visibility()
        entry.set_visibility(visible)
        if visible:
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-conceal-symbolic")
            entry.get_style_context().add_class("active")
        else:
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
            entry.get_style_context().remove_class("active")

    def relock(self, entry=None, box=None):
        if not self.lock_box:
            return
        if self.unlock_box:
            self.screen.overlay.remove(self.unlock_box)
        self.unlock_box = None
        self.lock_box.get_children()[0].grab_focus()
        self.screen.overlay.get_children()[0].show_all()

    def unlock_attempt(self, widget, entry):
        if entry.get_text() != self.screen._config.get_main_config().get("lock_password", ""):
            logging.info("Failed unlock")
            self.screen.show_popup_message(_("Unlock failed"))
            return
        self.clear_lock()

    def clear_lock(self):
        if self.lock_box:
            self.screen.overlay.remove(self.lock_box)
        if self.unlock_box:
            self.screen.overlay.remove(self.unlock_box)
        self.lock_box = None
        self.unlock_box = None
        self.screen.remove_keyboard()
        self.screen.overlay.get_children()[0].show()
        logging.info("Unlocked")
        self.reset_timeout()
