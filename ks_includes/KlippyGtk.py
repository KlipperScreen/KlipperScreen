# -*- coding: utf-8 -*-
import logging
import os
import pathlib

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk, Pango
from ks_includes.widgets.scroll import CustomScrolledWindow


def find_widget(widget, wanted_type):
    # Returns a widget of wanted_type or None
    if isinstance(widget, wanted_type):
        return widget
    if isinstance(widget, (Gtk.Container, Gtk.Bin, Gtk.Button, Gtk.Alignment, Gtk.Box)):
        for _ in widget.get_children():
            result = find_widget(_, wanted_type)
            if result is not None:
                return result


def format_label(widget, lines=2):
    label = find_widget(widget, Gtk.Label)
    if label is not None:
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_line_wrap(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_lines(lines)


class KlippyGtk:
    labels = {}

    def __init__(self, screen):
        self.screen = screen
        self.themedir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", screen.theme, "images")
        self.font_size_type = screen._config.get_main_config().get("font_size", "medium")
        self.width = screen.width
        self.height = screen.height
        self.ultra_tall = (self.height / self.width) >= 3
        self.font_ratio = [28, 42] if self.screen.vertical_mode else [40, 27]
        self.font_size = min(self.width / self.font_ratio[0], self.height / self.font_ratio[1])
        self.img_scale = self.font_size * 2
        self.button_image_scale = 1.38
        self.bsidescale = .65  # Buttons with image at the side
        self.dialog_buttons_height = round(self.height / 5)

        if self.font_size_type == "max":
            self.font_size = self.font_size * 1.06
            self.img_scale = self.img_scale * 0.7
            self.bsidescale = .7
        elif self.font_size_type == "extralarge":
            self.font_size = self.font_size * 1.05
            self.img_scale = self.img_scale * 0.7
            self.bsidescale = 1.0
        elif self.font_size_type == "large":
            self.font_size = self.font_size * 1.025
            self.img_scale = self.img_scale * 0.85
            self.bsidescale = .8
        elif self.font_size_type == "small":
            self.font_size = self.font_size * 0.91
            self.bsidescale = .55
        self.img_width = self.font_size * 3
        self.img_height = self.font_size * 3
        self.titlebar_height = self.font_size * 2
        logging.info(f"Font size: {self.font_size:.1f} ({self.font_size_type})")

        if self.screen.vertical_mode:
            self.action_bar_width = int(self.width)
            self.action_bar_height = int(self.height * .1)
            self.content_width = self.width
            self.content_height = self.height - self.titlebar_height - self.action_bar_height
        else:
            self.action_bar_width = int(self.width * .1)
            self.action_bar_height = int(self.height)
            self.content_width = self.width - self.action_bar_width
            self.content_height = self.height - self.titlebar_height

        self.keyboard_height = self.content_height * 0.5
        if self.ultra_tall:
            self.keyboard_height = self.keyboard_height * 0.5

        self.color_list = {}  # This is set by screen.py init_style()
        for key in self.color_list:
            if "base" in self.color_list[key]:
                rgb = [int(self.color_list[key]['base'][i:i + 2], 16) for i in range(0, 6, 2)]
                self.color_list[key]['rgb'] = rgb

    def get_temp_color(self, device):
        # logging.debug("Color list %s" % self.color_list)
        if device not in self.color_list:
            return False, False

        if 'base' in self.color_list[device]:
            rgb = self.color_list[device]['rgb'].copy()
            if self.color_list[device]['state'] > 0:
                rgb[1] = rgb[1] + self.color_list[device]['hsplit'] * self.color_list[device]['state']
            self.color_list[device]['state'] += 1
            rgb = [x / 255 for x in rgb]
            # logging.debug(f"Assigning color: {device} {rgb}")
        else:
            colors = self.color_list[device]['colors']
            if self.color_list[device]['state'] >= len(colors):
                self.color_list[device]['state'] = 0
            color = colors[self.color_list[device]['state'] % len(colors)]
            rgb = [int(color[i:i + 2], 16) / 255 for i in range(0, 6, 2)]
            self.color_list[device]['state'] += 1
            # logging.debug(f"Assigning color: {device} {rgb} {color}")
        return rgb

    def reset_temp_color(self):
        for key in self.color_list:
            self.color_list[key]['state'] = 0

    def Image(self, image_name=None, width=None, height=None):
        if image_name is None:
            return Gtk.Image()
        pixbuf = self.PixbufFromIcon(image_name, width, height)
        return Gtk.Image.new_from_pixbuf(pixbuf) if pixbuf is not None else Gtk.Image()

    def update_themedir(self, theme):
        self.themedir = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "styles", theme, "images")

    def PixbufFromIcon(self, filename, width=None, height=None):
        width = width if width is not None else self.img_width
        height = height if height is not None else self.img_height
        filename = os.path.join(self.themedir, filename)
        for ext in ["svg", "png"]:
            file = f"{filename}.{ext}"
            pixbuf = self.PixbufFromFile(file, int(width), int(height)) if os.path.exists(file) else None
            if pixbuf is not None:
                return pixbuf
        return None

    @staticmethod
    def PixbufFromFile(filename, width=-1, height=-1):
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_size(filename, int(width), int(height))
        except Exception as e:
            logging.exception(e)
            logging.error(f"Unable to find image {filename}")
            return None

    def PixbufFromHttp(self, resource, width=-1, height=-1):
        response = self.screen.apiclient.get_thumbnail_stream(resource)
        if response is False:
            return None
        stream = Gio.MemoryInputStream.new_from_data(response, None)
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(stream, int(width), int(height), True)
        except Exception as e:
            logging.exception(e)
            return None
        stream.close_async(2)
        return pixbuf

    def Button(self, image_name=None, label=None, style=None, scale=None, position=Gtk.PositionType.TOP, lines=2):
        if self.font_size_type == "max" and label is not None:
            image_name = None
        b = Gtk.Button(hexpand=True, vexpand=True, can_focus=False, image_position=position, always_show_image=True)
        if label is not None:
            b.set_label(label.replace("\n", " "))
        if image_name is not None:
            b.set_name(image_name)
            if scale is None:
                scale = self.button_image_scale
            if label is None:
                scale = scale * 1.4
            width = height = self.img_scale * scale
            b.set_image(self.Image(image_name, width, height))
            spinner = Gtk.Spinner(width_request=width, height_request=height, no_show_all=True)
            spinner.hide()
            box = find_widget(b, Gtk.Box)
            if box:
                box.add(spinner)

        if label is not None:
            format_label(b, lines)
        if style is not None:
            b.get_style_context().add_class(style)
        b.connect("clicked", self.screen.screensaver.reset_timeout)
        return b

    @staticmethod
    def Button_busy(widget, busy):
        spinner = find_widget(widget, Gtk.Spinner)
        image = find_widget(widget, Gtk.Image)
        if busy:
            widget.set_sensitive(False)
            if image:
                widget.set_always_show_image(False)
                image.hide()
            if spinner:
                spinner.start()
                spinner.show()
        else:
            if image:
                widget.set_always_show_image(True)
                image.show()
            if spinner:
                spinner.stop()
                spinner.hide()
            widget.set_sensitive(True)

    def dialog_content_decouple(self, widget, event, dialog):
        self.remove_dialog(dialog)

    def Dialog(self, title, buttons, content, callback=None, *args):
        dialog = Gtk.Dialog(title=title, modal=True, transient_for=self.screen,
                            default_width=self.width, default_height=self.height)
        dialog.set_size_request(self.width, self.height)
        if not self.screen.get_resizable():
            dialog.fullscreen()

        if buttons:
            max_buttons = 4
            if len(buttons) > max_buttons:
                buttons = buttons[:max_buttons]
            if len(buttons) > 2:
                dialog.get_action_area().set_layout(Gtk.ButtonBoxStyle.EXPAND)
                button_hsize = -1
            else:
                button_hsize = int((self.width / 3))
            for button in buttons:
                style = button['style'] if 'style' in button else 'dialog-default'
                dialog.add_button(button['name'], button['response'])
                button = dialog.get_widget_for_response(button['response'])
                button.set_size_request(button_hsize, self.dialog_buttons_height)
                button.get_style_context().add_class(style)
                format_label(button, 2)
        else:
            # No buttons means clicking anywhere closes the dialog
            content.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
            content.connect("button-release-event", self.dialog_content_decouple, dialog)
            dialog.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
            dialog.connect("button-release-event", self.remove_dialog)

        dialog.connect("response", self.screen.screensaver.reset_timeout)
        dialog.connect("response", callback, *args)
        dialog.get_style_context().add_class("dialog")

        content_area = dialog.get_content_area()
        content_area.set_margin_start(10)
        content_area.set_margin_end(5)
        content_area.set_margin_top(5)
        content_area.set_margin_bottom(0)
        content_area.add(content)

        dialog.show_all()
        # Change cursor to blank
        self.set_cursor(show=self.screen.show_cursor, window=dialog.get_window())

        self.screen.dialogs.append(dialog)
        logging.info(f"Showing dialog {dialog.get_title()} {dialog.get_size()}")
        return dialog

    def remove_dialog(self, dialog, *args):
        if not isinstance(dialog, Gtk.Dialog):
            logging.error(f"Invalid dialog: {dialog}")
            return
        if self.screen.updating:
            return
        if dialog == self.screen.confirm:
            self.screen.confirm = None
        dialog.destroy()
        if dialog in self.screen.dialogs:
            logging.info("Removing Dialog")
            self.screen.dialogs.remove(dialog)
            return
        logging.debug(f"Cannot remove dialog {dialog}")

    def ScrolledWindow(self, steppers=True, **kwargs):
        steppers = steppers and self.screen._config.get_main_config().getboolean("show_scroll_steppers", fallback=False)
        return CustomScrolledWindow(steppers, **kwargs)

    def set_cursor(self, show: bool, window: Gdk.Window):
        if show:
            window.set_cursor(
                Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.ARROW))
            os.system("xsetroot  -cursor_name  arrow")
        else:
            window.set_cursor(
                Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.BLANK_CURSOR))
            os.system("xsetroot  -cursor ks_includes/emptyCursor.xbm ks_includes/emptyCursor.xbm")
