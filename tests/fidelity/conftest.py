"""Fidelity tier -- skips when no display is available.

Fidelity builds a *real* panel against the fakes, so it needs a Gdk display;
without one it segfaults during widget construction.
"""

import os

import pytest


def _display_available():
    """True if a Wayland socket or an X display is reachable."""
    wayland = os.environ.get("WAYLAND_DISPLAY")
    if wayland and os.path.exists(f"/run/user/{os.getuid()}/{wayland}"):
        return True
    return bool(os.environ.get("DISPLAY"))


@pytest.fixture(scope="session", autouse=True)
def _fidelity_display():
    if not _display_available():
        pytest.skip("no display available; fidelity builds real GTK widgets")
    yield
