import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.autogrid import AutoGrid
from ks_includes.KlippyGtk import find_widget


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Printer Select")
        super().__init__(screen, title)
        printers = self._config.get_printers()

        self.printer_buttons = []
        for i, printer in enumerate(printers):
            name = list(printer)[0]
            scale = 3
            self.labels[name] = self._gtk.Button("printer", name, f"color{1 + i % 4}", scale=scale)
            scale *= self._gtk.img_scale
            pixbuf = self._gtk.PixbufFromIcon(f"../../printers/{name}", scale, scale)
            if pixbuf is not None:
                image = find_widget(self.labels[name], Gtk.Image)
                image.set_from_pixbuf(pixbuf)
            self.labels[name].connect("clicked", self.connect_printer, name)
            self.printer_buttons.append(self.labels[name])
        grid = AutoGrid(self.printer_buttons, vertical=self._screen.vertical_mode)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(grid)
        self.content.add(scroll)

    def connect_printer(self, widget, name):
        self._screen.connect_printer(name)

    def activate(self):
        if self._screen._ws and self._screen._ws.connected:
            self._screen.close_websocket()
            logging.debug("Waiting for disconnect")
            self._screen.base_panel.set_title(_("Please wait"))
            b: Gtk.Button
            for b in self.printer_buttons:
                b.set_sensitive(False)

    def disconnected_callback(self):
        logging.debug("Disconnected. Enabling buttons")
        self._screen.base_panel.set_title(_("Printer Select"))
        for b in self.printer_buttons:
            b.set_sensitive(True)
