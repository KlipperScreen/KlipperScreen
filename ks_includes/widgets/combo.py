import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


class ComboBoxPlus(Gtk.ComboBox):
    """
    A special ComboBox that checks if the dropdown was closed too fast and re-opens it.

    Supports both the model-based Gtk.ComboBox API (passing `model=` zcalibrate)
    and a simple append() text API like Gtk.ComboBoxText
    """

    def __init__(self, *args, **kwargs):
        self._store = None
        super().__init__(*args, **kwargs)
        self._last_open_time = 0
        self.set_property("focus-on-click", False)
        self.connect("notify::popup-shown", self._on_popup_shown)

    def append(self, value, text):
        """Append an option, building a text store on first use."""
        if self._store is None:
            self._store = Gtk.ListStore(str, str)
            renderer = Gtk.CellRendererText()
            self.pack_start(renderer, True)
            self.add_attribute(renderer, "text", 1)
            self.set_model(self._store)
        self._store.append([value, text])

    def _on_popup_shown(self, combo, pspec):
        if self.get_property("popup-shown"):
            self._last_open_time = GLib.get_monotonic_time()
            return

        # Microseconds to seconds
        duration = (GLib.get_monotonic_time() - self._last_open_time) / 1000000.0

        if duration < 0.2:
            GLib.idle_add(self._reopen_now, priority=GLib.PRIORITY_HIGH_IDLE)

    def _reopen_now(self):
        self.popup()
        return False
