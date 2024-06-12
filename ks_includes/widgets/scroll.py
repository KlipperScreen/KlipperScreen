import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk


class CustomScrolledWindow(Gtk.ScrolledWindow):
    def __init__(self, steppers=False, **kwargs):
        args = {
            "hexpand": True,
            "vexpand": True,
            "overlay_scrolling": False
        }
        args.update(kwargs)
        super().__init__(**args)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.TOUCH_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK)
        if steppers:
            self.get_vscrollbar().get_style_context().add_class("with-steppers")
