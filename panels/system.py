import gi
import logging
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from datetime import datetime

from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel

def create_panel(*args):
    return SystemPanel(*args)

class SystemPanel(ScreenPanel):
    def initialize(self, panel_name):
        _ = self.lang.gettext

        grid = self._gtk.HomogeneousGrid()
        grid.set_row_homogeneous(False)

        restart = self._gtk.ButtonImage('refresh',"\n".join(_('Klipper Restart').split(' ')),'color1')
        restart.connect("clicked", self.restart_klippy)
        restart.set_vexpand(False)
        firmrestart = self._gtk.ButtonImage('refresh',"\n".join(_('Firmware Restart').split(' ')),'color2')
        firmrestart.connect("clicked", self.restart_klippy, "firmware")
        firmrestart.set_vexpand(False)

        ks_restart = self._gtk.ButtonImage('refresh',"\n".join(_('Restart Klipper Screen').split(' ')))
        ks_restart.set_vexpand(False)
        ks_restart.connect("clicked", self.restart_ks)

        reboot = self._gtk.ButtonImage('refresh',_('System\nRestart'),'color3')
        reboot.connect("clicked", self._screen._confirm_send_action,
            _("Are you sure you wish to reboot the system?"), "machine.reboot")
        reboot.set_vexpand(False)
        shutdown = self._gtk.ButtonImage('shutdown',_('System\nShutdown'),'color4')
        shutdown.connect("clicked", self._screen._confirm_send_action,
            _("Are you sure you wish to shutdown the system?"), "machine.shutdown")
        shutdown.set_vexpand(False)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info.set_vexpand(True)
        info.set_valign(Gtk.Align.CENTER)

        self.labels['loadavg'] = Gtk.Label("temp")
        #self.system_timeout = GLib.timeout_add(1000, self.update_system_load)

        self.labels['klipper_version'] = Gtk.Label(_("Klipper Version") +
            (": %s" % self._screen.printer.get_klipper_version()))
        self.labels['klipper_version'].set_margin_top(15)

        self.labels['ks_version'] = Gtk.Label(_("KlipperScreen Version") + (": %s" % self._screen.version))
        self.labels['ks_version'].set_margin_top(15)

        info.add(self.labels['loadavg'])
        info.add(self.labels['klipper_version'])
        info.add(self.labels['ks_version'])

        scroll = Gtk.ScrolledWindow()
        scroll.set_property("overlay-scrolling", False)
        scroll.set_vexpand(True)

        infogrid = Gtk.Grid()
        infogrid.get_style_context().add_class("system-program-grid")
        update_resp = self._screen.apiclient.send_request("machine/update/status")
        self.update_status = False

        if update_resp == False:
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
                self.labels["%s_status" % prog].connect("clicked", self.update_program, prog)
                self.labels["%s_box" % prog] = Gtk.Box()
                self.labels["%s_box" % prog].set_hexpand(False)
                self.labels["%s_info" % prog] = self._gtk.ButtonImage("info",None, None, .7, .7)
                self.labels["%s_info" % prog].connect("clicked", self.show_commit_history, prog)

                self.labels["%s_box" % prog].pack_end(self.labels["%s_status" % prog], True, 0, 0)
                logging.info("Updating program: %s " % prog)
                self.update_program_info(prog)


                infogrid.attach(self.labels["%s_box" % prog], 1, i, 1, 1)
                infogrid.attach(self.labels[prog], 0, i, 1, 1)
                i = i + 1

        scroll.add(infogrid)

        grid.attach(scroll, 0, 0, 5, 2)
        grid.attach(restart, 0, 2, 1, 1)
        grid.attach(firmrestart, 1, 2, 1, 1)
        grid.attach(ks_restart, 2, 2, 1, 1)
        grid.attach(reboot, 3, 2, 1, 1)
        grid.attach(shutdown, 4, 2, 1, 1)

        self.content.add(grid)
        self._screen.add_subscription(panel_name)

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
        if update_resp == False:
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
            if 'application' in data and data['application'] == self.update_prog:
                self.labels['update_progress'].set_text(self.labels['update_progress'].get_text().strip() + "\n" +
                    data['message'] + "\n")
                adjustment = self.labels['update_scroll'].get_vadjustment()
                adjustment.set_value( adjustment.get_upper() - adjustment.get_page_size() )
                adjustment = self.labels['update_scroll'].show_all()

                if data['complete'] == True:
                    self.update_dialog.set_response_sensitive(Gtk.ResponseType.CANCEL, True)

    def show_commit_history(self, widget, program):
        _ = self.lang.gettext

        if self.update_status == False or program not in self.update_status['version_info']:
            return

        info = self.update_status['version_info'][program]
        if info['version'] == info['remote_version']:
            return

        buttons = [
            {"name":_("Go Back"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        grid = Gtk.Grid()
        grid.set_halign(Gtk.Align.START)
        i = 0
        date = ""
        for c in info['commits_behind']:
            ndate = datetime.fromtimestamp(int(c['date'])).strftime("%b %d")
            if date != ndate:
                date = ndate
                label = Gtk.Label("")
                label.set_markup("<b>%s</b>\n" % date)
                grid.attach(label, 0, i, 1, 1)
                i = i + 1

            label = Gtk.Label()
            label.set_markup("%s\n<i>%s</i> %s %s\n" % (c['subject'], c['author'], _("Commited"),"2 days ago"))
            label.set_hexpand(True)
            label.set_halign(Gtk.Align.START)
            grid.attach(label, 0, i, 1, 1)
            i = i + 1

        scroll.add(grid)

        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.destroy_widget)

    def update_program(self, widget, program):
        if self._screen.is_updating():
            return

        _ = self.lang.gettext

        if self.update_status == False or program not in self.update_status['version_info']:
            return

        info = self.update_status['version_info'][program]
        logging.info("program: %s" % info)
        if "package_count" in info:
            if info['package_count'] == 0:
                return
        else:
            if info['version'] == info['remote_version']:
                return

        buttons = [
            {"name":_("Finish"), "response": Gtk.ResponseType.CANCEL}
        ]

        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        self.labels['update_progress'] = Gtk.Label("%s %s%s" % (_("Starting update for"), program, _("...")))
        self.labels['update_progress'].set_halign(Gtk.Align.START)
        self.labels['update_progress'].set_valign(Gtk.Align.START)
        scroll.add(self.labels['update_progress'])
        self.labels['update_scroll'] = scroll

        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.finish_updating)
        dialog.set_response_sensitive(Gtk.ResponseType.CANCEL, False)

        self.update_prog = program
        self.update_dialog = dialog

        if program in ['klipper','moonraker','system']:
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
            version = (info['full_version_string'] if "full_version_string" in info else info['version'])

            if info['version'] == info['remote_version']:
                self.labels[p].set_markup("<b>%s</b>\n%s" % (p, version))
                self.labels["%s_status" % p].set_label(_("Up To Date"))
                self.labels["%s_status" % p].set_sensitive(False)
                if self.labels["%s_info" % p] in self.labels["%s_box" % p].get_children():
                    self.labels["%s_box" % p].remove(self.labels["%s_info" % p])
            else:
                self.labels[p].set_markup("<b>%s</b>\n%s -> %s" % (p, version, info['remote_version']))
                self.labels["%s_status" % p].set_label(_("Update"))
                self.labels["%s_status" % p].set_sensitive(True)
                if not self.labels["%s_info" % p] in self.labels["%s_box" % p].get_children():
                    self.labels["%s_box" % p].pack_start(self.labels["%s_info" % p], True, 0, 0)
        else:
            self.labels[p].set_markup("<b>System</b>")
            if info['package_count'] == 0:
                self.labels["%s_status" % p].set_label(_("Up To Date"))
                self.labels["%s_status" % p].set_sensitive(False)
            else:
                self.labels["%s_status" % p].set_label(_("Update"))
                self.labels["%s_status" % p].set_sensitive(True)

    def restart_klippy(self, widget, type=None):
        if type == "firmware":
            self._screen._ws.klippy.restart_firmware()
        else:
            self._screen._ws.klippy.restart()

    def restart_ks(self, widget):
        os.system("sudo systemctl restart KlipperScreen")
