"""Fidelity -- no compositor/display server.

Purpose: prove the fakes reflect reality *before* any headless run.  We
construct a real panel against the fakes and assert the resulting widget tree
matches exactly what an extruder + heater_bed + chamber printer + shipped config
would produce.  If these fail, the fakes are wrong and the whole suite is
meaningless -- so this runs first and standalone.
"""

import gi

gi.require_version("Gtk", "3.0")
import pytest
from fakes.runtime import FakeScreen
from gi.repository import Gtk

pytestmark = pytest.mark.fidelity


def _device_grid(panel):
    return panel.labels["devices"]


def test_extruder_bed_and_chamber_produce_three_device_rows():
    screen = FakeScreen(width=800, height=480)
    from panels.temperature import Panel

    panel = Panel(screen, "Temperature")

    # The printer fake declared [extruder] + [heater_bed] + [heater_generic
    # chamber].  Real Printer.reinit keys the extruder tool by its config-section
    # name ("extruder", not the websocket's "extruder0"), so the panel must build
    # exactly these three device rows.  This is the core fidelity check.
    assert set(panel.devices) == {
        "extruder",
        "heater_bed",
        "heater_generic chamber",
    }, panel.devices

    grid = _device_grid(panel)
    assert grid is not None
    # Header row (name + temp labels) + one device row per device; each device
    # row attaches a name button and a temp button -> 2 + 3*2 = 8 children.
    assert len(grid.get_children()) == 8, len(grid.get_children())

    # Each device row's name is a themed button carrying the device image name.
    # (The temp cell is also a Gtk.Button, but without an image; name buttons
    # are the ones with an image set.)
    name_buttons = [
        w for w in _walk(grid) if isinstance(w, Gtk.Button) and w.get_image() is not None
    ]
    assert len(name_buttons) == 3


def test_idle_state_enables_preheat():
    screen = FakeScreen(width=800, height=480)
    from panels.temperature import Panel

    panel = Panel(screen, "Temperature")

    # state == "idle" (not printing/paused) -> preheat grid is shown.
    assert panel.show_preheat is True
    assert len(panel.preheat_options) >= 1


def _walk(widget, depth=0):
    yield widget
    if depth < 40 and isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from _walk(child, depth + 1)
