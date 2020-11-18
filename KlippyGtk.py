# -*- coding: utf-8 -*-
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import os
klipperscreendir = os.getcwd()

class KlippyGtk:
    labels = {}

    @staticmethod
    def Label(label, style):
        l = Gtk.Label(label)
        if style != False:
            l.get_style_context().add_class(style)
        return l

    @staticmethod
    def ImageLabel(image_name, text, size=20, style=False):
        box1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        image = Gtk.Image()
        #TODO: update file reference
        image.set_from_file(klipperscreendir + "/styles/z-bolt/images/" + str(image_name) + ".svg")

        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(klipperscreendir + "/styles/z-bolt/images/" + str(image_name) + ".svg", 20, 20, True)
        image.set_from_pixbuf(pixbuf)

        label = Gtk.Label()
        label.set_text(text)
        box1.add(image) #, size, size)
        box1.add(label)

        if style != False:
            ctx = box1.get_style_context()
            ctx.add_class(style)

        return {"l": label, "b": box1}

    @staticmethod
    def Image(image_name, style=False, width=None, height=None):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(klipperscreendir + "/styles/z-bolt/images/" + str(image_name) + ".svg")

        if height != None and width != None:
            pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)

        return Gtk.Image.new_from_pixbuf(pixbuf)

    @staticmethod
    def ImageFromFile(filename, style=False, width=None, height=None):
        if height != -1 or width != -1:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename, width, height, True)
        else:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)

        return Gtk.Image.new_from_pixbuf(pixbuf)

    @staticmethod
    def PixbufFromFile(filename, style=False, width=None, height=None):
        if height != -1 or width != -1:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename, width, height, True)
        else:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(filename)

        return pixbuf

    @staticmethod
    def ProgressBar(style=False):
        bar = Gtk.ProgressBar()

        if style != False:
            ctx = bar.get_style_context()
            ctx.add_class(style)

        return bar

    @staticmethod
    def Button(label=None, style=None):
        b = Gtk.Button(label=label)
        b.set_hexpand(True)
        b.set_vexpand(True)
        b.set_can_focus(False)
        b.props.relief = Gtk.ReliefStyle.NONE

        if style != None:
            b.get_style_context().add_class(style)

        return b

    @staticmethod
    def ButtonImage(image_name, label=None, style=None, height=None, width=None):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(klipperscreendir + "/styles/z-bolt/images/" + str(image_name) + ".svg")

        if height != None and width != None:
            pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)


        img = Gtk.Image.new_from_pixbuf(pixbuf)

        b = Gtk.Button(label=label)
        b.set_image(img)
        b.set_hexpand(True)
        b.set_vexpand(True)
        b.set_can_focus(False)
        b.set_image_position(Gtk.PositionType.TOP)
        b.set_always_show_image(True)
        b.props.relief = Gtk.ReliefStyle.NONE

        if style != None:
            b.get_style_context().add_class(style)

        return b

    @staticmethod
    def Dialog(screen, buttons, content, callback=None, *args):
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


    @staticmethod
    def ToggleButtonImage(image_name, label, style=False):
        img = Gtk.Image.new_from_file(klipperscreendir + "/styles/z-bolt/images/" + str(image_name) + ".svg")

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

    @staticmethod
    def HomogeneousGrid():
        g = Gtk.Grid()
        g.set_row_homogeneous(True)
        g.set_column_homogeneous(True)
        return g

    @staticmethod
    def ToggleButton(text):
        b = Gtk.ToggleButton(text)
        b.props.relief = Gtk.ReliefStyle.NONE
        b.set_hexpand(True)
        b.set_vexpand(True)
        return b

    @staticmethod
    def formatFileName(name):
        name = name.split('/')[-1] if "/" in name else name
        name = name.split('.gcod')[0] if ".gcode" in name else name
        if len(name) > 25:
            return name[0:25] + "\n" + name[25:50]
        return name


    @staticmethod
    def formatTimeString(seconds):
        time = int(seconds)
        text = ""
        if int(time/3600) !=0:
            text += str(int(time/3600))+"h "
        text += str(int(time/60)%60)+"m "+str(time%60)+"s"
        return text

    @staticmethod
    def formatTemperatureString(temp, target):
        if (target > temp-2 and target < temp+2) or round(target,0) == 0:
            return str(round(temp,2)) + "°C" #°C →"
        return str(round(temp)) + " → " + str(round(target)) + "°C"
