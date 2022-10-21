import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GLib

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return SystemPanel(*args)


# Same as ALLOWED_SERVICES in moonraker
# https://github.com/Arksine/moonraker/blob/master/moonraker/components/machine.py
ALLOWED_SERVICES = (
    "crowsnest",
    "MoonCord",
    "moonraker",
    "moonraker-telegram-bot",
    "klipper",
    "KlipperScreen",
    "sonar",
    "webcamd",
)


class SystemPanel(ScreenPanel):
    def __init__(self, screen, title, back=True):
        super().__init__(screen, title, back)
        self.refresh = None
        self.update_status = None
        self.update_dialog = None
        self.update_prog = None

    def initialize(self, panel_name):

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)

        update_all = self._gtk.ButtonImage('arrow-up', _('Full Update'), 'color1')
        update_all.connect("clicked", self.show_update_info, "full")
        update_all.set_vexpand(False)
        self.refresh = self._gtk.ButtonImage('refresh', _('Refresh'), 'color2')
        self.refresh.connect("clicked", self.refresh_updates)
        self.refresh.set_vexpand(False)

        reboot = self._gtk.ButtonImage('refresh', _('Restart'), 'color3')
        reboot.connect("clicked", self.reboot_poweroff, "reboot")
        reboot.set_vexpand(False)
        shutdown = self._gtk.ButtonImage('shutdown', _('Shutdown'), 'color4')
        shutdown.connect("clicked", self.reboot_poweroff, "poweroff")
        shutdown.set_vexpand(False)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        infogrid = Gtk.Grid()
        infogrid.get_style_context().add_class("system-program-grid")
        update_resp = self._screen.apiclient.send_request("machine/update/status")
        self.update_status = None

        if not update_resp:
            logging.info("No update manager configured")
        else:
            self.update_status = update_resp['result']
            vi = update_resp['result']['version_info']
            items = sorted(list(vi))
            i = 0
            for prog in items:
                self.labels[prog] = Gtk.Label("")
                self.labels[prog].set_hexpand(True)
                self.labels[prog].set_halign(Gtk.Align.START)

                self.labels[f"{prog}_status"] = self._gtk.Button()
                self.labels[f"{prog}_status"].set_hexpand(False)
                self.labels[f"{prog}_status"].connect("clicked", self.show_update_info, prog)

                if prog in ALLOWED_SERVICES:
                    self.labels[f"{prog}_restart"] = self._gtk.ButtonImage("refresh", scale=.7)
                    self.labels[f"{prog}_restart"].connect("clicked", self.restart, prog)
                    infogrid.attach(self.labels[f"{prog}_restart"], 0, i, 1, 1)

                infogrid.attach(self.labels[f"{prog}_status"], 2, i, 1, 1)
                logging.info(f"Updating program: {prog} ")
                self.update_program_info(prog)

                infogrid.attach(self.labels[prog], 1, i, 1, 1)
                self.labels[prog].get_style_context().add_class('updater-item')
                i = i + 1

        scroll.add(infogrid)

        grid.attach(scroll, 0, 0, 4, 2)
        grid.attach(update_all, 0, 2, 1, 1)
        grid.attach(self.refresh, 1, 2, 1, 1)
        grid.attach(reboot, 2, 2, 1, 1)
        grid.attach(shutdown, 3, 2, 1, 1)
        self.content.add(grid)

    def activate(self):
        self.get_updates()

    def finish_updating(self, widget, response_id):
        widget.destroy()
        self._screen.set_updating(False)
        self.get_updates()

    def refresh_updates(self, widget=None):
        self.refresh.set_sensitive(False)
        self._screen.show_popup_message(_("Checking for updates, please wait..."), level=1)
        GLib.timeout_add_seconds(1, self.get_updates, "true")

    def get_updates(self, refresh="false"):
        update_resp = self._screen.apiclient.send_request(f"machine/update/status?refresh={refresh}")
        if not update_resp:
            logging.info("No update manager configured")
        else:
            self.update_status = update_resp['result']
            vi = update_resp['result']['version_info']
            items = sorted(list(vi))
            for prog in items:
                self.update_program_info(prog)
        self.refresh.set_sensitive(True)
        self._screen.close_popup_message()

    def process_update(self, action, data):
        if action == "notify_update_response":
            logging.info(f"Update: {data}")
            if 'application' in data:
                self.labels['update_progress'].set_text(
                    f"{self.labels['update_progress'].get_text().strip()}\n"
                    f"{data['message']}\n"
                )
                if data['complete']:
                    self.update_dialog.set_response_sensitive(Gtk.ResponseType.CANCEL, True)
                    self.update_dialog.get_widget_for_response(Gtk.ResponseType.CANCEL).show()

    def restart(self, widget, program):
        if program not in ALLOWED_SERVICES:
            return

        logging.info(f"Restarting service: {program}")
        self._screen._ws.send_method("machine.services.restart", {"service": program})

    def show_update_info(self, widget, program):

        if not self.update_status:
            return
        if program in self.update_status['version_info']:
            info = self.update_status['version_info'][program]
        else:
            info = {"full": True}

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)

        label = Gtk.Label()
        label.set_line_wrap(True)
        if 'configured_type' in info and info['configured_type'] == 'git_repo':
            if not info['is_valid'] or info['is_dirty']:
                label.set_markup(_("Do you want to recover %s?") % program)
                vbox.add(label)
                scroll.add(vbox)
                recoverybuttons = [
                    {"name": _("Recover Hard"), "response": Gtk.ResponseType.OK},
                    {"name": _("Recover Soft"), "response": Gtk.ResponseType.APPLY},
                    {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
                ]
                self._gtk.Dialog(self._screen, recoverybuttons, scroll, self.reset_confirm, program)
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

                for c in info['commits_behind']:
                    commit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    title = Gtk.Label()
                    title.set_line_wrap(True)
                    title.set_line_wrap_mode(Pango.WrapMode.CHAR)
                    title.set_markup(f"\n<b>{c['subject']}</b>\n<i>{c['author']}</i>\n")
                    title.set_halign(Gtk.Align.START)
                    commit_box.add(title)

                    details = Gtk.Label(label=f"{c['message']}")
                    details.set_line_wrap(True)
                    details.set_halign(Gtk.Align.START)
                    commit_box.add(details)
                    commit_box.add(Gtk.Separator())
                    vbox.add(commit_box)

        if "package_count" in info:
            label.set_markup((
                f'<b>{info["package_count"]} '
                + ngettext("Package will be updated", "Packages will be updated", info["package_count"])
                + f':</b>\n'
            ))
            label.set_halign(Gtk.Align.CENTER)
            vbox.add(label)
            grid = Gtk.Grid()
            grid.set_column_homogeneous(True)
            grid.set_halign(Gtk.Align.CENTER)
            grid.set_valign(Gtk.Align.CENTER)
            i = 0
            for j, c in enumerate(info["package_list"]):
                label = Gtk.Label()
                label.set_markup(f"  {c}  ")
                label.set_halign(Gtk.Align.START)
                label.set_ellipsize(Pango.EllipsizeMode.END)
                pos = (j % 3)
                grid.attach(label, pos, i, 1, 1)
                if pos == 2:
                    i += 1
            vbox.add(grid)
        elif "full" in info:
            label.set_markup('<b>' + _("Perform a full upgrade?") + '</b>')
            vbox.add(label)
        else:
            label.set_markup(
                "<b>" + _("%s will be updated to version") % program.capitalize()
                + f": {info['remote_version']}</b>"
            )
            vbox.add(label)

        scroll.add(vbox)

        buttons = [
            {"name": _("Update"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        self._gtk.Dialog(self._screen, buttons, scroll, self.update_confirm, program)

    def update_confirm(self, widget, response_id, program):
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Updating {program}")
            self.update_program(self, program)
        widget.destroy()

    def reset_confirm(self, widget, response_id, program):
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Recovering hard {program}")
            self.reset_repo(self, program, True)
        if response_id == Gtk.ResponseType.APPLY:
            logging.debug(f"Recovering soft {program}")
            self.reset_repo(self, program, False)
        widget.destroy()

    def reset_repo(self, widget, program, hard):
        if self._screen.is_updating():
            return

        buttons = [
            {"name": _("Finish"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = self._gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", True)

        self.labels['update_progress'] = Gtk.Label(_("Starting recovery for") + f' {program}...')
        self.labels['update_progress'].set_halign(Gtk.Align.START)
        self.labels['update_progress'].set_valign(Gtk.Align.START)
        self.labels['update_progress'].set_ellipsize(Pango.EllipsizeMode.END)
        self.labels['update_progress'].connect("size-allocate", self._autoscroll)
        scroll.add(self.labels['update_progress'])
        self.labels['update_scroll'] = scroll

        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.finish_updating)
        dialog.set_response_sensitive(Gtk.ResponseType.CANCEL, False)
        dialog.get_widget_for_response(Gtk.ResponseType.CANCEL).hide()

        self.update_prog = program
        self.update_dialog = dialog

        logging.info(f"Sending machine.update.recover name: {program}")

        self._screen._ws.send_method("machine.update.recover", {"name": program, "hard": hard})
        self._screen.set_updating(True)

    def update_program(self, widget, program):
        if self._screen.is_updating():
            return

        if not self.update_status:
            return

        if program in self.update_status['version_info']:
            info = self.update_status['version_info'][program]
            logging.info(f"program: {info}")
        else:
            info = {"full": True}
            logging.info("full upgrade")

        if "package_count" in info and info['package_count'] == 0 \
                or "version" in info and info['version'] == info['remote_version']:
            return
        buttons = [
            {"name": _("Finish"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = self._gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", True)

        if "full" in info:
            self.labels['update_progress'] = Gtk.Label(_("Updating") + '\n')
        else:
            self.labels['update_progress'] = Gtk.Label(_("Starting update for") + f' {program}...')
        self.labels['update_progress'].set_halign(Gtk.Align.START)
        self.labels['update_progress'].set_valign(Gtk.Align.START)
        self.labels['update_progress'].connect("size-allocate", self._autoscroll)
        scroll.add(self.labels['update_progress'])
        self.labels['update_scroll'] = scroll

        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.finish_updating)
        dialog.set_response_sensitive(Gtk.ResponseType.CANCEL, False)
        dialog.get_widget_for_response(Gtk.ResponseType.CANCEL).hide()

        self.update_prog = program
        self.update_dialog = dialog

        if program in ['klipper', 'moonraker', 'system', 'full']:
            logging.info(f"Sending machine.update.{program}")
            self._screen._ws.send_method(f"machine.update.{program}")
        else:
            logging.info(f"Sending machine.update.client name: {program}")
            self._screen._ws.send_method("machine.update.client", {"name": program})
        self._screen.set_updating(True)

    def update_program_info(self, p):

        logging.info(f"Updating program: {p} ")
        if 'version_info' not in self.update_status or p not in self.update_status['version_info']:
            return

        info = self.update_status['version_info'][p]
        logging.info(f"{p}: {info}")

        if p == "system":
            self.labels[p].set_markup("<b>System</b>")
            if info['package_count'] == 0:
                self.labels[f"{p}_status"].set_label(_("Up To Date"))
                self.labels[f"{p}_status"].get_style_context().remove_class('update')
                self.labels[f"{p}_status"].set_sensitive(False)
            else:
                self._needs_update(p)

        elif 'configured_type' in info and info['configured_type'] == 'git_repo':
            if info['is_valid'] and not info['is_dirty']:
                if info['version'] == info['remote_version']:
                    self._already_updated(p, info)
                    self.labels[f"{p}_status"].get_style_context().remove_class('invalid')
                else:
                    self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}")
                    self._needs_update(p)
            else:
                self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
                self.labels[f"{p}_status"].set_label(_("Invalid"))
                self.labels[f"{p}_status"].get_style_context().add_class('invalid')
                self.labels[f"{p}_status"].set_sensitive(True)
        elif 'version' in info and info['version'] == info['remote_version']:
            self._already_updated(p, info)
        else:
            self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}")
            self._needs_update(p)

    def _already_updated(self, p, info):
        self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
        self.labels[f"{p}_status"].set_label(_("Up To Date"))
        self.labels[f"{p}_status"].get_style_context().remove_class('update')
        self.labels[f"{p}_status"].set_sensitive(False)

    def _needs_update(self, p):
        self.labels[f"{p}_status"].set_label(_("Update"))
        self.labels[f"{p}_status"].get_style_context().add_class('update')
        self.labels[f"{p}_status"].set_sensitive(True)

    def _autoscroll(self, *args):
        adj = self.labels['update_scroll'].get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def reboot_poweroff(self, widget, method):
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        if method == "reboot":
            label = Gtk.Label(label=_("Are you sure you wish to reboot the system?"))
        else:
            label = Gtk.Label(label=_("Are you sure you wish to shutdown the system?"))
        vbox.add(label)
        scroll.add(vbox)
        buttons = [
            {"name": _("Host"), "response": Gtk.ResponseType.OK},
            {"name": _("Printer"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        self._gtk.Dialog(self._screen, buttons, scroll, self.reboot_poweroff_confirm, method)

    def reboot_poweroff_confirm(self, widget, response_id, method):
        if response_id == Gtk.ResponseType.OK:
            if method == "reboot":
                os.system("systemctl reboot")
            else:
                os.system("systemctl poweroff")
        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            else:
                self._screen._ws.send_method("machine.shutdown")
        widget.destroy()
