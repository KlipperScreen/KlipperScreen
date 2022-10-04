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
        self.font_spacing = round(self.font_size * 1.5)
        self.margin_left = round(self.font_size * 2.75)
        self.margin_right = 15
        self.margin_top = 10
        self.margin_bottom = self.font_size * 2
        self.objects = self.printer.get_stat("exclude_object", "objects")
        self.current_object = self.printer.get_stat("current_object", "current_object")
        self.excluded_objects = self.printer.get_stat("exclude_object", "excluded_objects")
        self.min_x = self.min_y = 99999999
        self.max_x = self.max_y = 0

    def x_graph_to_bed(self, width, gx):
        return (((gx - self.margin_left) * (self.max_x - self.min_x))
                / (width - self.margin_left - self.margin_right)) + self.min_x

    def y_graph_to_bed(self, height, gy):
        return ((1 - ((gy - self.margin_top) / (height - self.margin_top - self.margin_bottom)))
                * (self.max_y - self.min_y)) + self.min_y

    def event_cb(self, da, ev):
        # Convert coordinates from screen-graph to bed
        x = self.x_graph_to_bed(da.get_allocated_width(), ev.x)
        y = self.y_graph_to_bed(da.get_allocated_height(), ev.y)
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
        right = da.get_allocated_width() - self.margin_right
        bottom = da.get_allocated_height() - self.margin_bottom
        self.objects = self.printer.get_stat("exclude_object", "objects")

        for obj in self.objects:
            for point in obj["polygon"]:
                # Find min coords
                self.min_x = min(self.min_x, point[0])
                self.min_y = min(self.min_y, point[1])
                # Find max coords
                self.max_x = max(self.max_x, point[0])
                self.max_y = max(self.max_y, point[1])

        # Styling
        ctx.set_source_rgb(.5, .5, .5)  # Grey
        ctx.set_line_width(1)
        ctx.set_font_size(self.font_size)

        # Borders
        ctx.move_to(self.margin_left, self.margin_top)
        # logging.info(f"l:{self.margin_left:.0f} t:{self.margin_top:.0f} r:{right:.0f} b:{bottom:.0f}")
        ctx.line_to(right, self.margin_top)
        ctx.line_to(right, bottom)
        ctx.line_to(self.margin_left, bottom)
        ctx.line_to(self.margin_left, self.margin_top)
        ctx.stroke()

        # Axis labels
        ctx.move_to(0, bottom + self.font_spacing)
        ctx.show_text(f"{self.min_x:.0f},{self.min_y:.0f}")
        ctx.stroke()
        ctx.move_to(right - self.font_spacing * 2, bottom + self.font_spacing)
        ctx.show_text(f"{self.max_x:.0f},{self.min_y:.0f}")
        ctx.stroke()
        ctx.move_to(0, self.font_spacing / 2)
        ctx.show_text(f"{self.min_x:.0f},{self.max_y:.0f}")
        ctx.stroke()

        # middle markers
        midx = (right - self.margin_left) / 2 + self.margin_left
        ctx.set_dash([1, 1])
        ctx.move_to(midx, self.margin_top)
        ctx.line_to(midx, bottom)
        ctx.stroke()
        midy = (self.margin_top - bottom) / 2 + bottom
        ctx.move_to(self.margin_left, midy)
        ctx.line_to(right, midy)
        ctx.stroke()
        ctx.set_dash([1, 0])

        # Draw objects
        for obj in self.objects:
            # change the color depending on the status
            if obj['name'] == self.printer.get_stat("exclude_object", "current_object"):
                ctx.set_source_rgb(1, 0, 0)  # Red
            elif obj['name'] in self.printer.get_stat("exclude_object", "excluded_objects"):
                ctx.set_source_rgb(0, 0, 0)  # Black
            else:
                ctx.set_source_rgb(.5, .5, .5)  # Grey
            for i, point in enumerate(obj["polygon"]):
                # Convert coordinates from bed to screen-graph
                x = self.x_bed_to_graph(da.get_allocated_width(), point[0])
                y = self.y_bed_to_graph(da.get_allocated_height(), point[1])
                if i == 0:
                    ctx.move_to(x, y)
                    continue
                ctx.line_to(x, y)
                # logging.info(f"obj graph: {x=:.0f},{y=:.0f} bed: {point[0]:.0f},{point[1]:.0f}")
            ctx.close_path()
            ctx.fill()
            ctx.stroke()

    def x_bed_to_graph(self, width, bx):
        return (((bx - self.min_x) * (width - self.margin_left - self.margin_right))
                / (self.max_x - self.min_x)) + self.margin_left

    def y_bed_to_graph(self, height, by):
        return ((1 - ((by - self.min_y) / (self.max_y - self.min_y)))
                * (height - self.margin_top - self.margin_bottom)) + self.margin_top
