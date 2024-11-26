import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk


class Prompt:
    def __init__(self, screen):
        self.screen = screen
        self.gtk = screen.gtk
        self.window_title = 'KlipperScreen'
        self.text = self.header = ""
        self.buttons = []
        self.id = 1
        self.prompt = None
        self.scroll_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
        )
        self.groups = []

    def _key_press_event(self, widget, event):
        keyval_name = Gdk.keyval_name(event.keyval)
        if keyval_name in ["Escape", "BackSpace"]:
            self.close()

    def decode(self, data):
        logging.info(f'{data}')
        if data.startswith('prompt_begin'):
            self.header = data.replace('prompt_begin', '')
            if self.header:
                self.window_title = self.header
            self.text = ""
            self.buttons = []
            return
        elif data.startswith('prompt_text'):
            self.text = data.replace('prompt_text ', '')
            return
        elif data.startswith('prompt_button '):
            data = data.replace('prompt_button ', '')
            params = data.split('|')
            if len(params) == 1:
                params.append(self.text)
            if len(params) > 3:
                logging.error('Unexpected number of parameters on the button')
                return
            self.set_button(*params)
            return
        elif data.startswith('prompt_footer_button'):
            data = data.replace('prompt_footer_button ', '')
            params = data.split('|')
            if len(params) == 1:
                params.append(self.text)
            if len(params) > 3:
                logging.error('Unexpected number of parameters on the button')
                return
            self.set_footer_button(*params)
            return
        elif data == 'prompt_show':
            if not self.prompt:
                self.show()
            return
        elif data == 'prompt_end':
            self.end()
        elif data == 'prompt_button_group_start':
            self.groups.append(
                Gtk.FlowBox(
                    selection_mode=Gtk.SelectionMode.NONE,
                    orientation=Gtk.Orientation.HORIZONTAL,
                )
            )
        elif data == 'prompt_button_group_end':
            if self.groups:
                self.scroll_box.add(self.groups.pop())
        else:
            logging.debug(f'Unknown option {data}')

    def set_button(self, name, gcode, style='default'):
        button = self.gtk.Button(image_name=None, label=f"{name}", style=f'dialog-{style}')
        button.connect("clicked", self.screen._send_action, "printer.gcode.script", {'script': gcode})
        if self.groups:
            self.groups[-1].add(button)
            # Workaround to expand the buttons horizontally
            max_childs = len(self.groups[-1].get_children())
            self.groups[-1].set_max_children_per_line(min(4, max_childs))
            self.groups[-1].set_min_children_per_line(min(4, max_childs))
        else:
            self.scroll_box.add(button)

    def set_footer_button(self, name, gcode, style='default'):
        self.buttons.append(
            {"name": name, "response": self.id, 'gcode': gcode, 'style': f'dialog-{style}'}
        )
        self.id += 1

    def show(self):
        logging.info(f'Prompt {self.header} {self.text} {self.buttons}')

        title = Gtk.Label(wrap=True, hexpand=True, vexpand=False, halign=Gtk.Align.CENTER, label=self.header)

        close = self.gtk.Button("cancel", scale=self.gtk.bsidescale)
        close.set_hexpand(False)
        close.set_vexpand(False)
        close.connect("clicked", self.close)

        label = Gtk.Label(label=self.text, wrap=True, hexpand=True, vexpand=True)

        self.scroll_box.add(label)
        self.scroll_box.reorder_child(label, 0)

        scroll = self.gtk.ScrolledWindow(steppers=False)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.scroll_box)

        content = Gtk.Grid()
        if not self.screen.get_resizable():
            content.attach(title, 0, 0, 1, 1)
            content.attach(close, 1, 0, 1, 1)
        content.attach(scroll, 0, 1, 2, 1)

        self.prompt = self.gtk.Dialog(
            self.window_title,
            self.buttons,
            content,
            self.response,
        )
        self.prompt.connect("key-press-event", self._key_press_event)
        self.prompt.connect("delete-event", self.close)
        self.screen.wake_screen()

    def response(self, dialog, response_id):
        for button in self.buttons:
            if button['response'] == response_id:
                self.screen._send_action(None, "printer.gcode.script", {'script': button['gcode']})

    def close(self, *args):
        script = {'script': 'RESPOND type="command" msg="action:prompt_end"'}
        self.screen._send_action(None, "printer.gcode.script", script)

    def end(self):
        if self.prompt is not None:
            self.gtk.remove_dialog(self.prompt)
        self.prompt = None
        self.screen.prompt = None
