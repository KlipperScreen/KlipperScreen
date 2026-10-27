import logging
import os
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from ks_includes.screen_panel import ScreenPanel

try:
    from ks_includes.gio_nm import NetworkManagerClient, NetworkSnapshot
except (ImportError, ValueError) as error:
    NetworkManagerClient = None
    NetworkSnapshot = None
    NM_IMPORT_ERROR = error
else:
    NM_IMPORT_ERROR = None


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title or _("Network"))
        self.last_drop_time = datetime.now()
        self.show_add = False
        self.interface = None
        self.device_signature = ()
        self.network_rows = {}
        self.networks = {}
        self.snapshot = NetworkSnapshot() if NetworkSnapshot is not None else None
        self.operation_pending = False
        self.scan_busy = None
        self.ready = False
        self.nm = None
        self.wifi_signal_icons = {
            "excellent": self._gtk.PixbufFromIcon("wifi_excellent"),
            "good": self._gtk.PixbufFromIcon("wifi_good"),
            "fair": self._gtk.PixbufFromIcon("wifi_fair"),
            "weak": self._gtk.PixbufFromIcon("wifi_weak"),
        }
        self.interface_box = Gtk.Box()
        self.labels["ip"] = Gtk.Label(hexpand=True)
        self.reload_button = self._gtk.Button("refresh", None, "color1", self.bts)
        self.reload_button.set_no_show_all(True)
        self.reload_button.connect("clicked", self.reload_networks)
        self.reload_button.set_hexpand(False)
        self.wifi_toggle_switch = Gtk.Switch(
            width_request=round(self._gtk.font_size * 2),
            height_request=round(self._gtk.font_size),
        )
        self.wifi_toggle_switch.set_no_show_all(True)
        self.wifi_handler = self.wifi_toggle_switch.connect("notify::active", self.toggle_wifi)
        self.wifi_toggle_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.wifi_toggle_box.add(self.wifi_toggle_switch)
        sbox = Gtk.Box(hexpand=True, vexpand=False)
        if not self._screen.vertical_mode:
            sbox.add(Gtk.Label(_("Interface") + ": "))
        sbox.add(self.interface_box)
        sbox.add(self.labels["ip"])
        sbox.add(self.reload_button)
        sbox.add(self.wifi_toggle_box)
        self.network_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True
        )
        self.labels["network_list_status"] = Gtk.Label(
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, vexpand=True
        )
        self.labels["networkinfo"] = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.scroll = self._gtk.ScrolledWindow()
        self.labels["main_box"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.labels["main_box"].pack_start(sbox, False, False, 5)
        self.labels["main_box"].pack_start(self.scroll, True, True, 0)
        self.content.add(self.labels["main_box"])
        self._set_empty_message(_("Connecting"))
        self._replace_scroll(self.network_list)
        if NM_IMPORT_ERROR is not None:
            self._render_error(str(NM_IMPORT_ERROR))
            return
        self.nm = NetworkManagerClient(self._on_snapshot, self._on_operation)
        self.content.show_all()
        self._show_wifi_controls(False, False)

    def _replace_scroll(self, child):
        current = self.scroll.get_child()
        if current is not None:
            content = current.get_child() if isinstance(current, Gtk.Viewport) else current
            if content == child:
                return
        for current in self.scroll.get_children():
            self.scroll.remove(current)
        self.scroll.add(child)
        child.show_all()

    def _render_error(self, message):
        self.ready = False
        self._show_wifi_controls(False, False)
        self.labels["networkinfo"].set_markup(
            "<b>"
            + _("Failed to initialize")
            + "</b>\n\n"
            + _("This panel needs NetworkManager and its GObject introspection bindings")
            + "\n\n"
            + GLib.markup_escape_text(message)
        )
        self._replace_scroll(self.labels["networkinfo"])

    def _on_operation(self, result):
        if result.operation == "initialization":
            self._render_error(result.message)
        if result.operation != "state":
            self._set_operation_pending(False)
        if result.operation == "connect" and result.success and self.show_add:
            self.close_add_network()
        if result.operation == "wifi" and not result.success:
            self._sync_wifi_switch()
        if result.message:
            self._screen.show_popup_message(result.message, 1 if result.success else 3)

    def _on_snapshot(self, snapshot):
        self.ready = True
        self.snapshot = snapshot
        if self.interface != snapshot.interface:
            self.interface = snapshot.interface
            self._clear_rows()
        signature = tuple((device.interface, device.wireless) for device in snapshot.devices)
        if signature != self.device_signature:
            self.device_signature = signature
            self._update_interface_widget()
        wireless = self._selected_device() is not None
        self._show_wifi_controls(wireless, snapshot.wireless_enabled)
        self._sync_wifi_switch()
        self.update_ip_label()
        if wireless:
            self._replace_scroll(self.network_list)
            self._refresh_network_rows()
        elif snapshot.devices:
            self._update_wired_info()
        else:
            self.labels["networkinfo"].set_text(_("No network devices available"))
            self._replace_scroll(self.labels["networkinfo"])
        self._set_scan_busy(snapshot.scanning and snapshot.wireless_enabled)
        self._set_row_sensitivity()
        self.content.show_all()
        self._show_wifi_controls(wireless, snapshot.wireless_enabled)

    def _selected_device(self):
        return next(
            (
                device
                for device in self.snapshot.devices
                if device.interface == self.interface and device.wireless
            ),
            None,
        )

    def _update_interface_widget(self):
        for child in self.interface_box.get_children():
            self.interface_box.remove(child)
        if len(self.snapshot.devices) <= 1:
            widget = Gtk.Label(hexpand=True, halign=Gtk.Align.START)
            widget.set_text(self.interface or "?")
        else:
            widget = Gtk.ComboBoxText(hexpand=True)
            for device in self.snapshot.devices:
                widget.append(device.interface, device.interface)
            self.iface_handler = widget.connect("changed", self.iface_changed)
            widget.handler_block(self.iface_handler)
            widget.set_active_id(self.interface)
            widget.handler_unblock(self.iface_handler)
        self.labels["interface"] = widget
        self.interface_box.add(widget)
        self.interface_box.show_all()

    def _show_wifi_controls(self, wireless, enabled):
        self.wifi_toggle_box.set_visible(wireless)
        self.wifi_toggle_switch.set_visible(wireless)
        self.wifi_toggle_switch.set_sensitive(wireless)
        self.reload_button.set_visible(wireless and enabled)

    def _sync_wifi_switch(self):
        if self.snapshot is None:
            return
        self.wifi_toggle_switch.handler_block(self.wifi_handler)
        self.wifi_toggle_switch.set_active(self.snapshot.wireless_enabled)
        self.wifi_toggle_switch.handler_unblock(self.wifi_handler)

    def _set_scan_busy(self, busy):
        if busy == self.scan_busy:
            return
        self.scan_busy = busy
        self._gtk.Button_busy(self.reload_button, busy)

    def _set_operation_pending(self, pending):
        self.operation_pending = pending
        self._set_row_sensitivity()
        if "interface" in self.labels:
            self.labels["interface"].set_sensitive(not pending)
        if self.show_add:
            for name in ("network_psk", "network_identity", "save_network"):
                if name in self.labels:
                    self.labels[name].set_sensitive(not pending)

    def _set_row_sensitivity(self):
        for widgets in self.networks.values():
            widgets["row"].set_sensitive(not self.operation_pending)
        if self.snapshot is not None:
            self.reload_button.set_sensitive(
                not self.operation_pending and not self.snapshot.scanning
            )

    def update_ip_label(self):
        device = next(
            (item for item in self.snapshot.devices if item.interface == self.interface), None
        )
        address = device.ip_address if device else "?"
        self.labels["ip"].set_text(address if self._screen.vertical_mode else f"IP: {address}")

    def _update_wired_info(self):
        device = next(
            (item for item in self.snapshot.devices if item.interface == self.interface), None
        )
        self.labels["networkinfo"].set_markup(
            f"<b>{_('Interface')}:</b> {GLib.markup_escape_text(self.interface or '?')}\n\n"
            f"<b>{_('Hostname')}:</b> {GLib.markup_escape_text(os.uname().nodename)}\n"
            f"<b>IPv4:</b> {device.ip_address if device else '?'}"
        )
        self._replace_scroll(self.labels["networkinfo"])

    def _clear_rows(self):
        for child in self.network_list.get_children():
            self.network_list.remove(child)
        self.network_rows.clear()
        self.networks.clear()

    def _refresh_network_rows(self):
        current_bssids = {network.bssid for network in self.snapshot.networks}
        for bssid in tuple(self.network_rows):
            if bssid not in current_bssids:
                self.network_list.remove(self.network_rows.pop(bssid))
                del self.networks[bssid]
        for index, network in enumerate(self.snapshot.networks):
            if network.bssid not in self.network_rows:
                self._add_network_row(network)
            self._update_network_row(network)
            self.network_list.reorder_child(self.network_rows[network.bssid], index)
        status = self.labels["network_list_status"]
        if not self.snapshot.networks:
            self._set_empty_message(_("No network devices available"))
        elif status.get_parent() is not None:
            self.network_list.remove(status)
        self.network_list.show_all()

    def _set_empty_message(self, message):
        status = self.labels["network_list_status"]
        status.set_text(message)
        if status.get_parent() is None:
            self.network_list.pack_end(status, True, True, 0)
        status.show()

    def _add_network_row(self, network):
        connect = self._gtk.Button("load", None, "color3", self.bts)
        connect.connect("clicked", self.connect_network, network.ssid)
        connect.set_hexpand(False)
        connect.set_halign(Gtk.Align.END)
        delete = self._gtk.Button("delete", None, "color3", self.bts)
        delete.connect("clicked", self.remove_confirm_dialog, network.ssid, network.bssid)
        delete.set_no_show_all(True)
        delete.set_hexpand(False)
        delete.set_halign(Gtk.Align.END)
        buttons = Gtk.Box(spacing=5)
        buttons.add(delete)
        buttons.add(connect)
        name = Gtk.Label(
            hexpand=True,
            halign=Gtk.Align.START,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
        )
        info = Gtk.Label(halign=Gtk.Align.START)
        labels = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            vexpand=True,
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
        )
        labels.add(name)
        labels.add(info)
        icon = self._gtk.Image()
        row = Gtk.Box(spacing=5, hexpand=True, vexpand=False)
        row.get_style_context().add_class("frame-item")
        row.add(icon)
        row.add(labels)
        row.add(buttons)
        self.network_rows[network.bssid] = row
        self.networks[network.bssid] = {
            "connect": connect,
            "delete": delete,
            "icon": icon,
            "info": info,
            "name": name,
            "row": row,
        }
        self.network_list.add(row)

    def _update_network_row(self, network):
        widgets = self.networks[network.bssid]
        ssid = GLib.markup_escape_text(network.ssid)
        if network.connected:
            ssid += " (" + _("Connected") + ")"
            widgets["name"].set_markup(f"<big><b>{ssid}</b></big>")
        else:
            widgets["name"].set_markup(f"<b>{ssid}</b>")
        widgets["delete"].set_visible(network.known)
        widgets["icon"].set_from_pixbuf(self.get_signal_strength_icon(network.signal_level))
        info = (
            f"{network.frequency} GHz  {_('Channel')} {network.channel}  "
            f"{network.signal_level} %\n{network.security}\n{network.bssid}"
        )
        widgets["info"].set_markup(f"<small>{GLib.markup_escape_text(info)}</small>")

    def get_signal_strength_icon(self, signal_level):
        if signal_level > 75:
            return self.wifi_signal_icons["excellent"]
        if signal_level > 60:
            return self.wifi_signal_icons["good"]
        if signal_level > 30:
            return self.wifi_signal_icons["fair"]
        return self.wifi_signal_icons["weak"]

    def iface_changed(self, combo):
        selected = combo.get_active_id()
        if selected is None or selected == self.interface:
            return
        logging.info("Selected interface: %s", selected)
        if not self.nm.select_interface(selected):
            combo.handler_block(self.iface_handler)
            combo.set_active_id(self.interface)
            combo.handler_unblock(self.iface_handler)
            return
        self.interface = selected
        self._clear_rows()
        if self._selected_device() is None:
            self._update_wired_info()

    def reload_networks(self, _widget=None):
        if self.ready and self._selected_device() is not None:
            self.nm.request_scan()

    def remove_confirm_dialog(self, _widget, ssid, bssid):
        label = Gtk.Label(wrap=True, vexpand=True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        message = _("Do you want to forget or disconnect %s?") % GLib.markup_escape_text(ssid)
        label.set_markup(message)
        buttons = [
            {"name": _("Forget"), "response": Gtk.ResponseType.OK, "style": "dialog-warning"},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": "dialog-error"},
        ]
        network = next((item for item in self.snapshot.networks if item.bssid == bssid), None)
        if network is not None and network.connected:
            buttons.insert(
                0,
                {
                    "name": _("Disconnect"),
                    "response": Gtk.ResponseType.APPLY,
                    "style": "dialog-info",
                },
            )
        self._gtk.Dialog(_("Remove network"), buttons, label, self.confirm_removal, ssid)

    def confirm_removal(self, dialog, response_id, ssid):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.CANCEL:
            return
        self._set_operation_pending(True)
        if response_id == Gtk.ResponseType.OK:
            logging.info("Deleting %s", ssid)
            if not self.nm.delete_network(ssid):
                self._set_operation_pending(False)
        elif response_id == Gtk.ResponseType.APPLY:
            logging.info("Disconnecting %s", ssid)
            if not self.nm.disconnect():
                self._set_operation_pending(False)

    def _network(self, ssid):
        return next((network for network in self.snapshot.networks if network.ssid == ssid), None)

    def connect_network(self, _widget, ssid):
        network = self._network(ssid)
        if network is None:
            self._screen.show_popup_message(_("Network not found"), 2)
            return
        if not network.known and network.security != "Open" and "OWE" not in network.security:
            self.show_add_network(ssid)
            return
        self._set_operation_pending(True)
        if not self.nm.connect(ssid, psk="" if not network.known else None):
            self._set_operation_pending(False)

    def add_new_network(self, _widget, ssid):
        self._screen.remove_keyboard()
        self._set_operation_pending(True)
        connected = self.nm.connect(
            ssid,
            psk=self.labels["network_psk"].get_text(),
            eap_method=self.get_dropdown_value(self.labels["network_eap_method"]),
            identity=self.labels["network_identity"].get_text(),
            phase2=self.get_dropdown_value(self.labels["network_phase2"]),
        )
        if not connected:
            self._set_operation_pending(False)

    @staticmethod
    def get_dropdown_value(dropdown):
        tree_iter = dropdown.get_active_iter()
        if tree_iter is None:
            return None
        value = dropdown.get_model()[tree_iter][0]
        return value if value != "disabled" else None

    def show_add_network(self, ssid):
        if self.show_add:
            return
        for child in self.content.get_children():
            self.content.remove(child)
        eap_method = Gtk.ComboBoxText(hexpand=True)
        eap_method.connect("notify::popup-shown", self.on_popup_shown)
        for method in ("peap", "ttls", "pwd", "leap", "md5"):
            eap_method.append(method, method.upper())
        eap_method.set_active(0)
        self.labels["network_eap_method"] = eap_method
        phase2 = Gtk.ComboBoxText(hexpand=True)
        phase2.connect("notify::popup-shown", self.on_popup_shown)
        for method in ("mschapv2", "gtc", "pap", "chap", "disabled"):
            phase2.append(method, method.upper())
        phase2.set_active(0)
        self.labels["network_phase2"] = phase2
        auth_selection_box = Gtk.Box(no_show_all=True)
        auth_selection_box.add(eap_method)
        auth_selection_box.add(phase2)
        self.labels["network_identity"] = Gtk.Entry(hexpand=True, no_show_all=True)
        self.labels["network_identity"].connect("touch-event", self._screen.show_keyboard)
        self.labels["network_identity"].connect("button-press-event", self._screen.show_keyboard)
        self.labels["network_psk"] = Gtk.Entry(hexpand=True)
        self.labels["network_psk"].connect("activate", self.add_new_network, ssid)
        self.labels["network_psk"].connect("touch-event", self._screen.show_keyboard)
        self.labels["network_psk"].connect("button-press-event", self._screen.show_keyboard)
        save = self._gtk.Button("sd", _("Save"), "color3")
        save.set_hexpand(False)
        save.connect("clicked", self.add_new_network, ssid)
        self.labels["save_network"] = save
        user_label = Gtk.Label(label=_("User"), hexpand=False, no_show_all=True)
        auth_grid = Gtk.Grid()
        auth_grid.attach(user_label, 0, 0, 1, 1)
        auth_grid.attach(self.labels["network_identity"], 1, 0, 1, 1)
        auth_grid.attach(Gtk.Label(label=_("Password"), hexpand=False), 0, 1, 1, 1)
        auth_grid.attach(self.labels["network_psk"], 1, 1, 1, 1)
        auth_grid.attach(save, 2, 0, 1, 2)
        network = self._network(ssid)
        if network is not None and "802.1x" in network.security:
            user_label.show()
            eap_method.show()
            phase2.show()
            self.labels["network_identity"].show()
            auth_selection_box.show()
        self.labels["add_network"] = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=5,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            vexpand=True,
        )
        self.labels["add_network"].add(Gtk.Label(label=_("Connecting to %s") % ssid))
        self.labels["add_network"].add(auth_selection_box)
        self.labels["add_network"].add(auth_grid)
        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.labels["add_network"])
        self.content.add(scroll)
        self.labels["network_psk"].grab_focus_without_selecting()
        self.content.show_all()
        self.show_add = True

    def close_add_network(self):
        if not self.show_add:
            return
        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)
        self.content.add(self.labels["main_box"])
        for name in (
            "add_network",
            "network_psk",
            "network_identity",
            "network_eap_method",
            "network_phase2",
            "save_network",
        ):
            self.labels.pop(name, None)
        self.show_add = False
        self.content.show_all()
        self._show_wifi_controls(
            self._selected_device() is not None, self.snapshot.wireless_enabled
        )

    def back(self):
        if self.show_add:
            self.close_add_network()
            return True
        return False

    def on_popup_shown(self, combo_box, _params):
        if combo_box.get_property("popup-shown"):
            self.last_drop_time = datetime.now()
        elif (datetime.now() - self.last_drop_time).total_seconds() < 0.2:
            GLib.timeout_add(50, combo_box.popup)

    def activate(self):
        if self.nm is None:
            return
        self.nm.activate()
        if self.nm.snapshot.interface is not None:
            self._on_snapshot(self.nm.snapshot)

    def deactivate(self):
        if self.nm is not None:
            self.nm.deactivate()
        self._set_operation_pending(False)

    def toggle_wifi(self, switch, _params):
        if self.nm is not None and self.ready:
            logging.info("Wi-Fi %s", switch.get_active())
            self.nm.set_wireless_enabled(switch.get_active())
