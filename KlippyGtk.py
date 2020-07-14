# -*- coding: utf-8 -*-
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

class KlippyGtk:
    labels = {}

    #def __init__ (self):

    @staticmethod
    def ImageLabel(image_name, text, size=20, style=False):
        box1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        image = Gtk.Image()
        #TODO: update file reference
        image.set_from_file("/opt/printer/OctoScreen/styles/z-bolt/images/" + str(image_name) + ".svg")

        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale("/opt/printer/OctoScreen/styles/z-bolt/images/" + str(image_name) + ".svg", 20, 20, True)
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
    def ProgressBar(style=False):
        bar = Gtk.ProgressBar()

        if style != False:
            print "Styling bar " + style
            ctx = bar.get_style_context()
            ctx.add_class(style)

        return bar

    @staticmethod
    def ButtonImage(image_name, label, style=False):
        img = Gtk.Image.new_from_file("/opt/printer/OctoScreen/styles/z-bolt/images/" + str(image_name) + ".svg")

        b = Gtk.Button(label=label)
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
        if time/3600 !=0:
            text += str(time/3600)+"h "
        text += str(time/60%60)+"m "+str(time%60)+"s"
        return text

    @staticmethod
    def formatTemperatureString(temp, target):
        if (target > temp-2 and target < temp+2) or round(target,0) == 0:
            return str(round(temp,2)) + "°C" #°C →"
        return str(round(temp,2)) + "°C  → " + str(round(target,2)) + "°C"
