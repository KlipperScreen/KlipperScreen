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
        self.invert_x = False
        self.invert_y = False
        self.rotation = 0
        self.mesh_min = [0, 0]
        self.mesh_max = [0, 0]
        self.mesh_radius = 0

    def update_bm(self, bm, radius=None):
        if not bm:
            self.bm = None
            return

        for key, value in bm.items():
            if key == 'profiles':
                continue
        if radius:
            self.mesh_radius = float(radius)
        if 'mesh_min' in bm:
            self.mesh_min = bm['mesh_min']
        elif 'min_x' in bm and 'min_y' in bm:
            self.mesh_min = (float(bm['min_x']), float(bm['min_y']))
        if 'mesh_max' in bm:
            self.mesh_max = bm['mesh_max']
        elif 'max_x' in bm and 'max_y' in bm:
            self.mesh_max = (float(bm['max_x']), float(bm['max_y']))
        if 'probed_matrix' in bm:
            bm = bm['probed_matrix']
        elif 'points' in bm:
            bm = self.transform_points_to_matrix(bm['points'])
        else:
            self.bm = None
            return

        if self.invert_x and self.invert_y:
            self.rotation = (self.rotation + 180) % 360
            self.invert_x = self.invert_y = False
        if self.invert_x:
            new_max = [self.mesh_min[0], self.mesh_max[1]]
            new_min = [self.mesh_max[0], self.mesh_min[1]]
            self.mesh_max = new_max
            self.mesh_min = new_min
            self.bm = [list(reversed(b)) for b in list(reversed(bm))]
        if self.invert_y:
            new_max = [self.mesh_max[0], self.mesh_min[1]]
            new_min = [self.mesh_min[0], self.mesh_max[1]]
            self.mesh_max = new_max
            self.mesh_min = new_min
            self.bm = list(bm)
        else:
            self.bm = list(reversed(bm))

        if self.rotation in (90, 180, 270):
            self.bm = self.rotate_matrix(self.bm)

    @staticmethod
    def transform_points_to_matrix(points):
        rows = points.strip().split('\n')
        return [list(map(float, row.split(','))) for row in rows]

    def rotate_matrix(self, matrix):
        if self.rotation == 90:
            new_max = [self.mesh_max[1], self.mesh_min[0]]
            new_min = [self.mesh_min[1], self.mesh_max[0]]
            self.mesh_max = new_max
            self.mesh_min = new_min
            return [list(row) for row in zip(*matrix[::-1])]
        elif self.rotation == 180:
            new_max = [self.mesh_min[0], self.mesh_min[1]]
            new_min = [self.mesh_max[0], self.mesh_max[1]]
            self.mesh_max = new_max
            self.mesh_min = new_min
            return [list(row)[::-1] for row in matrix[::-1]]
        elif self.rotation == 270:
            new_max = [self.mesh_min[1], self.mesh_max[0]]
            new_min = [self.mesh_max[1], self.mesh_min[0]]

            self.mesh_max = new_max
            self.mesh_min = new_min
            return [list(row) for row in zip(*matrix)][::-1]

    def draw_graph(self, da, ctx):
        width = da.get_allocated_width()
        height = da.get_allocated_height()
        gwidth = int(width - self.font_size * 2.2)
        gheight = int(height - self.font_size * 1.8)
        # Styling
        ctx.set_line_width(1)
        ctx.set_font_size(self.font_size)

        if self.bm is None:
            ctx.move_to(self.font_spacing, height / 2)
            ctx.set_source_rgb(0.5, 0.5, 0.5)
            ctx.show_text(_("No mesh has been loaded"))
            ctx.stroke()
            return

        text_side_top = [0, self.font_size]
        text_side_bottom = [0, height - int(self.font_size * 2)]
        text_side_middle = [self.font_size, (text_side_top[1] + text_side_bottom[1]) / 2]
        text_bottom_left = [self.font_size * 1.8, height - int(self.font_size / 2)]
        text_bottom_right = [width - int(self.font_size * 2.2), height - int(self.font_size / 2)]
        text_bottom_middle = [int(self.font_size * 2 + gwidth / 2), height - int(self.font_size / 2)]

        ctx.set_source_rgb(0.5, 0.5, 0.5)
        ctx.move_to(*text_side_middle)
        ctx.show_text(f"{'Y' if self.rotation in (0, 180) else 'X'}")
        ctx.move_to(*text_bottom_middle)
        ctx.show_text(f"{'X' if self.rotation in (0, 180) else 'Y'}")
        ctx.stroke()

        # min and max axis labels
        ctx.move_to(*text_side_top)
        ctx.show_text(f"{self.mesh_max[1]:.0f}".rjust(4, " "))
        ctx.move_to(*text_side_bottom)
        ctx.show_text(f"{self.mesh_min[1]:.0f}".rjust(4, " "))
        ctx.move_to(*text_bottom_left)
        ctx.show_text(f"{self.mesh_min[0]:.0f}".rjust(4, " "))
        ctx.move_to(*text_bottom_right)
        ctx.show_text(f"{self.mesh_max[0]:.0f}".rjust(4, " "))
        ctx.stroke()

        rows = len(self.bm)
        columns = len(self.bm[0])
        for i, row in enumerate(self.bm):
            ty = (gheight / rows * i)
            by = ty + gheight / rows
            column: float
            for j, column in enumerate(row):
                if self.mesh_radius > 0 and self.round_bed_skip(i, j, row, rows, columns):
                    continue
                lx = (gwidth / columns * j) + self.font_size * 2.2
                rx = lx + gwidth / columns
                # Colors
                ctx.set_source_rgb(*self.colorbar(column))
                ctx.move_to(lx, ty)
                ctx.line_to(lx, by)
                ctx.line_to(rx, by)
                ctx.line_to(rx, ty)
                ctx.close_path()
                ctx.fill()
                ctx.stroke()
                # Numbers
                if gwidth / columns < self.font_size * 3:
                    continue
                ctx.set_source_rgb(0, 0, 0)
                if column > 0:
                    ctx.move_to((lx + rx) / 2 - self.font_size, (ty + by + self.font_size) / 2)
                else:
                    ctx.move_to((lx + rx) / 2 - self.font_size * 1.2, (ty + by + self.font_size) / 2)
                ctx.show_text(f"{column:.2f}")
                ctx.stroke()

    @staticmethod
    def round_bed_skip(i, j, row, rows, columns):
        if columns <= 3:
            return False
        if i != rows // 2 and j != columns // 2:
            # Skip if the value is equal to the next but verify that this also happens on the other side
            if j < columns // 2 and row[j] == row[j + 1] and row[columns - 1] == row[columns - 1 - j]:
                return True
            if j > columns // 2 and row[j] == row[j - 1] and row[0] == row[columns - j]:
                return True
        return False

    @staticmethod
    def colorbar(value: float):
        rmax = 0.25
        color = min(1, max(0, 1 - 1 / rmax * abs(value)))
        if value > 0:
            return [1, color, color]
        if value < 0:
            return [color, color, 1]
        return [1, 1, 1]

    def set_inversion(self, x=False, y=False):
        self.invert_x = x
        self.invert_y = y

    def set_rotation(self, rotation=0):
        self.rotation = rotation
