import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango
from ks_includes.screen_panel import ScreenPanel
from ks_includes.sdbus_nm import SdbusNm
from datetime import datetime


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("Network")
        super().__init__(screen, title)
        self.last_drop_time = datetime.now()
        self.show_add = False
        try:
            self.sdbus_nm = SdbusNm(self.popup_callback)
        except Exception as e:
            logging.exception("Failed to initialize")
            self.sdbus_nm = None
            self.error_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                hexpand=True,
                vexpand=True
            )
            message = (
                _("Failed to initialize") + "\n"
                + "This panel needs NetworkManager installed into the system\n"
                + "And the apropriate permissions, without them it will not function.\n"
                + f"\n{e}\n"
            )
            self.error_box.add(
                Gtk.Label(
                    label=message,
                    wrap=True,
                    wrap_mode=Pango.WrapMode.WORD_CHAR,
                )
            )
            self.error_box.set_valign(Gtk.Align.CENTER)
            self.content.add(self.error_box)
            self._screen.panels_reinit.append(self._screen._cur_panels[-1])
            return
        self.update_timeout = None
        self.network_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        self.network_rows = {}
        self.networks = {}
        self.wifi_signal_icons = {
            'excellent': self._gtk.PixbufFromIcon('wifi_excellent'),
            'good': self._gtk.PixbufFromIcon('wifi_good'),
            'fair': self._gtk.PixbufFromIcon('wifi_fair'),
            'weak': self._gtk.PixbufFromIcon('wifi_weak'),
        }

        self.network_interfaces = self.sdbus_nm.get_interfaces()
        logging.info(f"Network interfaces: {self.network_interfaces}")

        self.wireless_interfaces = [iface.interface for iface in self.sdbus_nm.get_wireless_interfaces()]
        logging.info(f"Wireless interfaces: {self.wireless_interfaces}")

        self.interface = self.sdbus_nm.get_primary_interface()
        logging.info(f"Primary interface: {self.interface}")

        self.labels['interface'] = Gtk.Label(hexpand=True)
        self.labels['ip'] = Gtk.Label(hexpand=True)
        if self.interface is not None:
            self.labels['interface'].set_text(_("Interface") + f': {self.interface}')
            self.labels['ip'].set_text(f"IP: {self.sdbus_nm.get_ip_address()}")

        self.reload_button = self._gtk.Button("refresh", None, "color1", self.bts)
        self.reload_button.set_no_show_all(True)
        self.reload_button.show()
        self.reload_button.connect("clicked", self.reload_networks)
        self.reload_button.set_hexpand(False)

        self.wifi_toggle = Gtk.Switch(
            width_request=round(self._gtk.font_size * 2),
            height_request=round(self._gtk.font_size),
            active=self.sdbus_nm.is_wifi_enabled()
        )
        self.wifi_toggle.connect("notify::active", self.toggle_wifi)

        sbox = Gtk.Box(hexpand=True, vexpand=False)
        sbox.add(self.labels['interface'])
        sbox.add(self.labels['ip'])
        sbox.add(self.reload_button)
        sbox.add(self.wifi_toggle)

        scroll = self._gtk.ScrolledWindow()
        self.labels['main_box'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)

        if self.sdbus_nm.wifi:
            self.labels['main_box'].pack_start(sbox, False, False, 5)
            GLib.idle_add(self.load_networks)
            scroll.add(self.network_list)
            self.sdbus_nm.enable_monitoring(True)
            self.conn_status = GLib.timeout_add_seconds(1, self.sdbus_nm.monitor_connection_status)
        else:
            self._screen.show_popup_message(_("No wireless interface has been found"), level=2)
            self.labels['networkinfo'] = Gtk.Label()
            scroll.add(self.labels['networkinfo'])
            self.update_single_network_info()

        self.labels['main_box'].pack_start(scroll, True, True, 0)
        self.content.add(self.labels['main_box'])

    def popup_callback(self, msg, level=3):
        self._screen.show_popup_message(msg, level)

    def load_networks(self):
        for net in self.sdbus_nm.get_networks():
            self.add_network(net['BSSID'])
        GLib.timeout_add_seconds(10, self._gtk.Button_busy, self.reload_button, False)
        self.content.show_all()
        return False

    def add_network(self, bssid):
        if bssid in self.network_rows:
            return

        net = next(net for net in self.sdbus_nm.get_networks() if bssid == net['BSSID'])
        ssid = net['SSID']

        connect = self._gtk.Button("load", None, "color3", self.bts)
        connect.connect("clicked", self.connect_network, ssid)
        connect.set_hexpand(False)
        connect.set_halign(Gtk.Align.END)

        delete = self._gtk.Button("delete", None, "color3", self.bts)
        delete.connect("clicked", self.remove_confirm_dialog, ssid, bssid)
        delete.set_hexpand(False)
        delete.set_halign(Gtk.Align.END)

        buttons = Gtk.Box(spacing=5)

        name = Gtk.Label(hexpand=True, halign=Gtk.Align.START, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        if bssid == self.sdbus_nm.get_connected_bssid():
            ssid += ' (' + _("Connected") + ')'
            name.set_markup(f"<big><b>{ssid}</b></big>")
        else:
            name.set_markup(f"<b>{ssid}</b>")
        if net['known']:
            buttons.add(delete)
        buttons.add(connect)

        info = Gtk.Label(halign=Gtk.Align.START)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True,
                         halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        labels.add(name)
        labels.add(info)
        icon = self._gtk.Image()

        self.network_rows[bssid] = Gtk.Box(spacing=5, hexpand=True, vexpand=False)
        self.network_rows[bssid].get_style_context().add_class("frame-item")
        self.network_rows[bssid].add(icon)
        self.network_rows[bssid].add(labels)
        self.network_rows[bssid].add(buttons)

        self.networks[bssid] = {
            "connect": connect,
            "delete": delete,
            "icon": icon,
            "info": info,
            "name": name,
            "row": self.network_rows[bssid],
        }

        self.network_list.add(self.network_rows[bssid])

    def remove_confirm_dialog(self, widget, ssid, bssid):

        label = Gtk.Label(wrap=True, vexpand=True)
        label.set_markup(_("Do you want to forget or disconnect %s?") % ssid)
        buttons = [
            {"name": _("Forget"), "response": Gtk.ResponseType.OK, "style": 'dialog-warning'},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": 'dialog-error'},
        ]
        if bssid == self.sdbus_nm.get_connected_bssid():
            buttons.insert(0, {"name": _("Disconnect"), "response": Gtk.ResponseType.APPLY, "style": 'dialog-info'})
        self._gtk.Dialog(_("Remove network"), buttons, label, self.confirm_removal, ssid)

    def confirm_removal(self, dialog, response_id, ssid):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        bssid = self.sdbus_nm.get_bssid_from_ssid(ssid)
        self.remove_network_from_list(bssid)
        if response_id == Gtk.ResponseType.OK:
            logging.info(f"Deleting {ssid}")
            self.sdbus_nm.delete_network(ssid)
        if response_id == Gtk.ResponseType.APPLY:
            logging.info(f"Disconnecting {ssid}")
            self.sdbus_nm.disconnect_network()

    def add_new_network(self, widget, ssid):
        self._screen.remove_keyboard()
        psk = self.labels['network_psk'].get_text()
        identity = self.labels['network_identity'].get_text()
        eap_method = self.get_dropdown_value(self.labels['network_eap_method'])
        phase2 = self.get_dropdown_value(self.labels['network_phase2'])
        logging.debug(f"{phase2=}")
        logging.debug(f"{eap_method=}")
        result = self.sdbus_nm.add_network(ssid, psk, eap_method, identity, phase2)
        if "error" in result:
            self._screen.show_popup_message(result["message"])
            if result["error"] == "psk_invalid":
                return
        else:
            self.connect_network(widget, ssid, showadd=False)
        self.close_add_network()

    def get_dropdown_value(self, dropdown, default=None):
        tree_iter = dropdown.get_active_iter()
        model = dropdown.get_model()
        result = model[tree_iter][0]
        return result if result != "disabled" else None

    def back(self):
        if self.show_add:
            self.close_add_network()
            return True
        return False

    def close_add_network(self):
        if not self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels['main_box'])
        self.content.show()
        for i in ['add_network', 'network_psk', 'network_identity']:
            if i in self.labels:
                del self.labels[i]
        self.show_add = False

    def connect_network(self, widget, ssid, showadd=True):
        self.deactivate()
        if showadd and not self.sdbus_nm.is_known(ssid):
            sec_type = self.sdbus_nm.get_security_type(ssid)
            if sec_type == "Open" or "OWE" in sec_type:
                logging.debug("Network is Open do not show psk")
                result = self.sdbus_nm.add_network(ssid, '')
                if "error" in result:
                    self._screen.show_popup_message(result["message"])
            else:
                self.show_add_network(widget, ssid)
            self.activate()
            return
        bssid = self.sdbus_nm.get_bssid_from_ssid(ssid)
        if bssid and bssid in self.network_rows:
            self.remove_network_from_list(bssid)
        self.sdbus_nm.connect(ssid)
        self.reload_networks()

    def remove_network_from_list(self, bssid):
        if bssid not in self.network_rows:
            logging.error(f"{bssid} not in rows")
            return
        self.network_list.remove(self.network_rows[bssid])
        del self.network_rows[bssid]
        del self.networks[bssid]
        return

    def on_popup_shown(self, combo_box, params):
        if combo_box.get_property("popup-shown"):
            logging.debug("Dropdown popup show")
            self.last_drop_time = datetime.now()
        else:
            elapsed = (datetime.now() - self.last_drop_time).total_seconds()
            if elapsed < 0.2:
                logging.debug(f"Dropdown closed too fast ({elapsed}s)")
                GLib.timeout_add(50, combo_box.popup)
                return
            logging.debug("Dropdown popup close")

    def show_add_network(self, widget, ssid):
        if self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)

        if "add_network" in self.labels:
            del self.labels['add_network']

        eap_method = Gtk.ComboBoxText(hexpand=True)
        eap_method.connect("notify::popup-shown", self.on_popup_shown)
        for method in ("peap", "ttls", "pwd", "leap", "md5"):
            eap_method.append(method, method.upper())
        self.labels['network_eap_method'] = eap_method
        eap_method.set_active(0)

        phase2 = Gtk.ComboBoxText(hexpand=True)
        phase2.connect("notify::popup-shown", self.on_popup_shown)
        for method in ("mschapv2", "gtc", "pap", "chap", "mschap", "disabled"):
            phase2.append(method, method.upper())
        self.labels['network_phase2'] = phase2
        phase2.set_active(0)

        auth_selection_box = Gtk.Box(no_show_all=True)
        auth_selection_box.add(self.labels['network_eap_method'])
        auth_selection_box.add(self.labels['network_phase2'])

        self.labels['network_identity'] = Gtk.Entry(hexpand=True, no_show_all=True)
        self.labels['network_identity'].connect("focus-in-event", self._screen.show_keyboard)

        self.labels['network_psk'] = Gtk.Entry(hexpand=True)
        self.labels['network_psk'].connect("activate", self.add_new_network, ssid)
        self.labels['network_psk'].connect("focus-in-event", self._screen.show_keyboard)

        save = self._gtk.Button("sd", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.add_new_network, ssid)

        user_label = Gtk.Label(label=_("User"), hexpand=False, no_show_all=True)
        auth_grid = Gtk.Grid()
        auth_grid.attach(user_label, 0, 0, 1, 1)
        auth_grid.attach(self.labels['network_identity'], 1, 0, 1, 1)
        auth_grid.attach(Gtk.Label(label=_("Password"), hexpand=False), 0, 1, 1, 1)
        auth_grid.attach(self.labels['network_psk'], 1, 1, 1, 1)
        auth_grid.attach(save, 2, 0, 1, 2)

        if "802.1x" in self.sdbus_nm.get_security_type(ssid):
            user_label.show()
            self.labels['network_eap_method'].show()
            self.labels['network_phase2'].show()
            self.labels['network_identity'].show()
            auth_selection_box.show()

        self.labels['add_network'] = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=5, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=True
        )
        self.labels['add_network'].add(Gtk.Label(label=_("Connecting to %s") % ssid))
        self.labels['add_network'].add(auth_selection_box)
        self.labels['add_network'].add(auth_grid)
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels['add_network'])
        self.content.add(scroll)
        self.labels['network_psk'].grab_focus_without_selecting()
        self.content.show_all()
        self.show_add = True

    def update_all_networks(self):
        self.interface = self.sdbus_nm.get_primary_interface()
        self.labels['interface'].set_text(_("Interface") + f': {self.interface}')
        self.labels['ip'].set_text(f"IP: {self.sdbus_nm.get_ip_address()}")
        nets = self.sdbus_nm.get_networks()
        remove = [bssid for bssid in self.network_rows.keys() if bssid not in [net['BSSID'] for net in nets]]
        for bssid in remove:
            self.remove_network_from_list(bssid)
        for net in nets:
            if net['BSSID'] not in self.network_rows.keys():
                self.add_network(net['BSSID'])
            self.update_network_info(net)
        for i, net in enumerate(nets):
            for child in self.network_list.get_children():
                if child == self.network_rows[net['BSSID']]:
                    self.network_list.reorder_child(child, i)
        self.network_list.show_all()
        return True

    def update_network_info(self, net):
        if net['BSSID'] not in self.network_rows.keys() or net['BSSID'] not in self.networks:
            logging.info(f"Unknown SSID {net['SSID']}")
            return
        info = _("Password saved") + '\n' if net['known'] else ""
        chan = _("Channel") + f' {net["channel"]}'
        max_bitrate = _("Max:") + f"{self.format_speed(net['max_bitrate'])}"
        self.networks[net['BSSID']]['icon'].set_from_pixbuf(self.get_signal_strength_icon(net["signal_level"]))
        self.networks[net['BSSID']]['info'].set_markup(
            "<small>"
            f"{info}"
            f"{net['security']}\n"
            f"{max_bitrate}\n"
            f"{net['frequency']} Ghz  {chan}  {net['signal_level']} %\n"
            f"{net['BSSID']}"
            "</small>"
        )

    def get_signal_strength_icon(self, signal_level):
        # networkmanager uses percentage not dbm
        if signal_level > 75:
            return self.wifi_signal_icons['excellent']
        elif signal_level > 60:
            return self.wifi_signal_icons['good']
        elif signal_level > 30:
            return self.wifi_signal_icons['fair']
        else:
            return self.wifi_signal_icons['weak']

    def update_single_network_info(self):
        self.labels['networkinfo'].set_markup(
            f'<b>{self.interface}</b>\n\n'
            + '<b>' + _("Hostname") + f':</b> {os.uname().nodename}\n'
            f'<b>IPv4:</b> {self.sdbus_nm.get_ip_address()}\n'
        )
        self.labels['networkinfo'].show_all()
        return True

    def reload_networks(self, widget=None):
        self.deactivate()
        del self.network_rows
        self.network_rows = {}
        for child in self.network_list.get_children():
            self.network_list.remove(child)
        if self.sdbus_nm is not None and self.sdbus_nm.wifi:
            if widget:
                self._gtk.Button_busy(widget, True)
            self.sdbus_nm.rescan()
            self.load_networks()
        self.activate()

    def activate(self):
        if self.sdbus_nm is None:
            return
        if self.update_timeout is None:
            if self.sdbus_nm.wifi:
                if self.reload_button.get_sensitive():
                    self._gtk.Button_busy(self.reload_button, True)
                    self.sdbus_nm.rescan()
                    self.load_networks()
                self.update_all_networks()
                self.update_timeout = GLib.timeout_add_seconds(5, self.update_all_networks)
            else:
                self.update_single_network_info()
                self.update_timeout = GLib.timeout_add_seconds(5, self.update_single_network_info)

    def deactivate(self):
        if self.sdbus_nm is None:
            return
        if self.update_timeout is not None:
            GLib.source_remove(self.update_timeout)
            self.update_timeout = None
        if self.sdbus_nm.wifi:
            self.sdbus_nm.enable_monitoring(False)

    def toggle_wifi(self, switch, gparams):
        enable = switch.get_active()
        logging.info(f"WiFi {enable}")
        self.sdbus_nm.toggle_wifi(enable)
        if enable:
            self.reload_button.show()
            self.reload_networks()
        else:
            self.reload_button.hide()
