import contextlib
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.objectmap import ObjectMap


def create_panel(*args):
    return ExcludeObjectPanel(*args)


class ExcludeObjectPanel(ScreenPanel):
    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)
        self._screen = screen
        self.object_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.object_list.set_valign(Gtk.Align.CENTER)
        self.object_list.set_halign(Gtk.Align.START)
        self.buttons = {}
        self.current_object = self._gtk.ButtonImage("extrude", "", scale=.66, position=Gtk.PositionType.LEFT, lines=1)
        self.current_object.connect("clicked", self.exclude_current)
        self.current_object.set_vexpand(False)
        self.excluded_objects = self._printer.get_stat("exclude_object", "excluded_objects")
        logging.info(f'Excluded: {self.excluded_objects}')
        self.objects = self._printer.get_stat("exclude_object", "objects")
        self.labels['map'] = None

    def initialize(self, panel_name):
        for obj in self.objects:
            logging.info(f"Adding {obj['name']}")
            self.add_object(obj["name"])

        scroll = self._gtk.ScrolledWindow()
        scroll.set_size_request((self._screen.width * .9) // 2, -1)
        scroll.add(self.object_list)
        scroll.set_halign(Gtk.Align.CENTER)

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)
        grid.attach(self.current_object, 0, 0, 2, 1)
        grid.attach(Gtk.Separator(), 0, 1, 2, 1)

        if self.objects and "polygon" in self.objects[0]:
            self.labels['map'] = ObjectMap(self._screen, self._printer, self._gtk.get_font_size())
            grid.attach(self.labels['map'], 0, 2, 1, 1)
            grid.attach(scroll, 1, 2, 1, 1)
        else:
            grid.attach(scroll, 0, 2, 2, 1)

        self.content.add(grid)
        self.content.show_all()

    def add_object(self, name):
        if name not in self.buttons and name not in self.excluded_objects:
            self.buttons[name] = self._gtk.Button(name.replace("_", " "))
            self.buttons[name].get_children()[0].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            self.buttons[name].get_children()[0].set_line_wrap(True)
            self.buttons[name].connect("clicked", self.exclude_object, name)
            self.buttons[name].get_style_context().add_class("frame-item")
            self.object_list.add(self.buttons[name])

    def exclude_object(self, widget, name):
        if len(self.excluded_objects) == len(self.objects) - 1:
            # Do not exclude the last object, this is a workaround for a bug of klipper that starts
            # to move the toolhead really fast skipping gcode until the file ends
            # Remove this if they fix it.
            self._screen._confirm_send_action(
                widget,
                _("Are you sure you wish to cancel this print?"),
                "printer.print.cancel",
            )
            return
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
                # Update objects
                self.objects = data["exclude_object"]["objects"]
                logging.info(f'Objects: {data["exclude_object"]["objects"]}')
                for obj in self.buttons:
                    self.object_list.remove(self.buttons[obj])
                self.buttons = {}
                for obj in self.objects:
                    logging.info(f"Adding {obj['name']}")
                    self.add_object(obj["name"])
            with contextlib.suppress(KeyError):
                # Update current objects
                if data["exclude_object"]["current_object"]:
                    self.current_object.set_label(f'{data["exclude_object"]["current_object"].replace("_", " ")}')
                self.update_graph()
            with contextlib.suppress(KeyError):
                # Update excluded objects
                logging.info(f'Excluded objects: {data["exclude_object"]["excluded_objects"]}')
                self.excluded_objects = data["exclude_object"]["excluded_objects"]
                for name in self.excluded_objects:
                    if name in self.buttons:
                        self.object_list.remove(self.buttons[name])
                self.update_graph()
                if len(self.excluded_objects) == len(self.objects):
                    self.menu_return(False)
        elif action == "notify_gcode_response" and "Excluding object" in data:
            self._screen.show_popup_message(data, level=1)
            self.update_graph()

    def activate(self):
        self.update_graph()

    def update_graph(self):
        if self.labels['map']:
            self.labels['map'].queue_draw()
