import datetime
import logging
import math

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk


class HeaterGraph(Gtk.DrawingArea):
    def __init__(self, printer, font_size):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.get_style_context().add_class('heatergraph')
        self.printer = printer
        self.store = {}
        self.max_length = 0
        self.connect('draw', self.draw_graph)
        self.add_events(Gdk.EventMask.TOUCH_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('touch-event', self.event_cb)
        self.connect('button_press_event', self.event_cb)
        self.font_size = round(font_size * 0.75)

    def add_object(self, name, ev_type, rgb=None, dashed=False, fill=False):
        if rgb is None:
            rgb = [0, 0, 0]
        if name not in self.store:
            self.store.update({name: {"show": True}})
        self.store[name].update({ev_type: {
            "dashed": dashed,
            "fill": fill,
            "rgb": rgb
        }})

    @staticmethod
    def event_cb(da, ev):
        if ev.type == Gdk.EventType.BUTTON_PRESS:
            x = ev.x
            y = ev.y
            logging.info(f"Graph area: {x} {y}")

    def get_max_length(self):
        return min(len(self.printer.get_temp_store(name, "temperatures"))
                   for name in self.store if "temperatures" in self.store[name])

    def get_max_num(self, data_points=0):
        mnum = [0]
        for device in self.store:
            if self.store[device]['show']:
                temp = self.printer.get_temp_store(device, "temperatures", data_points)
                if temp:
                    mnum.append(max(temp))
                target = self.printer.get_temp_store(device, "targets", data_points)
                if target:
                    mnum.append(max(target))
        return max(mnum)

    def draw_graph(self, da, ctx):
        width = da.get_allocated_width()
        height = da.get_allocated_height()

        g_width_start = round(self.font_size * 2.75)
        g_width = width - 15
        g_height_start = 10
        g_height = height - self.font_size * 2

        ctx.set_source_rgb(.5, .5, .5)
        ctx.set_line_width(1)
        ctx.set_tolerance(0.1)

        ctx.move_to(g_width_start, g_height_start)
        ctx.line_to(g_width, g_height_start)
        ctx.line_to(g_width, g_height)
        ctx.line_to(g_width_start, g_height)
        ctx.line_to(g_width_start, g_height_start)
        ctx.stroke()

        ctx.set_source_rgb(1, 0, 0)
        ctx.move_to(g_width_start, height)

        gsize = [
            [g_width_start, g_height_start],
            [g_width, g_height]
        ]

        self.max_length = self.get_max_length()
        graph_width = gsize[1][0] - gsize[0][0]
        points_per_pixel = self.max_length / graph_width
        data_points = int(round(graph_width * points_per_pixel, 0))
        max_num = math.ceil(self.get_max_num(data_points) * 1.1 / 10) * 10
        if points_per_pixel == 0:
            return
        d_width = 1 / points_per_pixel

        d_height_scale = self.graph_lines(ctx, gsize, max_num)
        self.graph_time(ctx, gsize, points_per_pixel)

        for name in self.store:
            if not self.store[name]['show']:
                continue
            for dev_type in self.store[name]:
                d = self.printer.get_temp_store(name, dev_type, data_points)
                if d is False:
                    continue
                self.graph_data(ctx, d, gsize, d_height_scale, d_width, self.store[name][dev_type]["rgb"],
                                self.store[name][dev_type]["dashed"], self.store[name][dev_type]["fill"])

    @staticmethod
    def graph_data(ctx, data, gsize, hscale, swidth, rgb, dashed=False, fill=False):
        i = 0
        ctx.set_source_rgba(rgb[0], rgb[1], rgb[2], 1)
        ctx.move_to(gsize[0][0] + 1, gsize[0][1] - 1)
        if dashed:
            ctx.set_dash([10, 5])
        else:
            ctx.set_dash([1, 0])
        d_len = len(data) - 1
        for d in data:
            p_x = i * swidth + gsize[0][0] if i != d_len else gsize[1][0] - 1
            p_y = max(gsize[0][1], min(gsize[1][1], gsize[1][1] - 1 - (d * hscale)))
            if i == 0:
                ctx.move_to(gsize[0][0] + 1, p_y)
                i += 1
                continue
            ctx.line_to(p_x, p_y)
            i += 1
        if fill is False:
            ctx.stroke()
            return

        ctx.stroke_preserve()
        ctx.line_to(gsize[1][0] - 1, gsize[1][1] - 1)
        ctx.line_to(gsize[0][0] + 1, gsize[1][1] - 1)
        if fill:
            ctx.set_source_rgba(rgb[0], rgb[1], rgb[2], .1)
            ctx.fill()

    def graph_lines(self, ctx, gsize, max_num):
        nscale = 10
        max_num = min(max_num, 999)
        while (max_num / nscale) > 5:
            nscale += 10
        # nscale = math.floor((max_num / 10) / 4) * 10
        r = int(max_num / nscale) + 1
        hscale = (gsize[1][1] - gsize[0][1]) / (r * nscale)

        for i in range(r):
            ctx.set_source_rgb(.5, .5, .5)
            lheight = gsize[1][1] - nscale * i * hscale
            ctx.move_to(6, lheight + 3)
            ctx.set_font_size(self.font_size)
            ctx.show_text(str(nscale * i).rjust(3, " "))
            ctx.stroke()
            ctx.set_source_rgba(.5, .5, .5, .2)
            ctx.move_to(gsize[0][0], lheight)
            ctx.line_to(gsize[1][0], lheight)
            ctx.stroke()
        return hscale

    def graph_time(self, ctx, gsize, points_per_pixel):

        now = datetime.datetime.now()
        first = gsize[1][0] - (now.second + ((now.minute % 2) * 60)) / points_per_pixel
        steplen = 120 / points_per_pixel  # For 120s

        i = 0
        while True:
            x = first - i * steplen
            if x < gsize[0][0]:
                break
            ctx.set_source_rgba(.5, .5, .5, .2)
            ctx.move_to(x, gsize[0][1])
            ctx.line_to(x, gsize[1][1])
            ctx.stroke()

            ctx.set_source_rgb(.5, .5, .5)
            ctx.move_to(x - round(self.font_size * 1.5), gsize[1][1] + round(self.font_size * 1.5))

            h = now.hour
            m = now.minute - (now.minute % 2) - i * 2
            if m < 0:
                h -= 1
                m += 60
                if h < 0:
                    h += 24
            ctx.set_font_size(self.font_size)
            ctx.show_text(f"{h:2}:{m:02}")
            ctx.stroke()
            i += 1 + self.max_length // 601

    def is_showing(self, device):
        return False if device not in self.store else self.store[device]['show']

    def set_showing(self, device, show=True):
        if device not in self.store:
            return
        self.store[device]['show'] = show
