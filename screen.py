#!/usr/bin/python

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

class KlipperScreen(Gtk.Window):
  """ Class for creating a screen for Klipper via HDMI """
  currentPanel = None
  
  def __init__(self):
      self.init_style()
      Gtk.Window.__init__(self)
      
      self.set_default_size(Gdk.Screen.get_width(Gdk.Screen.get_default()),Gdk.Screen.get_height(Gdk.Screen.get_default()))
      
      
      #self.splash_screen()
      self.main_panel()
      
      self.box = Gtk.Box(spacing=6)
      #self.add(self.box)

      self.button1 = Gtk.Button(label="Hello")
      self.button1.connect("clicked", self.on_button1_clicked)
      #self.box.pack_start(self.button1, True, True, 0)

      self.button2 = Gtk.Button(label="Goodbye")
      self.button2.connect("clicked", self.on_button2_clicked)
      #self.box.pack_start(self.button2, True, True, 0)
  
  def init_style(self):
    cssdata = ""
    with open ('/home/pi/style.css', 'r' ) as file:
      cssdata = file.read()
    
    style_provider = Gtk.CssProvider()
    style_provider.load_from_path("/home/pi/style.css")

    Gtk.StyleContext.add_provider_for_screen(
          Gdk.Screen.get_default(),
          style_provider,
          Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    
  def splash_screen(self):
    image = Gtk.Image()
    #TODO: update file reference
    image.set_from_file("/opt/printer/OctoScreen/styles/z-bolt/images/logo.png")
    
    #label = Gtk.Label()
    #label.set_text("Initializing printer...")
    label = Gtk.Button(label="Initializing printer...")
    label.connect("clicked", self.printer_initialize)
    
    main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
    main.pack_start(image, True, True, 10)
    main.pack_end(label, True, True, 10)
    
    box = Gtk.VBox()
    box.add(main)
    self.add(box)
    self.currentPanel = box
  
  def main_panel (self):
    box = Gtk.Box(spacing=6)
    
    box.add(self.gtk_ButtonImage("/opt/printer/OctoScreen/styles/z-bolt/images/home.svg", "Home"))
    box.add(self.gtk_ButtonImage("/opt/printer/OctoScreen/styles/z-bolt/images/filament.svg", "Filament"))
    self.add(box)
    self.currentPanel = box
    
  
  def gtk_ButtonImage (self, image, label):
    img = Gtk.Image.new_from_file(image)
    
    b = Gtk.Button(label=label)
    b.set_image(img)
    b.set_image_position(Gtk.PositionType.TOP)
    b.set_always_show_image(True)
    ctx = b.get_style_context()
    ctx.add_class("color1")
    #button.set_vertical_expand(True)
    #button.set_h_expand(True)
    return b
  
  def printer_initialize(self, widget):
    self.remove(self.currentPanel)
    self.main_panel()
  
  def on_button1_clicked(self, widget):
      print("Hello")

  def on_button2_clicked(self, widget):
      print("Goodbye")


win = KlipperScreen()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()


#win = KlipperScreen()
#win.connect("destroy", Gtk.main_quit)
#win.show_all()
#Gtk.main()

