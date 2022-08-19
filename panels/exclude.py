import gi
import contextlib
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return ExcludeObjectPanel(*args)


class ExcludeObjectPanel(ScreenPanel):
    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)
        self.object_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.object_list.set_valign(Gtk.Align.CENTER)
        self.object_list.set_halign(Gtk.Align.CENTER)
        self.buttons = {}
        self.current_object = self._gtk.ButtonImage("extrude", "", scale=.66,
                                                    position=Gtk.PositionType.LEFT, lines=1)
        self.current_object.connect("clicked", self.exclude_current)
        self.current_object.set_hexpand(True)
        self.current_object.set_vexpand(False)
        self.excluded_objects = self._printer.get_stat("exclude_object", "excluded_objects")
        logging.info(f'Excluded: {self.excluded_objects}')

    def initialize(self, panel_name):
        objects = self._printer.get_stat("exclude_object", "objects")
        for obj in objects:
            logging.info(f"Adding {obj['name']}")
            self.add_object(obj["name"])

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.object_list)
        scroll.set_halign(Gtk.Align.CENTER)
        scroll.set_size_request(self._gtk.get_content_width(), 0)

        grid = Gtk.Grid()
        grid.attach(self.current_object, 0, 0, 1, 1)
        grid.attach(Gtk.Separator(), 0, 1, 1, 1)
        grid.attach(scroll, 0, 2, 1, 1)
        self.content.add(grid)
        self.content.show_all()

    def add_object(self, name):
        if name not in self.buttons:
            self.buttons[name] = self._gtk.ButtonImage("cancel", name, scale=.66, position=Gtk.PositionType.LEFT,
                                                       lines=1)
            self.buttons[name].connect("clicked", self.exclude_object, name)
            self.buttons[name].set_hexpand(True)
        if name in self.excluded_objects:
            self.buttons[name].set_sensitive(False)
        self.buttons[name].get_style_context().add_class("frame-item")
        self.object_list.add(self.buttons[name])

    def exclude_object(self, widget, name):
        script = {"script": f"EXCLUDE_OBJECT NAME={name}"}
        self._screen._confirm_send_action(
            widget,
            _("Are you sure do you want to exclude the object?") + f"\n\n{name}",
            "printer.gcode.script",
            script
        )

    def exclude_current(self, widget):
        self.exclude_object(widget, f"{self.current_object.get_label()}")

    def process_update(self, action, data):
        if action == "notify_status_update":
            with contextlib.suppress(KeyError):
                self.current_object.set_label(f'{data["exclude_object"]["current_object"]}')
            with contextlib.suppress(KeyError):
                logging.info(f'Excluded objects: {data["exclude_object"]["excluded_objects"]}')
                self.excluded_objects = data["exclude_object"]["excluded_objects"]
                for name in self.excluded_objects:
                    self.buttons[name].set_sensitive(False)
            with contextlib.suppress(KeyError):
                logging.info(f'Objects: {data["exclude_object"]["objects"]}')
        elif action == "notify_gcode_response" and "Excluding object" in data:
            self._screen.show_popup_message(data, level=1)
