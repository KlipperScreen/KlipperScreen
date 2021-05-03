# -*- coding: utf-8 -*-
import gi
import logging

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib, Pango
import os
klipperscreendir = os.getcwd()

class KlippyGtk:
    labels = {}
    font_ratio = [51, 30]
    width_ratio = 16
    height_ratio = 9.375

    def __init__(self, screen, width, height, theme):
        self.screen = screen

        self.width = width
        self.height = height
        self.theme = theme
        self.font_size = int(min(
            self.width / self.font_ratio[0],
            self.height / self.font_ratio[1]
        ))
        self.header_size = int(round((self.width / self.width_ratio) / 1.33))
        self.img_width = int(round(self.width / self.width_ratio))
        self.img_height = int(round(self.height / self.height_ratio))
        self.action_bar_width = int(self.width * .1)
        self.header_image_scale_width = 1.2
        self.header_image_scale_height = 1.4

        logging.debug("img width: %s height: %s" % (self.img_width, self.img_height))

    def get_action_bar_width(self):
        return self.action_bar_width

    def get_content_width(self):
        return self.width - self.action_bar_width

    def get_content_height(self):
        return self.height - self.header_size

    def get_header_size(self):
        return self.header_size

    def get_header_image_scale(self):
        return [self.header_image_scale_width, self.header_image_scale_height]

    def get_image_width(self):
        return self.img_width

    def get_image_height(self):
        return self.img_height

    def get_font_size(self):
        return self.font_size

    def Label(self, label, style=None):
        l = Gtk.Label(label)
        if style != None and style != False:
            l.get_style_context().add_class(style)
        return l

    def ImageLabel(self, image_name, text, size=20, style=False, width_scale=.32, height_scale=.32):
        box1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            "%s/styles/%s/images/%s.svg" % (klipperscreendir, self.theme, str(image_name)),
            int(round(self.img_width * width_scale)), int(round(self.img_height * height_scale)), True)

        image = Gtk.Image.new_from_pixbuf(pixbuf)

        label = Gtk.Label()
        label.set_text(text)
        box1.add(image)
        box1.add(label)

        if style != False:
            ctx = box1.get_style_context()
            ctx.add_class(style)

        return {"l": label, "b": box1}

    def Image(self, image_name, style=False, width_scale=1, height_scale=1):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            "%s/styles/%s/images/%s" % (klipperscreendir, self.theme, str(image_name)),
            int(round(self.img_width * width_scale)), int(round(self.img_height * height_scale)), True)

        return Gtk.Image.new_from_pixbuf(pixbuf)

    def ImageFromFile(self, filename, style=False, width_scale=1, height_scale=1):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename,
            int(round(self.img_width * width_scale)), int(round(self.img_height * height_scale)), True)

        return Gtk.Image.new_from_pixbuf(pixbuf)

    def PixbufFromFile(self, filename, style=False, width_scale=1, height_scale=1):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename, int(round(self.img_width * width_scale)),
            int(round(self.img_height * height_scale)), True)

        return pixbuf

    def PixbufFromHttp(self, resource, style=False, width_scale=1, height_scale=1):
        response = self.screen.apiclient.get_thumbnail_stream(resource)
        if response == False:
            return None
        stream = Gio.MemoryInputStream.new_from_data(response, None)
        pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, int(round(self.img_width * width_scale)),
            int(round(self.img_height * height_scale)), True)

        return pixbuf

    def ProgressBar(self, style=False):
        bar = Gtk.ProgressBar()

        if style != False:
            ctx = bar.get_style_context()
            ctx.add_class(style)

        return bar

    def Button(self, label=None, style=None):
        b = Gtk.Button(label=label)
        b.set_hexpand(True)
        b.set_vexpand(True)
        b.set_can_focus(False)
        b.props.relief = Gtk.ReliefStyle.NONE

        if style != None:
            b.get_style_context().add_class(style)

        return b

    def ButtonImage(self, image_name, label=None, style=None, width_scale=1, height_scale=1,
            position=Gtk.PositionType.TOP, word_wrap=True):
        filename = "%s/styles/%s/images/%s.svg" % (klipperscreendir, self.theme, str(image_name))
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            filename,
            int(round(self.img_width * width_scale)),
            int(round(self.img_height * height_scale)),
            True
        )

        img = Gtk.Image.new_from_pixbuf(pixbuf)

        b = Gtk.Button(label=label)
        b.set_image(img)
        b.set_hexpand(True)
        b.set_vexpand(True)
        b.set_can_focus(False)
        b.set_image_position(position)
        b.set_always_show_image(True)
        b.props.relief = Gtk.ReliefStyle.NONE

        if word_wrap is True:
            try:
                # Get the label object
                child = b.get_children()[0].get_children()[0].get_children()[1]
                child.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                child.set_line_wrap(True)
            except:
                pass

        if style != None:
            b.get_style_context().add_class(style)

        return b

    def Dialog(self, screen, buttons, content, callback=None, *args):
        dialog = Gtk.Dialog()
        dialog.set_default_size(screen.width - 15, screen.height - 15)
        dialog.set_resizable(False)
        dialog.set_transient_for(screen)
        dialog.set_modal(True)

        for button in buttons:
            dialog.add_button(button_text=button['name'], response_id=button['response'])

        dialog.connect("response", callback, *args)
        dialog.get_style_context().add_class("dialog")

        grid = Gtk.Grid()
        grid.set_size_request(screen.width - 60, -1)
        grid.set_vexpand(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        grid.add(content)

        content_area = dialog.get_content_area()
        content_area.set_margin_start(15)
        content_area.set_margin_end(15)
        content_area.set_margin_top(15)
        content_area.set_margin_bottom(15)
        content_area.add(grid)

        dialog.show_all()

        return dialog, grid


    def ToggleButtonImage(self, image_name, label, style=False, width_scale=1, height_scale=1):
        filename = "%s/styles/%s/images/%s.svg" % (klipperscreendir, self.theme, str(image_name))
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            filename,
            int(round(self.img_width * width_scale)),
            int(round(self.img_height * height_scale)),
            True
        )

        img = Gtk.Image.new_from_pixbuf(pixbuf)

        b = Gtk.ToggleButton(label=label)
        #b.props.relief = Gtk.RELIEF_NONE
        b.set_image(img)
        b.set_hexpand(True)
        b.set_vexpand(True)
        b.set_can_focus(False)
        b.set_image_position(Gtk.PositionType.TOP)
        b.set_always_show_image(True)
        b.props.relief = Gtk.ReliefStyle.NONE

        if style != False:
            ctx = b.get_style_context()
            ctx.add_class(style)

        return b

    def HomogeneousGrid(self, width=None, height=None):
        g = Gtk.Grid()
        g.set_row_homogeneous(True)
        g.set_column_homogeneous(True)
        if width != None and height != None:
            g.set_size_request(width, height)
        return g

    def ToggleButton(self, text):
        b = Gtk.ToggleButton(text)
        b.props.relief = Gtk.ReliefStyle.NONE
        b.set_hexpand(True)
        b.set_vexpand(True)
        return b

    def formatFileName(self, name):
        name = name.split('/')[-1] if "/" in name else name
        name = name.split('.gcod')[0] if ".gcode" in name else name
        if len(name) > 25:
            return name[0:25] + "\n" + name[25:50]
        return name


    def formatTimeString(self, seconds):
        time = int(seconds)
        text = ""
        if int(time/3600) !=0:
            text += str(int(time/3600))+"h "
        text += str(int(time/60)%60)+"m "+str(time%60)+"s"
        return text

    def formatTemperatureString(self, temp, target):
        if (target > temp-2 and target < temp+2) or round(target,0) == 0:
            return str(round(temp,1)) + "°C" #°C →"
        return str(round(temp)) + " → " + str(round(target)) + "°C"
