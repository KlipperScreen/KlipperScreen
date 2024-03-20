import logging
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.update_status = None
        self.system_info = self._screen.apiclient.send_request("machine/system_info")

        self.update_all = self._gtk.Button('arrow-up', _('Full Update'), 'color1', self.bts, Gtk.PositionType.LEFT, 1)
        self.update_all.connect("clicked", self.show_update_info, "full")
        self.update_all.set_vexpand(False)
        self.refresh = self._gtk.Button('arrow-down', _('Refresh'), 'color3', self.bts, Gtk.PositionType.LEFT, 1)
        self.refresh.connect("clicked", self.refresh_updates)
        self.refresh.set_vexpand(False)

        sbox = Gtk.Box(vexpand=False)
        sbox.pack_start(self.update_all, True, True, 0)
        sbox.pack_start(self.refresh, True, True, 0)

        self.update_msg = Gtk.Label(label=_("Checking for updates, please wait..."), vexpand=True)

        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(self.update_msg)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.main_box.pack_start(sbox, False, False, 0)
        self.main_box.pack_start(self.scroll, True, True, 0)

        self.content.add(self.main_box)

    def activate(self):
        self._screen._ws.send_method('machine.update.status', callback=self.get_updates)

    def create_info_grid(self):
        infogrid = Gtk.Grid()
        infogrid.get_style_context().add_class("system-program-grid")
        for i, prog in enumerate(sorted(list(self.update_status['version_info']))):
            self.labels[prog] = Gtk.Label(hexpand=True, halign=Gtk.Align.START, ellipsize=Pango.EllipsizeMode.END)

            self.labels[f"{prog}_status"] = self._gtk.Button()
            self.labels[f"{prog}_status"].set_hexpand(False)
            self.labels[f"{prog}_status"].connect("clicked", self.show_update_info, prog)

            try:
                if prog in self.system_info['result']['system_info']['available_services']:
                    self.labels[f"{prog}_restart"] = self._gtk.Button("refresh", _("Restart"),
                                                                      "color2",
                                                                      position=Gtk.PositionType.LEFT,
                                                                      scale=self.bts)
                    self.labels[f"{prog}_restart"].connect("clicked", self.restart, prog)
                    infogrid.attach(self.labels[f"{prog}_restart"], 0, i, 1, 1)
            except Exception as e:
                logging.exception(e)

            infogrid.attach(self.labels[prog], 1, i, 1, 1)
            self.labels[prog].get_style_context().add_class('updater-item')

            infogrid.attach(self.labels[f"{prog}_status"], 2, i, 1, 1)
            self.update_program_info(prog)
        self.clear_scroll()
        self.scroll.add(infogrid)

    def clear_scroll(self):
        for child in self.scroll.get_children():
            self.scroll.remove(child)

    def refresh_updates(self, widget=None):
        self.clear_scroll()
        self.scroll.add(self.update_msg)
        self._gtk.Button_busy(widget, True)
        logging.info('Sending machine.update.refresh')
        self._screen._ws.send_method('machine.update.refresh', callback=self.get_updates)

    def get_updates(self, response, method, params):
        self._gtk.Button_busy(self.refresh, False)
        logging.info(response)
        if not response or 'result' not in response:
            self.update_all.set_sensitive(False)
            self.clear_scroll()
            if 'error' in response:
                self.scroll.add(Gtk.Label(label=f"Moonraker: {response['error']['message']}", vexpand=True))
            else:
                self.scroll.add(Gtk.Label(label=_("Not working or not configured"), vexpand=True))
        else:
            self.update_status = response['result']
            self.update_all.set_sensitive(True)
            self.create_info_grid()
        self.scroll.show_all()

    def restart(self, widget, program):
        if self._printer.state in ("printing", "paused"):
            self._screen._confirm_send_action(widget, f'{_("Are you sure?")}\n\n'
                                                      f'{_("Restart")}: {program}',
                                              "machine.services.restart", {"service": program})
        else:
            self._screen._send_action(widget, "machine.services.restart", {"service": program})

    def show_update_info(self, widget, program):
        info = self.update_status['version_info'][program] if program in self.update_status['version_info'] else {}

        scroll = self._gtk.ScrolledWindow(steppers=False)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        label = Gtk.Label(wrap=True, vexpand=True)
        if program == "full":
            label.set_markup('<b>' + _("Perform a full upgrade?") + '</b>')
            vbox.add(label)
        elif 'configured_type' in info and info['configured_type'] == 'git_repo':
            if not info['is_valid'] or info['is_dirty']:
                label.set_markup(_("Do you want to recover %s?") % program)
                recoverybuttons = [
                    {"name": _("Recover Hard"), "response": Gtk.ResponseType.OK, "style": 'dialog-warning'},
                    {"name": _("Recover Soft"), "response": Gtk.ResponseType.APPLY, "style": 'dialog-info'},
                    {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'}
                ]
                self._gtk.Dialog(_("Recover"), recoverybuttons, label, self.reset_confirm, program)
                return
            else:
                if info['version'] == info['remote_version']:
                    return
                ncommits = len(info['commits_behind'])
                label.set_markup("<b>" +
                                 _("Outdated by %d") % ncommits +
                                 " " + ngettext("commit", "commits", ncommits) +
                                 ":</b>\n")
                vbox.add(label)
                label.set_vexpand(False)
                for c in info['commits_behind']:
                    commit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    title = Gtk.Label(wrap=True, hexpand=True)
                    title.set_markup(f"\n<b>{c['subject']}</b>\n<i>{c['author']}</i>\n")
                    commit_box.add(title)

                    details = Gtk.Label(label=c['message'], wrap=True, hexpand=True)
                    commit_box.add(details)
                    commit_box.add(Gtk.Separator())
                    vbox.add(commit_box)

        elif "package_count" in info:
            label.set_markup((
                f'<b>{info["package_count"]} '
                + ngettext("Package will be updated", "Packages will be updated", info["package_count"])
                + ':</b>\n'
            ))
            label.set_vexpand(False)
            vbox.set_valign(Gtk.Align.CENTER)
            vbox.add(label)
            grid = Gtk.Grid(column_homogeneous=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            i = 0
            for j, c in enumerate(info["package_list"]):
                label = Gtk.Label(halign=Gtk.Align.START, ellipsize=Pango.EllipsizeMode.END)
                label.set_markup(f"  {c}  ")
                pos = (j % 3)
                grid.attach(label, pos, i, 1, 1)
                if pos == 2:
                    i += 1
            vbox.add(grid)
        else:
            label.set_markup(
                "<b>" + _("%s will be updated to version") % program.capitalize()
                + f": {info['remote_version']}</b>"
            )
            vbox.add(label)

        scroll.add(vbox)

        buttons = [
            {"name": _("Update"), "response": Gtk.ResponseType.OK, "style": 'dialog-info'},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'}
        ]
        self._gtk.Dialog(_("Update"), buttons, scroll, self.update_confirm, program)

    def update_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Updating {program}")
            self.update_program(self, program)

    def reset_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Recovering hard {program}")
            self.reset_repo(self, program, True)
        if response_id == Gtk.ResponseType.APPLY:
            logging.debug(f"Recovering soft {program}")
            self.reset_repo(self, program, False)

    def reset_repo(self, widget, program, hard):
        if self._screen.updating:
            return
        self._screen.base_panel.show_update_dialog()
        msg = _("Starting recovery for") + f' {program}...'
        self._screen._websocket_callback("notify_update_response",
                                         {'application': {program}, 'message': msg, 'complete': False})
        logging.info(f"Sending machine.update.recover name: {program} hard: {hard}")
        self._screen._ws.send_method("machine.update.recover", {"name": program, "hard": hard})

    def update_program(self, widget, program):
        if self._screen.updating or not self.update_status:
            return

        if program in self.update_status['version_info']:
            info = self.update_status['version_info'][program]
            logging.info(f"program: {info}")
            if "package_count" in info and info['package_count'] == 0 \
                    or "version" in info and info['version'] == info['remote_version']:
                return
        self._screen.base_panel.show_update_dialog()
        msg = _("Updating") if program == "full" else _("Starting update for") + f' {program}...'
        self._screen._websocket_callback("notify_update_response",
                                         {'application': {program}, 'message': msg, 'complete': False})

        if program in ['klipper', 'moonraker', 'system', 'full']:
            logging.info(f"Sending machine.update.{program}")
            self._screen._ws.send_method(f"machine.update.{program}")
        else:
            logging.info(f"Sending machine.update.client name: {program}")
            self._screen._ws.send_method("machine.update.client", {"name": program})

    def update_program_info(self, p):

        if not self.update_status or p not in self.update_status['version_info']:
            logging.info(f"Unknown version: {p}")
            return

        info = self.update_status['version_info'][p]

        if p == "system":
            self.labels[p].set_markup("<b>System</b>")
            if info['package_count'] == 0:
                self.labels[f"{p}_status"].set_label(_("Up To Date"))
                self.labels[f"{p}_status"].get_style_context().remove_class('update')
                self.labels[f"{p}_status"].set_sensitive(False)
            else:
                self._needs_update(p, local="", remote=info['package_count'])

        elif 'configured_type' in info and info['configured_type'] == 'git_repo':
            if info['is_valid'] and not info['is_dirty']:
                if info['version'] == info['remote_version']:
                    self._already_updated(p, info)
                    self.labels[f"{p}_status"].get_style_context().remove_class('invalid')
                else:
                    self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}")
                    self._needs_update(p, info['version'], info['remote_version'])
            else:
                logging.info(f"Invalid {p} {info['version']}")
                self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
                self.labels[f"{p}_status"].set_label(_("Invalid"))
                self.labels[f"{p}_status"].get_style_context().add_class('invalid')
                self.labels[f"{p}_status"].set_sensitive(True)
        elif 'version' in info and info['version'] == info['remote_version']:
            self._already_updated(p, info)
        else:
            self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}")
            self._needs_update(p, info['version'], info['remote_version'])

    def _already_updated(self, p, info):
        self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
        self.labels[f"{p}_status"].set_label(_("Up To Date"))
        self.labels[f"{p}_status"].get_style_context().remove_class('update')
        self.labels[f"{p}_status"].set_sensitive(False)

    def _needs_update(self, p, local="", remote=""):
        logging.info(f"{p} {local} -> {remote}")
        self.labels[f"{p}_status"].set_label(_("Update"))
        self.labels[f"{p}_status"].get_style_context().add_class('update')
        self.labels[f"{p}_status"].set_sensitive(True)
