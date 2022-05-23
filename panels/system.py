import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, Pango
from datetime import datetime

from ks_includes.screen_panel import ScreenPanel


def create_panel(*args):
    return SystemPanel(*args)


ALLOWED_SERVICES = ["KlipperScreen", "MoonCord", "klipper", "moonraker"]


class SystemPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)

        update_all = self._gtk.ButtonImage('refresh', "\n".join(_('Full\nUpdate').split(' ')), 'color1')
        update_all.connect("clicked", self.show_update_info, "full")
        update_all.set_vexpand(False)
        firmrestart = self._gtk.ButtonImage('refresh', "\n".join(_('Firmware\nRestart').split(' ')), 'color2')
        firmrestart.connect("clicked", self.restart_klippy, "firmware")
        firmrestart.set_vexpand(False)

        reboot = self._gtk.ButtonImage('refresh', _('System\nRestart'), 'color3')
        reboot.connect("clicked", self._screen._confirm_send_action,
                       _("Are you sure you wish to reboot the system?"), "machine.reboot")
        reboot.set_vexpand(False)
        shutdown = self._gtk.ButtonImage('shutdown', _('System\nShutdown'), 'color4')
        shutdown.connect("clicked", self._screen._confirm_send_action,
                         _("Are you sure you wish to shutdown the system?"), "machine.shutdown")
        shutdown.set_vexpand(False)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        infogrid = Gtk.Grid()
        infogrid.get_style_context().add_class("system-program-grid")
        update_resp = self._screen.apiclient.send_request("machine/update/status")
        self.update_status = False

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

                self.labels["%s_status" % prog] = self._gtk.Button()
                self.labels["%s_status" % prog].set_hexpand(False)
                self.labels["%s_status" % prog].connect("clicked", self.show_update_info, prog)

                if prog in ALLOWED_SERVICES:
                    self.labels["%s_restart" % prog] = self._gtk.ButtonImage("refresh", None, None, .7, .7)
                    self.labels["%s_restart" % prog].connect("clicked", self.restart, prog)
                    infogrid.attach(self.labels["%s_restart" % prog], 0, i, 1, 1)

                infogrid.attach(self.labels["%s_status" % prog], 2, i, 1, 1)
                logging.info("Updating program: %s " % prog)
                self.update_program_info(prog)

                infogrid.attach(self.labels[prog], 1, i, 1, 1)
                self.labels[prog].get_style_context().add_class('updater-item')
                i = i + 1

        scroll.add(infogrid)

        grid.attach(scroll, 0, 0, 4, 2)
        grid.attach(update_all, 0, 2, 1, 1)
        grid.attach(firmrestart, 1, 2, 1, 1)
        grid.attach(reboot, 2, 2, 1, 1)
        grid.attach(shutdown, 3, 2, 1, 1)
        self.content.add(grid)

    def activate(self):
        self.get_updates()

    def destroy_widget(self, widget, response_id):
        widget.destroy()

    def finish_updating(self, widget, response_id):
        widget.destroy()
        self._screen.set_updating(False)
        self.get_updates()

    def get_updates(self):
        update_resp = self._screen.apiclient.send_request("machine/update/status")
        if not update_resp:
            logging.info("No update manager configured")
        else:
            self.update_status = update_resp['result']
            vi = update_resp['result']['version_info']
            items = sorted(list(vi))
            for prog in items:
                self.update_program_info(prog)

    def process_update(self, action, data):
        if action == "notify_update_response":
            logging.info("Update: %s" % data)
            if 'application' in data:
                self.labels['update_progress'].set_text(self.labels['update_progress'].get_text().strip() + "\n" +
                                                        data['message'] + "\n")
                self.labels['update_progress'].set_ellipsize(Pango.EllipsizeMode.END)
                adjustment = self.labels['update_scroll'].get_vadjustment()
                adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
                adjustment = self.labels['update_scroll'].show_all()

                if data['complete']:
                    self.update_dialog.set_response_sensitive(Gtk.ResponseType.CANCEL, True)

    def restart(self, widget, program):
        if program not in ALLOWED_SERVICES:
            return

        logging.info("Restarting service: %s" % program)
        self._screen._ws.send_method("machine.services.restart", {"service": program})

    def show_update_info(self, widget, program):
        _ = self.lang.gettext
        _n = self.lang.ngettext

        if not self.update_status:
            return
        if program in self.update_status['version_info']:
            info = self.update_status['version_info'][program]
        else:
            info = ["full"]

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_valign(Gtk.Align.CENTER)
        i = 0
        label = Gtk.Label()
        label.set_line_wrap(True)
        if 'configured_type' in info and info['configured_type'] == 'git_repo':
            if not info['is_valid'] or info['is_dirty']:
                label.set_markup(_("Do you want to recover %s?") % program)
                grid.attach(label, 0, i, 1, 1)
                scroll.add(grid)
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
                                 " " + _n("commit", "commits", ncommits) +
                                 ":</b>\n")
                grid.attach(label, 0, i, 1, 1)
                i = i + 1
                date = ""
                for c in info['commits_behind']:
                    ndate = datetime.fromtimestamp(int(c['date'])).strftime("%b %d")
                    if date != ndate:
                        date = ndate
                        label = Gtk.Label()
                        label.set_line_wrap(True)
                        label.set_markup("<b>%s</b>\n" % date)
                        label.set_halign(Gtk.Align.START)
                        grid.attach(label, 0, i, 1, 1)
                        i = i + 1

                    label = Gtk.Label()
                    label.set_line_wrap(True)
                    label.set_markup("<b>%s</b>\n<i>%s</i>\n" % (c['subject'], c['author']))
                    label.set_halign(Gtk.Align.START)
                    grid.attach(label, 0, i, 1, 1)
                    i = i + 1

                    details = Gtk.Label(label=c['message'] + "\n\n\n")
                    details.set_line_wrap(True)
                    details.set_halign(Gtk.Align.START)
                    grid.attach(details, 0, i, 1, 1)
                    i = i + 1
        if "package_count" in info:
            label.set_markup("<b>%d " % info['package_count'] +
                             _n("Package will be updated", "Packages will be updated", info['package_count']) +
                             ":</b>\n")
            label.set_halign(Gtk.Align.CENTER)
            grid.attach(label, 0, i, 3, 1)
            i = i + 1
            j = 0
            for c in info["package_list"]:
                label = Gtk.Label()
                label.set_markup("  %s  " % c)
                label.set_halign(Gtk.Align.START)
                label.set_ellipsize(Pango.EllipsizeMode.END)
                pos = (j % 3)
                grid.attach(label, pos, i, 1, 1)
                j = j + 1
                if pos == 2:
                    i = i + 1
        elif "full" in info:
            label.set_markup("<b>" + _("Perform a full upgrade?") + "</b>")
            grid.attach(label, 0, i, 1, 1)
            i = i + 1
        else:
            label.set_markup("<b>" + _("%s will be updated to version") % program.capitalize() +
                             ": %s</b>" % (info['remote_version']))
            grid.attach(label, 0, i, 1, 1)
            i = i + 1

        scroll.add(grid)

        buttons = [
            {"name": _("Update"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        self._gtk.Dialog(self._screen, buttons, scroll, self.update_confirm, program)

    def update_confirm(self, widget, response_id, program):
        if response_id == Gtk.ResponseType.OK:
            logging.debug("Updating %s" % program)
            self.update_program(self, program)
        widget.destroy()

    def reset_confirm(self, widget, response_id, program):
        if response_id == Gtk.ResponseType.OK:
            logging.debug("Recovering hard %s" % program)
            self.reset_repo(self, program, True)
        if response_id == Gtk.ResponseType.APPLY:
            logging.debug("Recovering soft %s" % program)
            self.reset_repo(self, program, False)
        widget.destroy()

    def reset_repo(self, widget, program, hard):
        if self._screen.is_updating():
            return

        _ = self.lang.gettext

        buttons = [
            {"name": _("Finish"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        self.labels['update_progress'] = Gtk.Label("%s %s..." % (_("Starting recovery for"), program))
        self.labels['update_progress'].set_halign(Gtk.Align.START)
        self.labels['update_progress'].set_valign(Gtk.Align.START)
        scroll.add(self.labels['update_progress'])
        self.labels['update_scroll'] = scroll

        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.finish_updating)
        dialog.set_response_sensitive(Gtk.ResponseType.CANCEL, False)

        self.update_prog = program
        self.update_dialog = dialog

        logging.info("Sending machine.update.recover name: %s" % program)

        self._screen._ws.send_method("machine.update.recover", {"name": program, "hard": str(hard)})
        self._screen.set_updating(True)

    def update_program(self, widget, program):
        if self._screen.is_updating():
            return

        _ = self.lang.gettext

        if not self.update_status:
            return

        if program in self.update_status['version_info']:
            info = self.update_status['version_info'][program]
            logging.info("program: %s" % info)
        else:
            info = ["full"]
            logging.info("full upgrade")

        if "package_count" in info:
            if info['package_count'] == 0:
                return
        elif "version" in info:
            if info['version'] == info['remote_version']:
                return

        buttons = [
            {"name": _("Finish"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add_events(Gdk.EventMask.TOUCH_MASK)
        scroll.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        if "full" in info:
            self.labels['update_progress'] = Gtk.Label("%s\n" % _("Updating"))
        else:
            self.labels['update_progress'] = Gtk.Label("%s %s..." % (_("Starting update for"), program))
        self.labels['update_progress'].set_halign(Gtk.Align.START)
        self.labels['update_progress'].set_valign(Gtk.Align.START)
        scroll.add(self.labels['update_progress'])
        self.labels['update_scroll'] = scroll

        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.finish_updating)
        dialog.set_response_sensitive(Gtk.ResponseType.CANCEL, False)

        self.update_prog = program
        self.update_dialog = dialog

        if program in ['klipper', 'moonraker', 'system', 'full']:
            logging.info("Sending machine.update.%s" % program)
            self._screen._ws.send_method("machine.update.%s" % program)
        else:
            logging.info("Sending machine.update.client name: %s" % program)
            self._screen._ws.send_method("machine.update.client", {"name": program})
        self._screen.set_updating(True)

    def update_program_info(self, p):
        _ = self.lang.gettext

        logging.info("Updating program: %s " % p)
        if 'version_info' not in self.update_status or p not in self.update_status['version_info']:
            return

        info = self.update_status['version_info'][p]
        logging.info("%s: %s" % (p, info))

        if p != "system":
            if 'configured_type' in info and info['configured_type'] == 'git_repo':
                if info['is_valid'] and not info['is_dirty']:
                    if info['version'] == info['remote_version']:
                        self.labels[p].set_markup("<b>%s</b>\n%s" % (p, info['version']))
                        self.labels["%s_status" % p].set_label(_("Up To Date"))
                        self.labels["%s_status" % p].get_style_context().remove_class('update')
                        self.labels["%s_status" % p].get_style_context().remove_class('invalid')
                        self.labels["%s_status" % p].set_sensitive(False)
                    else:
                        self.labels[p].set_markup("<b>%s</b>\n%s -> %s" % (p, info['version'], info['remote_version']))
                        self.labels["%s_status" % p].set_label(_("Update"))
                        self.labels["%s_status" % p].get_style_context().add_class('update')
                        self.labels["%s_status" % p].set_sensitive(True)
                else:
                    self.labels[p].set_markup("<b>%s</b>\n%s" % (p, info['version']))
                    self.labels["%s_status" % p].set_label(_("Invalid"))
                    self.labels["%s_status" % p].get_style_context().add_class('invalid')
                    self.labels["%s_status" % p].set_sensitive(True)
            else:
                if 'version' in info and info['version'] == info['remote_version']:
                    self.labels[p].set_markup("<b>%s</b>\n%s" % (p, info['version']))
                    self.labels["%s_status" % p].set_label(_("Up To Date"))
                    self.labels["%s_status" % p].get_style_context().remove_class('update')
                    self.labels["%s_status" % p].set_sensitive(False)
                else:
                    self.labels[p].set_markup("<b>%s</b>\n%s -> %s" % (p, info['version'], info['remote_version']))
                    self.labels["%s_status" % p].set_label(_("Update"))
                    self.labels["%s_status" % p].get_style_context().add_class('update')
                    self.labels["%s_status" % p].set_sensitive(True)
        else:
            self.labels[p].set_markup("<b>System</b>")
            if info['package_count'] == 0:
                self.labels["%s_status" % p].set_label(_("Up To Date"))
                self.labels["%s_status" % p].get_style_context().remove_class('update')
                self.labels["%s_status" % p].set_sensitive(False)
            else:
                self.labels["%s_status" % p].set_label(_("Update"))
                self.labels["%s_status" % p].get_style_context().add_class('update')
                self.labels["%s_status" % p].set_sensitive(True)

    def restart_klippy(self, widget, type=None):
        if type == "firmware":
            self._screen._ws.klippy.restart_firmware()
        else:
            self._screen._ws.klippy.restart()

    def restart_ks(self, widget):
        os.system("sudo systemctl restart %s" % self._config.get_main_config_option('service'))
