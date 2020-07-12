import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

class KlippyGtk:
    labels = {}

    #def __init__ (self):

    @staticmethod
    def ImageLabel(image_name, text):
        box1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, relief=2)
        image = Gtk.Image()
        #TODO: update file reference
        image.set_from_file("/opt/printer/OctoScreen/styles/z-bolt/images/" + str(image_name) + ".svg")
        label = Gtk.Label()
        label.set_text(text)
        box1.add(image)
        box1.add(label)
        return box1

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

        if style != False:
            ctx = b.get_style_context()
            ctx.add_class(style)

        return b

    @staticmethod
    def formatTemperatureString(temp, target):
        if (target > temp-2 and target < temp+2) or round(target,0) == 0:
            return str(round(temp,2)) + "C"
        return str(round(temp,2)) + "C -> " + str(round(target,2)) + "C"
