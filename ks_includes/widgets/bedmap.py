import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class BedMap(Gtk.DrawingArea):
    def __init__(self, font_size, bm):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect('draw', self.draw_graph)
        self.font_size = font_size
        self.font_spacing = round(self.font_size * 1.5)
        self.bm = list(reversed(bm)) if bm is not None else None

    def update_bm(self, bm):
        self.bm = list(reversed(bm)) if bm is not None else None

    def draw_graph(self, da, ctx):
        width = da.get_allocated_width()
        height = da.get_allocated_height()
        # Styling
        ctx.set_line_width(1)
        ctx.set_font_size(self.font_size)

        if self.bm is None:
            ctx.move_to(self.font_spacing, height / 2)
            ctx.set_source_rgb(0.5, 0.5, 0.5)
            ctx.show_text(_("No mesh has been loaded"))
            ctx.stroke()
            return

        rows = len(self.bm)
        columns = len(self.bm[0])
        for i, row in enumerate(self.bm):
            ty = height / rows * i
            by = ty + height / rows
            for j, column in enumerate(row):
                lx = width / columns * j
                rx = lx + width / columns
                # Colors
                ctx.set_source_rgb(*self.colorbar(column))
                ctx.move_to(lx, ty)
                ctx.line_to(lx, by)
                ctx.line_to(rx, by)
                ctx.line_to(rx, ty)
                ctx.close_path()
                ctx.fill()
                ctx.stroke()
                if rows > 16 or columns > 8:
                    continue
                # Numbers
                ctx.set_source_rgb(0, 0, 0)
                if column > 0:
                    ctx.move_to((lx + rx) / 2 - self.font_size, (ty + by + self.font_size) / 2)
                else:
                    ctx.move_to((lx + rx) / 2 - self.font_size * 1.2, (ty + by + self.font_size) / 2)
                ctx.show_text(f"{column:.2f}")
                ctx.stroke()

    @staticmethod
    def colorbar(value):
        rmax = 0.25
        color = min(1, max(0, 1 - 1 / rmax * abs(value)))
        if value > 0:
            return [1, color, color]
        if value < 0:
            return [color, color, 1]
        return [1, 1, 1]
