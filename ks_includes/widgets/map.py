import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk


class ObjectMap(Gtk.DrawingArea):
    def __init__(self, screen, printer, font_size):
        super().__init__()
        self._screen = screen
        self.set_hexpand(True)
        self.set_vexpand(True)
        # self.get_style_context().add_class('objectmap')
        self.printer = printer
        self.max_length = 0
        self.connect('draw', self.draw_graph)
        self.add_events(Gdk.EventMask.TOUCH_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('button_press_event', self.event_cb)
        self.font_size = round(font_size * 0.75)
        self.margin_left = round(self.font_size * 2.75)
        self.margin_right = 15
        self.margin_top = 10
        self.margin_bottom = self.font_size * 2
        self.objects = self.printer.get_stat("exclude_object", "objects")
        self.current_object = self.printer.get_stat("current_object", "current_object")
        self.excluded_objects = self.printer.get_stat("exclude_object", "excluded_objects")

    def event_cb(self, da, ev):
        width = da.get_allocated_width()
        x = (ev.x - self.margin_left) * self.printer.get_bed_max('x') / (width - self.margin_left - self.margin_right)
        y = self.printer.get_bed_max('y') * (1 - (ev.y - self.margin_top) / (width - self.margin_top))
        logging.info(f"Touched GRAPH {ev.x:.0f},{ev.y:.0f} BED: {x:.0f},{y:.0f}")

        for obj in self.objects:
            obj_min_x = obj_max_x = obj["polygon"][0][0]
            obj_min_y = obj_max_y = obj["polygon"][0][1]
            for point in obj["polygon"]:
                obj_min_x = min(obj_min_x, point[0])
                obj_min_y = min(obj_min_y, point[1])
                obj_max_x = max(obj_max_x, point[0])
                obj_max_y = max(obj_max_y, point[1])
            if obj_min_x < x < obj_max_x and obj_min_y < y < obj_max_y:
                logging.info(f"TOUCHED object it's: {obj['name']}")
                if obj['name'] not in self.excluded_objects:
                    self.exclude_object(obj['name'])
                break

    def exclude_object(self, name):
        script = {"script": f"EXCLUDE_OBJECT NAME={name}"}
        self._screen._confirm_send_action(
            None,
            _("Are you sure do you want to exclude the object?") + f"\n\n{name}",
            "printer.gcode.script",
            script
        )

    def draw_graph(self, da, ctx):
        self.objects = self.printer.get_stat("exclude_object", "objects")
        self.current_object = self.printer.get_stat("exclude_object", "current_object")
        self.excluded_objects = self.printer.get_stat("exclude_object", "excluded_objects")
        width = da.get_allocated_width()
        height = da.get_allocated_height()
        left = self.margin_left
        right = width - self.margin_right
        top = self.margin_top
        bottom = height - self.margin_bottom
        font_spacing = round(self.font_size * 1.5)

        # Styling
        ctx.set_source_rgb(.5, .5, .5)
        ctx.set_line_width(1)
        ctx.set_font_size(self.font_size)

        # Borders
        ctx.move_to(left, top)
        logging.info(f"l:{left:.0f} t:{top:.0f} r:{right:.0f} b:{bottom:.0f}")
        ctx.line_to(right, top)
        ctx.line_to(right, bottom)
        ctx.line_to(left, bottom)
        ctx.line_to(left, top)
        ctx.stroke()

        # Indicators
        ctx.line_to(left - font_spacing, bottom + font_spacing)
        ctx.show_text("0".rjust(3, " "))
        ctx.stroke()

        ctx.line_to(right - font_spacing, bottom + font_spacing)
        ctx.show_text(f"{self.printer.get_bed_max('x'):.0f}")
        ctx.stroke()

        ctx.line_to(left - 1.5 * font_spacing, top)
        ctx.show_text(f"{self.printer.get_bed_max('y'):.0f}".rjust(3, " "))
        ctx.stroke()

        # middle markers
        midx = (right - left) / 2 + left
        ctx.set_dash([1, 1])
        ctx.move_to(midx, top)
        ctx.line_to(midx, bottom)
        ctx.stroke()
        midy = (top - bottom) / 2 + bottom
        ctx.move_to(left, midy)
        ctx.line_to(right, midy)
        ctx.stroke()
        ctx.set_dash([1, 0])

        # objects
        for obj in self.objects:
            # change the color depending on the status
            if obj['name'] == self.current_object:
                ctx.set_source_rgb(1, 0, 0)
            elif obj['name'] in self.excluded_objects:
                ctx.set_source_rgb(0, 0, 0)
            else:
                ctx.set_source_rgb(.5, .5, .5)
            for i, point in enumerate(obj["polygon"]):
                x = self.x_convert_bed_to_graph_coords(width, point[0])
                y = self.y_convert_bed_to_graph_coords(width, point[1])
                if i == 0:
                    ctx.move_to(x, y)
                    continue
                ctx.line_to(x, y)
                # logging.info(f"obj graph: {x=:.0f},{y=:.0f} bed: {point[0]:.0f},{point[1]:.0f}")
            ctx.close_path()
            ctx.fill()
            ctx.stroke()

    def x_convert_bed_to_graph_coords(self, w, bx):
        return ((bx * (w - self.margin_left - self.margin_right)) / self.printer.get_bed_max('x')) + self.margin_left

    def y_convert_bed_to_graph_coords(self, w, by):
        return ((1 - (by / self.printer.get_bed_max('y'))) * (w - self.margin_top)) + self.margin_top
