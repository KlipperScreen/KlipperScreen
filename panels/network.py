import asyncio
import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from datetime import datetime

from gi.repository import GLib, Gtk, Pango
from sdbus_async.networkmanager import enums

from ks_includes import async_utils
from ks_includes.screen_panel import ScreenPanel
from ks_includes.sdbus_nm import SdbusNm


class Panel(ScreenPanel):
    """Wi-Fi / network panel."""

    def __init__(self, screen, title):
        title = title or _("Network")
        super().__init__(screen, title)
        self.last_drop_time = datetime.now()
        self.show_add = False
        self._destroyed = False
        self._refresh_token = 0
        self._refreshing = False
        self._nm_tasks = []
        self.update_timeout = None
        self.interface = None
        self.network_devices = []
        self.network_interfaces = []
        self.wifi_signal_icons = {
            "excellent": self._gtk.PixbufFromIcon("wifi_excellent"),
            "good": self._gtk.PixbufFromIcon("wifi_good"),
            "fair": self._gtk.PixbufFromIcon("wifi_fair"),
            "weak": self._gtk.PixbufFromIcon("wifi_weak"),
        }
        try:
            self.sdbus_nm = SdbusNm(self.popup_callback)
        except Exception as e:
            logging.exception("Failed to initialize")
            self.sdbus_nm = None
            self.error_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True
            )
            message = (
                _("Failed to initialize")
                + "\n"
                + "This panel needs NetworkManager installed into the system\n"
                + "And the appropriate permissions, without them it will not function.\n"
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

        # React to Wi-Fi device state changes so the "(Connected)" label updates
        # promptly on connect/disconnect, without waiting for the periodic poll.
        self.sdbus_nm.register_state_callback(self.on_wifi_state_changed)

        # --- static skeleton --------------------------
        self.network_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True
        )
        self.network_rows = {}
        self.networks = {}

        self.labels["ip"] = Gtk.Label(hexpand=True)

        self.reload_button = self._gtk.Button("refresh", None, "color1", self.bts)
        self.reload_button.set_no_show_all(True)
        self.reload_button.hide()
        self.reload_button.connect("clicked", self.reload_networks)
        self.reload_button.set_hexpand(False)

        # Constructed inactive; real state applied in ``_async_init``.
        self.wifi_toggle_switch = Gtk.Switch(
            width_request=round(self._gtk.font_size * 2),
            height_request=round(self._gtk.font_size),
            active=False,
        )
        self.wifi_toggle_switch.set_no_show_all(True)
        self.wifi_toggle_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.wifi_toggle_box.add(self.wifi_toggle_switch)

        self.top_bar = Gtk.Box(hexpand=True, vexpand=False)
        if not self._screen.vertical_mode:
            self.top_bar.add(Gtk.Label(_("Interface") + ": "))
        self.iface_pos = 0 if self._screen.vertical_mode else 1
        self.labels["interface"] = Gtk.Label(hexpand=True, halign=Gtk.Align.START)
        self.top_bar.add(self.labels["interface"])
        self.top_bar.add(self.labels["ip"])
        self.top_bar.add(self.reload_button)
        self.top_bar.add(self.wifi_toggle_box)

        self.scroll = self._gtk.ScrolledWindow()
        self.labels["main_box"] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.labels["networkinfo"] = Gtk.Label()

        self.labels["main_box"].pack_start(self.top_bar, False, False, 5)
        self.labels["main_box"].pack_start(self.scroll, True, True, 0)
        self.content.add(self.labels["main_box"])

        # --- async discovery ----------------------------------------------
        self.schedule(self._async_init())

    # -- task helpers ------------------------------------------------------

    def schedule(self, coro, *, name=None):
        """Schedule *coro* on the persistent loop and track it for teardown."""
        task = async_utils.schedule(coro, name=name)
        self._nm_tasks.append(task)

        def _on_done(task):
            if task in self._nm_tasks:
                self._nm_tasks.remove(task)

        task.add_done_callback(_on_done)
        return task

    def _g(self, fn, *args, **kwargs):
        """Marshal a GTK-only call onto the GTK main thread."""
        return asyncio.wrap_future(async_utils.on_gtk_thread(fn, *args, **kwargs))

    def _next_refresh_token(self):
        self._refresh_token += 1
        return self._refresh_token

    def _refresh_token_valid(self, token):
        return not self._destroyed and token == self._refresh_token

    def _refresh_stopped(self, token):
        """True if the panel is torn down or a newer refresh has superseded this one.

        Equivalent to ``not self._refresh_token_valid(token)`` — validity already
        fails when destroyed — kept as a named guard for the many await points
        that must abort a stale refresh.
        """
        return not self._refresh_token_valid(token)

    def _pause_refresh(self):
        """Stop the periodic refresh and invalidate any in-flight refresh."""
        if self.update_timeout is not None:
            GLib.source_remove(self.update_timeout)
            self.update_timeout = None
        self._next_refresh_token()

    def _resume_refresh(self):
        """Re-arm the periodic refresh timer (idempotent)."""
        if self._destroyed or self.sdbus_nm is None or self.update_timeout is not None:
            return
        selected_dev = next(
            (d for d in self.network_devices if d["interface"] == self.interface), None
        )
        if selected_dev and selected_dev["type"] == enums.DeviceType.WIFI:
            self.update_all_networks()
            self.update_timeout = GLib.timeout_add_seconds(5, self.update_all_networks)
        elif self.interface is not None:
            self.schedule(self._async_update_wired())
            self.update_timeout = GLib.timeout_add_seconds(5, self._periodic_wired)

    def _finish_refresh(self):
        self._refreshing = False
        self._resume_refresh()

    def _periodic_wired(self):
        if self._refreshing or self._destroyed:
            return True
        self.schedule(self._async_update_wired())
        return True

    # -- lifecycle ---------------------------------------------------------

    def popup_callback(self, msg, level=3):
        self._screen.show_popup_message(msg, level)

    async def _async_init(self):
        if self._destroyed or self.sdbus_nm is None:
            return

        try:
            self.network_interfaces = await self.sdbus_nm.get_interfaces()
            logging.info(f"network panel: get_interfaces -> {self.network_interfaces}")
            self.network_devices = await self.sdbus_nm.get_all_network_devices()
            logging.info(f"network panel: get_all_network_devices -> {self.network_devices}")
            self.interface = await self.sdbus_nm.get_primary_interface()
            logging.info(f"network panel: get_primary_interface -> {self.interface}")

            # Resolve the wireless device up front.
            wifi_ready = await self.sdbus_nm.initialize()

            await self._g(self._build_interface_selector)
            await self.update_ip_label(self.interface)

            has_selector = len(self.network_devices) > 1
            primary_is_wifi = self.interface and any(
                d["interface"] == self.interface and d["type"] == enums.DeviceType.WIFI
                for d in self.network_devices
            )

            # Apply the saved Wi-Fi state before wiring the toggle handler.
            try:
                enabled = await self.sdbus_nm.is_wifi_enabled()
                await self._g(self.wifi_toggle_switch.set_active, enabled)
            except Exception:
                logging.exception("network panel: Failed to read wifi state")
            await self._g(self.wifi_toggle_switch.connect, "notify::active", self.toggle_wifi)

            if wifi_ready and self.sdbus_nm.wifi and primary_is_wifi:
                await self._g(self.wifi_toggle_switch.set_sensitive, True)
                await self._g(self.wifi_toggle_switch.show)
                await self._g(self.wifi_toggle_box.show)
                await self._g(self.reload_button.show)
                await self._g(self.scroll.add, self.network_list)
                self.sdbus_nm.set_connection_monitoring(True)
                self.schedule(self._async_load_networks())
            elif has_selector or len(self.network_devices) > 0:
                await self._g(self.scroll.add, self.labels["networkinfo"])
                await self.update_wired_network_info()
            else:
                await self._g(
                    self._screen.show_popup_message,
                    _("No network devices have been found"),
                    level=2,
                )
                await self._g(self.scroll.add, self.labels["networkinfo"])
                await self._g(
                    self.labels["networkinfo"].set_markup,
                    _("No network devices available"),
                )
                await self._g(self.labels["networkinfo"].show_all)

            await self._g(self.content.show_all)
        except Exception:
            logging.exception("network panel: _async_init failed")

    def _build_interface_selector(self):
        if len(self.network_devices) <= 1:
            if self.interface is not None:
                self.labels["interface"].set_text(str(self.interface))
            return
        old = self.labels["interface"]
        self.top_bar.remove(old)
        self.labels["interface"] = Gtk.ComboBoxText()
        for dev in self.network_devices:
            self.labels["interface"].append(dev["interface"], dev["interface"])
        if self.interface is not None:
            self.labels["interface"].set_active_id(self.interface)
        self.labels["interface"].connect("changed", self.iface_changed)
        self.top_bar.add(self.labels["interface"])
        self.top_bar.reorder_child(self.labels["interface"], self.iface_pos)

    # -- network listing ---------------------------------------------------

    async def _async_load_networks(self):
        if self._destroyed:
            return
        token = self._next_refresh_token()
        nets = await self.sdbus_nm.get_networks()
        if self._refresh_stopped(token):
            return
        connected_bssid = await self.sdbus_nm.get_connected_bssid()
        if self._refresh_stopped(token):
            return
        for net in nets:
            if self._refresh_stopped(token):
                return
            if "BSSID" not in net:
                continue
            await self._g(self.add_network, net, connected_bssid)
        if self._destroyed:
            return
        await self._g(self.content.show_all)

    def add_network(self, net, connected_bssid=None):
        if self._destroyed:
            return
        bssid = net["BSSID"]
        if bssid in self.network_rows:
            return

        ssid = net["SSID"]

        connect = self._gtk.Button("load", None, "color3", self.bts)
        connect.connect("clicked", self.connect_network, ssid)
        connect.set_hexpand(False)
        connect.set_halign(Gtk.Align.END)

        delete = self._gtk.Button("delete", None, "color3", self.bts)
        delete.connect("clicked", self.remove_confirm_dialog, ssid, bssid)
        delete.set_hexpand(False)
        delete.set_halign(Gtk.Align.END)

        buttons = Gtk.Box(spacing=5)

        name = Gtk.Label(
            hexpand=True, halign=Gtk.Align.START, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR
        )
        if connected_bssid is not None and bssid == connected_bssid:
            ssid += " (" + _("Connected") + ")"
            name.set_markup(f"<big><b>{ssid}</b></big>")
        else:
            name.set_markup(f"<b>{ssid}</b>")
        if net["known"]:
            buttons.add(delete)
        buttons.add(connect)

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

        self.network_rows[bssid] = Gtk.Box(spacing=5, hexpand=True, vexpand=False)
        self.network_rows[bssid].get_style_context().add_class("frame-item")
        self.network_rows[bssid].add(icon)
        self.network_rows[bssid].add(labels)
        self.network_rows[bssid].add(buttons)

        icon.set_from_pixbuf(self.get_signal_strength_icon(net["signal_level"]))
        chan = _("Channel") + f" {net['channel']}"
        info.set_markup(
            "<small>"
            f"{net['frequency']} Ghz  {chan}  {net['signal_level']} %\n"
            f"{net['security']}\n"
            f"{net['BSSID']}"
            "</small>"
        )

        self.networks[bssid] = {
            "connect": connect,
            "delete": delete,
            "icon": icon,
            "info": info,
            "name": name,
            "row": self.network_rows[bssid],
        }

        self.network_list.add(self.network_rows[bssid])

    async def update_ip_label(self, iface):
        if self._destroyed:
            return
        ip = await self.sdbus_nm.get_ip_for_interface(iface)
        if self._destroyed:
            return
        await self._g(self._render_ip_label, ip)

    def _render_ip_label(self, ip):
        if self._destroyed:
            return
        if self._screen.vertical_mode:
            self.labels["ip"].set_text(f"{ip}")
        else:
            self.labels["ip"].set_text(f"IP: {ip}")

    async def _async_iface_changed(self, selected_iface, combo):
        if self._destroyed:
            return
        old_iface = self.interface
        accepted = await self.sdbus_nm.set_selected_interface(selected_iface)
        if not accepted:
            await self._g(combo.set_active_id, old_iface)
            self.interface = old_iface
            return
        self.interface = selected_iface
        await self.update_ip_label(selected_iface)
        selected_dev = next(
            (d for d in self.network_devices if d["interface"] == selected_iface), None
        )
        is_wifi = selected_dev and selected_dev["type"] == enums.DeviceType.WIFI
        if is_wifi:
            await self._g(self.wifi_toggle_switch.set_sensitive, True)
            await self._g(self.wifi_toggle_switch.show)
            await self._g(self.wifi_toggle_box.show)
            await self._g(self.reload_button.show)
            self.sdbus_nm.set_connection_monitoring(True)
            for child in self.scroll.get_children():
                await self._g(self.scroll.remove, child)
            await self._g(self.scroll.add, self.network_list)
            await self._g(self.network_list.show_all)
            self.schedule(self._async_rescan_and_load())
        else:
            await self._g(self.wifi_toggle_switch.set_sensitive, False)
            await self._g(self.wifi_toggle_box.hide)
            await self._g(self.reload_button.hide)
            self.sdbus_nm.set_connection_monitoring(False)
            for child in self.scroll.get_children():
                await self._g(self.scroll.remove, child)
            for child in self.network_list.get_children():
                await self._g(self.network_list.remove, child)
            self.network_rows.clear()
            self.networks.clear()
            await self._g(self.scroll.add, self.labels["networkinfo"])
            await self.update_wired_network_info()

    def iface_changed(self, combo):
        selected_iface = combo.get_active_id()
        self.schedule(self._async_iface_changed(selected_iface, combo))

    def remove_confirm_dialog(self, widget, ssid, bssid):
        self.schedule(self._async_remove_confirm_dialog(ssid, bssid))

    async def _async_remove_confirm_dialog(self, ssid, bssid):
        if self._destroyed:
            return
        connected_bssid = await self.sdbus_nm.get_connected_bssid()
        if self._destroyed:
            return
        await self._g(self._render_remove_dialog, ssid, bssid, connected_bssid)

    def _render_remove_dialog(self, ssid, bssid, connected_bssid):
        if self._destroyed:
            return
        label = Gtk.Label(wrap=True, vexpand=True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_markup(_("Do you want to forget or disconnect %s?") % ssid)
        buttons = [
            {"name": _("Forget"), "response": Gtk.ResponseType.OK, "style": "dialog-warning"},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL, "style": "dialog-error"},
        ]
        if bssid == connected_bssid:
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
        if response_id == Gtk.ResponseType.OK:
            self.schedule(self._async_remove_network(ssid))
        elif response_id == Gtk.ResponseType.APPLY:
            self.schedule(self._async_disconnect())

    async def _async_remove_network(self, ssid):
        if self._destroyed:
            return
        bssid = await self.sdbus_nm.get_bssid_from_ssid(ssid)
        if bssid is not None:
            await self._g(self.remove_network_from_list, bssid)
        await self.sdbus_nm.delete_network(ssid)

    async def _async_disconnect(self):
        if self._destroyed:
            return
        await self.sdbus_nm.disconnect_network()

    def on_wifi_state_changed(self, state):
        if state in (enums.DeviceState.DISCONNECTED, enums.DeviceState.ACTIVATED):
            self.update_all_networks()

    def add_new_network(self, widget, ssid):
        self._screen.remove_keyboard()
        psk = self.labels["network_psk"].get_text()
        identity = self.labels["network_identity"].get_text()
        eap_method = self.get_dropdown_value(self.labels["network_eap_method"])
        phase2 = self.get_dropdown_value(self.labels["network_phase2"])
        self.schedule(self._async_add_new_network(widget, ssid, psk, identity, eap_method, phase2))
        self.close_add_network()

    async def _async_add_new_network(self, widget, ssid, psk, identity, eap_method, phase2):
        if self._destroyed:
            return
        result = await self.sdbus_nm.add_network(ssid, psk, eap_method, identity, phase2)
        if self._destroyed:
            return
        if "error" in result:
            await self._g(self._screen.show_popup_message, result["message"])
            if result["error"] == "psk_invalid":
                return
        else:
            self.connect_network(widget, ssid, showadd=False)

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
        self.content.add(self.labels["main_box"])
        self.content.show()
        for i in ["add_network", "network_psk", "network_identity"]:
            if i in self.labels:
                del self.labels[i]
        self.show_add = False

    def connect_network(self, widget, ssid, showadd=True):
        self._pause_refresh()
        self.schedule(self._async_connect_network(widget, ssid, showadd))

    async def _async_connect_network(self, widget, ssid, showadd):
        if self._destroyed:
            return
        token = self._next_refresh_token()
        if showadd and not await self.sdbus_nm.is_known(ssid):
            if self._refresh_stopped(token):
                return
            sec_type = await self.sdbus_nm.get_security_type(ssid)
            if self._destroyed:
                return
            if sec_type == "Open" or (sec_type and "OWE" in sec_type):
                result = await self.sdbus_nm.add_network(ssid, "")
                if self._destroyed:
                    return
                if "error" in result:
                    await self._g(self._screen.show_popup_message, result["message"])
                    self._resume_refresh()
                    return
            else:
                await self._g(self.show_add_network, widget, ssid, sec_type)
                self._resume_refresh()
                return
        if self._destroyed:
            return
        bssid = await self.sdbus_nm.get_bssid_from_ssid(ssid)
        if self._destroyed:
            return
        if widget is not None:
            await self._g(self._gtk.Button_busy, widget, True)
        # Small delay so the busy spinner shows and the click feels responsive.
        await asyncio.sleep(1)
        try:
            await self.sdbus_nm.connect(ssid)
            if self._destroyed:
                return
            if bssid and bssid in self.network_rows:
                await self._g(self.remove_network_from_list, bssid)
            self.reload_networks()
        finally:
            if widget is not None:
                await self._g(self._gtk.Button_busy, widget, False)

    def remove_network_from_list(self, bssid):
        if self._destroyed:
            return
        if bssid not in self.network_rows:
            logging.error(f"{bssid} not in rows")
            return
        self.network_list.remove(self.network_rows[bssid])
        del self.network_rows[bssid]
        del self.networks[bssid]
        return

    def on_popup_shown(self, combo_box, params):
        if combo_box.get_property("popup-shown"):
            self.last_drop_time = datetime.now()
        else:
            elapsed = (datetime.now() - self.last_drop_time).total_seconds()
            if elapsed < 0.2:
                logging.debug(f"Dropdown closed too fast ({elapsed}s)")
                GLib.timeout_add(50, combo_box.popup)
                return

    def show_add_network(self, widget, ssid, sec_type=None):
        if self._destroyed:
            return
        if self.show_add:
            return

        for child in self.content.get_children():
            self.content.remove(child)

        if "add_network" in self.labels:
            del self.labels["add_network"]

        eap_method = Gtk.ComboBoxText(hexpand=True)
        eap_method.connect("notify::popup-shown", self.on_popup_shown)
        for method in ("peap", "ttls", "pwd", "leap", "md5"):
            eap_method.append(method, method.upper())
        self.labels["network_eap_method"] = eap_method
        eap_method.set_active(0)

        phase2 = Gtk.ComboBoxText(hexpand=True)
        phase2.connect("notify::popup-shown", self.on_popup_shown)
        for method in ("mschapv2", "gtc", "pap", "chap", "mschap", "disabled"):
            phase2.append(method, method.upper())
        self.labels["network_phase2"] = phase2
        phase2.set_active(0)

        auth_selection_box = Gtk.Box(no_show_all=True)
        auth_selection_box.add(self.labels["network_eap_method"])
        auth_selection_box.add(self.labels["network_phase2"])

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

        user_label = Gtk.Label(label=_("User"), hexpand=False, no_show_all=True)
        auth_grid = Gtk.Grid()
        auth_grid.attach(user_label, 0, 0, 1, 1)
        auth_grid.attach(self.labels["network_identity"], 1, 0, 1, 1)
        auth_grid.attach(Gtk.Label(label=_("Password"), hexpand=False), 0, 1, 1, 1)
        auth_grid.attach(self.labels["network_psk"], 1, 1, 1, 1)
        auth_grid.attach(save, 2, 0, 1, 2)

        if sec_type is not None and "802.1x" in sec_type:
            user_label.show()
            self.labels["network_eap_method"].show()
            self.labels["network_phase2"].show()
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

    def update_all_networks(self):
        if self._refreshing or self._destroyed:
            return True
        self.schedule(self._async_update_all_networks())
        return True

    async def _async_update_all_networks(self):
        if self._destroyed:
            return
        token = self._next_refresh_token()
        selected_iface = (
            self.sdbus_nm.get_selected_interface() or await self.sdbus_nm.get_primary_interface()
        )
        if self._refresh_stopped(token):
            return
        self.interface = selected_iface
        await self.update_ip_label(selected_iface)
        if self._destroyed:
            return
        nets = await self.sdbus_nm.get_networks()
        if self._refresh_stopped(token):
            return
        connected_bssid = await self.sdbus_nm.get_connected_bssid()
        if self._refresh_stopped(token):
            return

        current_bssids = {net["BSSID"] for net in nets if "BSSID" in net}
        to_remove = [bssid for bssid in self.network_rows if bssid not in current_bssids]
        for bssid in to_remove:
            await self.remove_network_from_list(bssid)

        for net in nets:
            if self._refresh_stopped(token):
                return
            bssid = net.get("BSSID")
            if not bssid:
                continue
            if bssid not in self.network_rows:
                await self._g(self.add_network, net, connected_bssid)
            else:
                await self._g(self.update_network_info, net, connected_bssid)

        for i, net in enumerate(nets):
            bssid = net.get("BSSID")
            widget = self.network_rows.get(bssid)
            if widget:
                await self._g(self.network_list.reorder_child, widget, i)
        await self._g(self.network_list.show_all)

    async def _async_update_wired(self):
        if self._destroyed:
            return
        token = self._next_refresh_token()
        await self.update_wired_network_info()
        if self._refresh_stopped(token):
            return

    def update_network_info(self, net, connected_bssid=None):
        if self._destroyed:
            return
        if net["BSSID"] not in self.network_rows.keys() or net["BSSID"] not in self.networks:
            return
        chan = _("Channel") + f" {net['channel']}"
        self.networks[net["BSSID"]]["icon"].set_from_pixbuf(
            self.get_signal_strength_icon(net["signal_level"])
        )
        self.networks[net["BSSID"]]["info"].set_markup(
            "<small>"
            f"{net['frequency']} Ghz  {chan}  {net['signal_level']} %\n"
            f"{net['security']}\n"
            f"{net['BSSID']}"
            "</small>"
        )
        ssid = net["SSID"]
        if connected_bssid is not None and net["BSSID"] == connected_bssid:
            self.networks[net["BSSID"]]["name"].set_markup(
                f"<big><b>{ssid} ({_('Connected')})</b></big>"
            )
        else:
            self.networks[net["BSSID"]]["name"].set_markup(f"<b>{ssid}</b>")

    def get_signal_strength_icon(self, signal_level):
        if signal_level > 75:
            return self.wifi_signal_icons["excellent"]
        elif signal_level > 60:
            return self.wifi_signal_icons["good"]
        elif signal_level > 30:
            return self.wifi_signal_icons["fair"]
        else:
            return self.wifi_signal_icons["weak"]

    async def update_wired_network_info(self):
        if self._destroyed:
            return
        ip = await self.sdbus_nm.get_ip_for_interface(self.interface)
        if self._destroyed:
            return
        await self._g(self._render_wired_network_info, self.interface, ip)

    def _render_wired_network_info(self, interface, ip):
        if self._destroyed:
            return
        self.labels["networkinfo"].set_markup(
            "<b>"
            + _("Interface")
            + f":</b> {interface}\n\n"
            + "<b>"
            + _("Hostname")
            + f":</b> {os.uname().nodename}\n"
            f"<b>IPv4:</b> {ip}\n"
        )
        self.labels["networkinfo"].show_all()

    def reload_networks(self, widget=None):
        self._pause_refresh()
        self._refreshing = True
        if self.sdbus_nm is None:
            self._finish_refresh()
            return
        selected_dev = next(
            (d for d in self.network_devices if d["interface"] == self.interface), None
        )
        is_wifi = selected_dev and selected_dev["type"] == enums.DeviceType.WIFI
        if is_wifi:
            if widget:
                self._gtk.Button_busy(widget, True)
            self.schedule(self._async_reload())
        else:
            self._finish_refresh()

    async def _async_rescan_and_load(self):
        if self._destroyed:
            return
        token = self._next_refresh_token()
        await self._g(self._gtk.Button_busy, self.reload_button, True)
        try:
            await self.sdbus_nm.request_rescan()
            if self._refresh_stopped(token):
                return
            await self._async_load_networks()
        finally:
            await self._g(self._gtk.Button_busy, self.reload_button, False)

    async def _async_reload(self):
        await self._async_rescan_and_load()
        self._finish_refresh()

    def deactivate(self):
        self._destroyed = True
        self._pause_refresh()
        if self.sdbus_nm is not None:
            self.sdbus_nm.set_connection_monitoring(False)
            self.sdbus_nm.destroy()
        async_utils.cancel_all_tasks()
        self._nm_tasks.clear()

    def toggle_wifi(self, switch, gparams):
        if not switch.get_sensitive():
            return
        enable = switch.get_active()
        self.schedule(self._async_toggle_wifi(enable))

    async def _async_toggle_wifi(self, enable):
        if self._destroyed:
            return
        await self.sdbus_nm.toggle_wifi(enable)
        if self._destroyed:
            return
        if enable:
            await self._g(self.reload_button.show)
            self.reload_networks()
        else:
            await self._g(self.reload_button.hide)
