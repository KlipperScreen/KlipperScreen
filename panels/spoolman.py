import os.path
import pathlib
import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk
from ks_includes.screen_panel import ScreenPanel
from ks_includes.KlippyRest import KlippyRest
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


def format_date(date):
    try:
        return datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=ZoneInfo('UTC'))
    except ValueError:
        try:
            return datetime.strptime(date, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=ZoneInfo('UTC'))
        except ValueError:
            return None


class SpoolmanVendor:
    id: int
    name: str
    registered: datetime = None

    def __init__(self, **entries):
        self.__dict__.update(entries)
        for date in ["registered"]:
            if date in entries:
                self.__setattr__(date, format_date(entries[date]))


class SpoolmanFilament:
    article_number: str
    color_hex: str
    comment: str
    density: float
    diameter: float
    id: int
    material: str
    name: str
    price: float
    registered: datetime = None
    settings_bed_temp: int
    settings_extruder_temp: int
    spool_weight: float
    vendor: SpoolmanVendor = None
    weight: float

    def __init__(self, **entries):
        self.__dict__.update(entries)
        if "vendor" in entries:
            self.vendor = SpoolmanVendor(**(entries["vendor"]))
        for date in ["registered"]:
            if date in entries:
                self.__setattr__(date, format_date(entries[date]))


class SpoolmanSpool(GObject.GObject):
    archived: bool
    id: int
    remaining_length: float
    remaining_weight: float
    used_length: float
    used_weight: float
    lot_nr: str
    filament: SpoolmanFilament = None
    first_used: datetime = None
    last_used: datetime = None
    registered: datetime = None
    _icon: Gtk.Image = None
    theme_path: str = None
    _spool_icon: str = None

    def __init__(self, **entries):
        GObject.GObject.__init__(self)
        self.__dict__.update(entries)
        if "filament" in entries:
            self.filament = SpoolmanFilament(**(entries["filament"]))
        for date in ["first_used", "last_used", "registered"]:
            if date in entries:
                self.__setattr__(date, format_date(entries[date]))

    @property
    def name(self):
        result = self.filament.name
        if self.filament.vendor:
            result = " ".join([self.filament.vendor.name, "-", result])
        return result

    @property
    def icon(self):
        if self._icon is None:
            if SpoolmanSpool._spool_icon is None:
                klipperscreendir = pathlib.Path(__file__).parent.resolve().parent
                _spool_icon_path = os.path.join(
                    klipperscreendir, "styles", SpoolmanSpool.theme_path, "images", "spool.svg"
                )
                if not os.path.isfile(_spool_icon_path):
                    _spool_icon_path = os.path.join(klipperscreendir, "styles", "spool.svg")
                SpoolmanSpool._spool_icon = pathlib.Path(_spool_icon_path).read_text()

            loader = GdkPixbuf.PixbufLoader()
            loader.write(
                SpoolmanSpool._spool_icon.replace('var(--filament-color)', f'#{self.filament.color_hex}').encode()
            )
            loader.close()
            self._icon = loader.get_pixbuf()
        return self._icon


