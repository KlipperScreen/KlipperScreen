import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


COLORS = {
    "time": "DarkGrey",
    "info": "Silver",
    "warning": "DarkOrange",
    "error": "FireBrick",
}


def remove_newlines(msg: str) -> str:
    return msg.replace('\n', ' ')


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Notifications")
        super().__init__(screen, title)
        self.empty = _("Notification log empty")
        self.tb = Gtk.TextBuffer(text=self.empty)
        tv = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        tv.set_buffer(self.tb)
        tv.connect("size-allocate", self._autoscroll)

        scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroll.add(tv)

        clear_button = self._gtk.Button("refresh", _('Clear') + " ", None, self.bts, Gtk.PositionType.RIGHT, 1)
        clear_button.get_style_context().add_class("buttons_slim")
        clear_button.set_vexpand(False)
        clear_button.connect("clicked", self.clear)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.add(clear_button)
        content_box.add(scroll)
        self.content.add(content_box)

    def activate(self):
        self.refresh()

    def add_notification(self, log):
        if log["level"] == 0:
            if "error" in log["message"].lower() or "cannot" in log["message"].lower():
                color = COLORS["error"]
            else:
                color = COLORS["info"]
        elif log["level"] == 1:
            color = COLORS["info"]
        elif log["level"] == 2:
            color = COLORS["warning"]
        else:
            color = COLORS["error"]
        self.tb.insert_markup(
            self.tb.get_end_iter(),
            f'\n<span color="{COLORS["time"]}">{log["time"]}</span> '
            f'<span color="{color}"><b>{remove_newlines(log["message"])}</b></span>',
            -1
        )

    def clear(self, widget):
        self.tb.set_text("")
        self._screen.notification_log_clear()

    def refresh(self):
        self.tb.set_text("")
        for log in self._screen.notification_log:
            self.add_notification(log)

    def process_update(self, action, data):
        if action != "notify_log":
            return
        self.add_notification(data)
