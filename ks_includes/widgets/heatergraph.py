import datetime
import logging
import math

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, GLib
from cairo import Context as cairoContext


class HeaterGraph(Gtk.DrawingArea):
    def __init__(self, screen, printer, font_size, fullscreen=False, store=None):
        super().__init__()
        self._gtk = screen.gtk
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.get_style_context().add_class('heatergraph')
        self._screen = screen
        self.printer = printer
        self.store = {} if store is None else store
        self.connect('draw', self.draw_graph)
        self.add_events(Gdk.EventMask.TOUCH_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('button_press_event', screen.screensaver.reset_timeout)
        self.connect('button_press_event', self.event_cb)
        self.font_size = round(font_size * 0.75)
        self.fullscreen = fullscreen
        if fullscreen:
            GLib.timeout_add_seconds(1, self.update_graph)
        self.fs_graph = None
        self.max_temp = 0
        for section in self.printer.config:
            if "max_temp" in self.printer.get_config_section(section):
                self.max_temp = max(float(self.printer.get_config_section(section)["max_temp"]), self.max_temp)
        self.max_temp = min(self.max_temp, 999)

    def update_graph(self):
        self.queue_draw()
        return self.fullscreen

    def show_fullscreen_graph(self):
        self.fs_graph = HeaterGraph(self._screen, self.printer, self.font_size * 2, fullscreen=True, store=self.store)
        self._gtk.Dialog(_("Temperature"), None, self.fs_graph, self.close_fullscreen_graph)

    def close_fullscreen_graph(self, dialog, response_id):
        logging.info("Closing graph")
        self.fs_graph.fullscreen = False
        self._gtk.remove_dialog(dialog)

    def event_cb(self, da, ev):
        if self.fullscreen:
            logging.info(f"Graph area: {ev.x} {ev.y}")
        else:
            self.show_fullscreen_graph()
            logging.info("Entering Fullscreen")

    def add_object(self, name, ev_type, rgb=None, dashed=False, fill=False):
        rgb = [0, 0, 0] if rgb is None else rgb
        if name not in self.store:
            self.store.update({name: {"show": True}})
        self.store[name].update({ev_type: {
            "dashed": dashed,
            "fill": fill,
            "rgb": rgb
        }})

    def get_max_num(self, data_points=0):
        mnum = [0]
        for device in self.store:
            if self.store[device]['show']:
                temp = self.printer.get_temp_store(device, "temperatures", data_points)
                if isinstance(temp, list):
                    mnum.append(max(temp))
                target = self.printer.get_temp_store(device, "targets", data_points)
                if isinstance(target, list):
                    mnum.append(max(target))
        return max(mnum)

    def draw_graph(self, da: Gtk.DrawingArea, ctx: cairoContext):
        if not self.printer.tempstore:
            logging.info("Tempstore not initialized!")
            self._screen.init_tempstore()
            return
        x = round(self.font_size * 2.75)
        y = 10
        width = da.get_allocated_width() - 15
        height = da.get_allocated_height() - self.font_size * 2
        gsize = [[x, y], [width, height]]

        ctx.set_source_rgb(.5, .5, .5)
        ctx.set_line_width(1)
        ctx.set_tolerance(1)

        ctx.rectangle(x, y, width - x, height - y)

        graph_width = gsize[1][0] - gsize[0][0]
        points_per_pixel = self.printer.get_tempstore_size() / graph_width
        data_points = int(round(graph_width * points_per_pixel, 0))
        max_num = math.ceil(self.get_max_num(data_points) * 1.1 / 10) * 10
        if points_per_pixel == 0:
            logging.info(f"Data points: {data_points}")
            return
        d_width = 1 / points_per_pixel

        d_height_scale = self.graph_lines(ctx, gsize, max_num)
        self.graph_time(ctx, gsize, points_per_pixel)

        for name in self.store:
            if not self.store[name]['show']:
                continue
            for dev_type in self.store[name]:
                if d := self.printer.get_temp_store(name, dev_type, data_points):
                    self.graph_data(
                        ctx, d, gsize, d_height_scale, d_width, self.store[name][dev_type]["rgb"],
                        self.store[name][dev_type]["dashed"], self.store[name][dev_type]["fill"]
                    )

    @staticmethod
    def graph_data(ctx: cairoContext, data, gsize, hscale, swidth, rgb, dashed=False, fill=False):
        if fill:
            ctx.set_source_rgba(rgb[0], rgb[1], rgb[2], .25)
            ctx.set_dash([1, 0])
        elif dashed:
            ctx.set_source_rgba(rgb[0], rgb[1], rgb[2], .5)
            ctx.set_dash([10, 5])
        else:
            ctx.set_source_rgba(rgb[0], rgb[1], rgb[2], 1)
            ctx.set_dash([1, 0])
        d_len = len(data) - 1

        for i, d in enumerate(data):
            p_x = i * swidth + gsize[0][0] if i != d_len else gsize[1][0] - 1
            if dashed:  # d between 0 and 1
                p_y = gsize[1][1] - (d * (gsize[1][1] - gsize[0][1]))
            else:
                p_y = max(gsize[0][1], min(gsize[1][1], gsize[1][1] - 1 - (d * hscale)))
            if i == 0:
                ctx.move_to(gsize[0][0], p_y)
            ctx.line_to(p_x, p_y)
        if fill:
            ctx.stroke_preserve()
            ctx.line_to(gsize[1][0] - 1, gsize[1][1] - 1)
            ctx.line_to(gsize[0][0] + 1, gsize[1][1] - 1)
            ctx.fill()
        else:
            ctx.stroke()

    def graph_lines(self, ctx: cairoContext, gsize, max_num):
        nscale = 10
        max_num = min(max_num, self.max_temp)
        while (max_num / nscale) > 5:
            nscale += 10
        r = int(max_num / nscale) + 1
        hscale = (gsize[1][1] - gsize[0][1]) / (r * nscale)
        ctx.set_font_size(self.font_size)

        for i in range(r):
            ctx.set_source_rgb(.5, .5, .5)
            lheight = gsize[1][1] - nscale * i * hscale
            ctx.move_to(6, lheight + 3)
            ctx.show_text(str(nscale * i).rjust(3, " "))
            ctx.stroke()
            ctx.set_source_rgba(.5, .5, .5, .2)
            ctx.move_to(gsize[0][0], lheight)
            ctx.line_to(gsize[1][0], lheight)
            ctx.stroke()
        return hscale

    def graph_time(self, ctx: cairoContext, gsize, points_per_pixel):

        now = datetime.datetime.now()
        first = gsize[1][0] - (now.second + ((now.minute % 2) * 60)) / points_per_pixel
        steplen = 120 / points_per_pixel  # For 120s

        font_size_multiplier = round(self.font_size * 1.5)
        ctx.set_font_size(self.font_size)

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
            ctx.move_to(x - font_size_multiplier, gsize[1][1] + font_size_multiplier)

            ctx.show_text(f"{now - datetime.timedelta(minutes=2) * i:%H:%M}")
            ctx.stroke()
            i += 1 + self.printer.get_tempstore_size() // 601

    def is_showing(self, device):
        return False if device not in self.store else self.store[device]['show']

    def set_showing(self, device, show=True):
        if device not in self.store:
            return
        self.store[device]['show'] = show
