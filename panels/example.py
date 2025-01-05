import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Example")
        super().__init__(screen, title)

        # Create a vertical box to hold the buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        button_box.set_margin_top(20)
        button_box.set_margin_bottom(20)
        button_box.set_margin_start(20)
        button_box.set_margin_end(20)

        # Create Button 1
        button1 = Gtk.Button(label="Button 1")
        button1.connect("clicked", self.on_button1_clicked)
        button_box.pack_start(button1, True, True, 0)

        # Create Button 2
        button2 = Gtk.Button(label="Button 2")
        button2.connect("clicked", self.on_button2_clicked)
        button_box.pack_start(button2, True, True, 0)

        # Create Button 3
        button3 = Gtk.Button(label="Button 3")
        button3.connect("clicked", self.on_button3_clicked)
        button_box.pack_start(button3, True, True, 0)

        # Add the button box to the panel
        self.content.add(button_box)

    def on_button1_clicked(self, widget):
        print("Button 1 clicked")

    def on_button2_clicked(self, widget):
        print("Button 2 clicked")

    def on_button3_clicked(self, widget):
        print("Button 3 clicked")