class Panel(ScreenPanel):
    apiClient: KlippyRest
    _active_spool_id: int = None

    @staticmethod
    def spool_compare_id(model, row1, row2, user_data):
        spool1 = model.get_value(row1, 0)
        spool2 = model.get_value(row2, 0)
        return spool1.id - spool2.id

    @staticmethod
    def spool_compare_date(model, row1, row2, user_data):
        spool1 = model.get_value(row1, 0)
        spool2 = model.get_value(row2, 0)
        return 1 if (spool1.last_used or datetime.min).replace(tzinfo=None) > \
                    (spool2.last_used or datetime.min).replace(tzinfo=None) else -1

    def _on_material_filter_clear(self, sender, combobox):
        self._filters["material"] = None
        self._filterable.refilter()
        self._filter_expander.set_expanded(False)
        combobox.set_active_iter(self._materials.get_iter_first())

    def _on_material_filter_changed(self, sender):
        treeiter = sender.get_active_iter()
        if treeiter is not None:
            model = sender.get_model()
            self._filters["material"] = model[treeiter][0]
            self._filterable.refilter()

    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.apiClient = screen.apiclient
        if self._config.get_main_config().getboolean("24htime", True):
            self.timeFormat = '%Y-%m-%d %H:%M'
        else:
            self.timeFormat = '%Y-%m-%d %I:%M %p'

        SpoolmanSpool.theme_path = screen.theme
        GObject.type_register(SpoolmanSpool)
        self._filters = {}
        self._model = Gtk.TreeStore(SpoolmanSpool.__gtype__)
        self._materials = Gtk.ListStore(str, str)

        self._filterable = self._model.filter_new()
        self._filterable.set_visible_func(self._filter_spools)

        sortable = Gtk.TreeModelSort(self._filterable)
        sortable.set_sort_func(0, self.spool_compare_id)
        sortable.set_sort_func(1, self.spool_compare_date)

        self.scroll = self._gtk.ScrolledWindow()

        sbox = Gtk.Box(spacing=0)
        sbox.set_vexpand(False)

        clear_active_spool = self._gtk.Button("cancel", _("Clear"), "color2", self.bts, Gtk.PositionType.LEFT, 1)
        clear_active_spool.get_style_context().add_class("buttons_slim")
        clear_active_spool.connect('clicked', self.clear_active_spool)

        refresh = self._gtk.Button("refresh", style="color1", scale=.66)
        refresh.get_style_context().add_class("buttons_slim")
        refresh.connect('clicked', self.load_spools)

        sort_btn_id = self._gtk.Button(None, _("ID"), "color4", self.bts, Gtk.PositionType.RIGHT, 1)
        sort_btn_id.connect("clicked", self.change_sort, "id")
        sort_btn_id.get_style_context().add_class("buttons_slim")

        sort_btn_used = self._gtk.Button(None, _("Last Used"), "color3", self.bts, Gtk.PositionType.RIGHT, 1)
        sort_btn_used.connect("clicked", self.change_sort, "last_used")
        sort_btn_used.get_style_context().add_class("buttons_slim")

        switch = Gtk.Switch()
        switch.set_hexpand(False)
        switch.set_vexpand(False)
        switch.set_active(self._config.get_config().getboolean("spoolman", "hide_archived", fallback=True))
        switch.connect("notify::active", self.switch_config_option, "spoolman", "hide_archived", self.load_spools)

        name = Gtk.Label()
        name.set_markup(_("Archived"))
        name.set_halign(Gtk.Align.START)
        name.set_valign(Gtk.Align.CENTER)
        name.set_line_wrap(True)
        name.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        archived = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        archived.set_valign(Gtk.Align.CENTER)
        archived.add(name)
        archived.add(switch)

        sbox.pack_start(sort_btn_id, True, True, 0)
        sbox.pack_start(sort_btn_used, True, True, 0)
        sbox.pack_start(clear_active_spool, True, True, 0)
        sbox.pack_start(refresh, True, True, 0)
        sbox.pack_start(archived, False, False, 5)
        sbox.set_hexpand(True)
        sbox.set_vexpand(False)

        filter_box = Gtk.ListBox()
        filter_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._filter_expander = Gtk.Expander(label=_("Filter"))
        self._filter_expander.add(filter_box)

        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        row.add(hbox)

        label = Gtk.Label(_("Material"))
        _material_filter = Gtk.ComboBox.new_with_model(self._materials)
        _material_filter.connect("changed", self._on_material_filter_changed)
        cellrenderertext = Gtk.CellRendererText()
        _material_filter.pack_start(cellrenderertext, True)
        _material_filter.add_attribute(cellrenderertext, "text", 1)
        _material_filter.set_hexpand(True)

        _material_reset_filter = self._gtk.Button("cancel", _("Clear"), "color2", self.bts, Gtk.PositionType.LEFT, 1)
        _material_reset_filter.get_style_context().add_class("buttons_slim")
        _material_reset_filter.connect('clicked', self._on_material_filter_clear, _material_filter)

        hbox.pack_start(label, False, True, 0)
        hbox.pack_start(_material_filter, True, True, 0)
        hbox.pack_end(_material_reset_filter, False, True, 0)

        filter_box.add(row)

        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main.set_vexpand(True)
        self.main.pack_start(sbox, False, False, 0)
        self.main.pack_start(self._filter_expander, False, True, 0)
        self.main.pack_start(self.scroll, True, True, 0)

        self.load_spools()
        self.get_active_spool()
        self._treeview = Gtk.TreeView(model=sortable)
        self._treeview.set_headers_visible(False)
        self._treeview.set_show_expanders(False)

        text_renderer = Gtk.CellRendererText()
        pixbuf_renderer = Gtk.CellRendererPixbuf()
        pixbuf_renderer.set_padding(5, 5)
        checkbox_renderer = Gtk.CellRendererToggle()
        column_id = Gtk.TreeViewColumn(cell_renderer=text_renderer)
        column_id.set_cell_data_func(
            text_renderer,
            lambda column, cell, model, it, data:
            self._set_cell_background(cell, model.get_value(it, 0)) and
            cell.set_property('text', f'{model.get_value(it, 0).id}')
        )
        column_id.set_sort_column_id(0)

        column_icon = Gtk.TreeViewColumn(cell_renderer=pixbuf_renderer)
        column_icon.set_cell_data_func(
            pixbuf_renderer,
            lambda column, cell, model, it, data:
            self._set_cell_background(cell, model.get_value(it, 0)) and
            cell.set_property('pixbuf', model.get_value(it, 0).icon)
        )

        column_spool = Gtk.TreeViewColumn(cell_renderer=text_renderer)
        column_spool.set_expand(True)
        column_spool.set_cell_data_func(
            text_renderer,
            lambda column, cell, model, it, data:
            self._set_cell_background(cell, model.get_value(it, 0)) and
            cell.set_property('markup', self._get_filament_formated(model.get_value(it, 0)))
        )

        column_last_used = Gtk.TreeViewColumn(cell_renderer=text_renderer)
        column_last_used.set_visible(False)
        column_last_used.set_sort_column_id(1)

        column_material = Gtk.TreeViewColumn(cell_renderer=text_renderer)
        column_material.set_cell_data_func(
            text_renderer,
            lambda column, cell, model, it, data:
            self._set_cell_background(cell, model.get_value(it, 0)) and
            cell.set_property('text', model.get_value(it, 0).filament.material)
        )

        checkbox_renderer.connect("toggled", self._set_active_spool)
        column_toggle_active_spool = Gtk.TreeViewColumn(cell_renderer=checkbox_renderer)
        column_toggle_active_spool.set_cell_data_func(
            checkbox_renderer,
            lambda column, cell, model, it, data:
            self._set_cell_background(cell, model.get_value(it, 0)) and
            cell.set_property('active', model.get_value(it, 0).id == self._active_spool_id)
        )

        self._treeview.append_column(column_id)
        self._treeview.append_column(column_icon)
        self._treeview.append_column(column_spool)
        self._treeview.append_column(column_last_used)
        self._treeview.append_column(column_material)
        self._treeview.append_column(column_toggle_active_spool)

        self.current_sort_widget = sort_btn_id
        sort_btn_used.clicked()

        self.scroll.add(self._treeview)
        self.content.add(self.main)

    def _filter_spools(self, model, i, data):
        spool: SpoolmanSpool = model[i][0]
        matches = True
        if ("material" in self._filters) and (self._filters["material"] is not None):
            matches &= spool.filament.material == self._filters["material"]
        return matches

    def _set_cell_background(self, cell, spool: SpoolmanSpool):
        cell.set_property('cell-background-rgba', Gdk.RGBA(1, 1, 1, .1) if spool.id == self._active_spool_id else None)
        return True

    def _get_filament_formated(self, spool: SpoolmanSpool):
        if spool.id == self._active_spool_id:
            result = f'<big><b>{spool.name}</b></big>\n'
        else:
            result = f'<big>{spool.name}</big>\n'
        if spool.last_used:
            result += f'{_("Last used")}:<b> {spool.last_used.astimezone():{self.timeFormat}}</b>\n'
        if hasattr(spool, "remaining_weight"):
            result += f'{_("Remaining weight")}: <b>{round(spool.remaining_weight, 2)} g</b>\n'
        if hasattr(spool, "remaining_length"):
            result += f'{_("Remaining length")}: <b>{round(spool.remaining_length / 1000, 2)} m</b>\n'

        return result.strip()

    def _set_active_spool(self, sender, path):
        model = self._treeview.get_model()
        it = model.get_iter(path)
        spool = model.get_value(it, 0)
        if spool.id == self._active_spool_id:
            self.clear_active_spool()
        else:
            self.set_active_spool(spool)

    def change_sort(self, widget, sort_type):
        self.current_sort_widget.set_image(None)
        self.current_sort_widget = widget
        if sort_type == "id":
            logging.info("Sorting by ID")
            column = 0
        elif sort_type == "last_used":
            logging.info("Sorting by Last Used")
            column = 1
        else:
            logging.error("Unknown sort type")
            return
        if self._treeview.get_column(column).get_sort_order() == Gtk.SortType.DESCENDING:
            new_sort_order = Gtk.SortType.ASCENDING
        else:
            new_sort_order = Gtk.SortType.DESCENDING
        self._treeview.get_column(column).set_sort_order(new_sort_order)
        self._treeview.get_model().set_sort_column_id(column, new_sort_order)
        icon = "arrow-down" if new_sort_order == Gtk.SortType.DESCENDING else "arrow-up"
        widget.set_image(self._gtk.Image(icon, self._gtk.img_scale * self.bts))

    def process_update(self, action, data):
        if action == "notify_active_spool_set":
            self._active_spool_id = data['spool_id']
            self._treeview.get_model().foreach(lambda store, treepath, treeiter:
                                               store.row_changed(treepath, treeiter)
                                               )
            self._treeview.queue_draw()

    def load_spools(self, data=None):
        hide_archived = self._config.get_config().getboolean("spoolman", "hide_archived", fallback=True)
        self._model.clear()
        self._materials.clear()
        spools = self.apiClient.post_request("server/spoolman/proxy", json={
            "request_method": "GET",
            "path": f"/v1/spool?allow_archived={not hide_archived}",
        })
        if not spools or "result" not in spools:
            self._screen.show_error_modal("Exception when trying to fetch spools")
            return

        materials = []
        for spool in spools["result"]:
            spoolObject = SpoolmanSpool(**spool)
            self._model.append(None, [spoolObject])
            if spoolObject.filament.material not in materials:
                materials.append(spoolObject.filament.material)

        materials.sort()
        self._materials.append([None, _("All")])
        for material in materials:
            self._materials.append([material, material])

    def clear_active_spool(self, sender: Gtk.Button = None):
        result = self.apiClient.post_request("server/spoolman/spool_id", json={})
        if not result:
            self._screen.show_error_modal("Exception when setting active spool")
            return

    def set_active_spool(self, spool: SpoolmanSpool):
        result = self.apiClient.post_request("server/spoolman/spool_id", json={
            "spool_id": spool.id
        })
        if not result:
            self._screen.show_error_modal("Exception when setting active spool")
            return

    def get_active_spool(self) -> SpoolmanSpool:
        result = self.apiClient.send_request("server/spoolman/spool_id")
        if not result:
            self._screen.show_error_modal("Exception when getting active spool")
            return
        self._active_spool_id = result["result"]["spool_id"]
        return self._active_spool_id
