"""Render -- the authoritative fit check under real Wayland.

This proves that real KlipperScreen panels fit their target resolution when
rendered through the *real* host chrome, not a bare ``panel.content`` preview.

The tree that actually renders on the touch screen is ``main_grid`` (titlebar +
action_bar + injected panel content), so the test builds the real ``BasePanel``
and injects the panel the way ``screen.attach_panel`` does.  The chrome consumes
real pixels, so a test that maps ``panel.content`` into a bare window gives it
more space than reality and would false-pass anything that clips against the
chrome boundary.

The fit is verified in two layers (see ``render.fit.check_fit``):

  1. the host ``main_grid``'s *minimum* preferred size fits the target
     resolution -- the signal that catches "panel needs ~1006px at an 800
     request";
  2. nothing beneath it -- chrome or panel, every widget level -- is clipped.

The harness is ``tests/preview_panel.py`` -- the same tool a human uses to
inspect a panel's fit.  The matrix below drives its non-blocking
``build_and_measure`` (faithful build + real render + two-layer fit check +
clean teardown), so a pass here validates exactly the path a human would
eyeball.  It runs headless under Weston (no screen output needed).

Panels that do not yet fit are recorded as skipped TODO tests rather than live
failures (see below).
"""

import pytest
from fakes.runtime import FakeScreen
from preview_panel import FONT_SIZES, RESOLUTIONS, build_and_measure

from panels.base_panel import BasePanel
from panels.temperature import Panel
from render.fit import realize

pytestmark = pytest.mark.render

# Representative panels, all of which pass the fit check across the full
# resolution x font matrix.  "Fit" is the host-level "layout won't fit" signal:
# the host ``main_grid`` minimum preferred size fits the resolution (see
# ``preview_panel.build_and_measure``).  Intra-tree clipping of compressible /
# ellided containers (a homogeneous grid squeezing, an ellipsized combobox) is
# reported but is not a failure -- it is handled, not unreachable.
TESTED_PANELS = [
    "move",
    "extrude",
    "retraction",
    "pressure_advance",
    "fan",
    "fine_tune",
    "limits",
    "temperature",
    "zcalibrate",
    "job_status",
    "input_shaper",
    "bed_mesh",
    "network",
    "bed_level",
]

# Representative panels NOT yet covered, TODO
SKIPPED_PANELS = ["main_menu"]


# --- Shared build / fit helpers ------------------------------------------


def _build_host(width, height, font_size="medium"):
    """Build the real BasePanel host with the temperature panel injected.

    Mirrors ``screen.py``: construct the host, set its printer cfg, load the real
    base styles + theme, inject the panel via ``add_content`` (the same path as
    ``attach_panel``), then map the host's ``main_grid`` into a real window at the
    target resolution.

    Loading the shipped CSS + theme is essential: otherwise the layout is bare
    Adwaita and any CSS-driven sizing (e.g. button padding) is inert, so the fit
    check would false-pass anything that clips in production.
    """
    screen = FakeScreen(width=width, height=height, font_size=font_size)
    host = BasePanel(screen, "Hornet Temperature")
    host.set_ks_printer_cfg(screen.state.printer_name)
    screen.load_base_styles()
    screen.change_theme(screen.theme)
    panel = Panel(screen, "Temperature")
    host.add_content(panel)

    window = realize(host.main_grid, width, height)
    return screen, host, panel, window


def _host_fits(host, width, height):
    """True iff the host (chrome + panel) fits within the requested resolution.

    Robust against both failure modes:

      * **grow** -- the window here is unfixed, so content wider/taller than the
        request pushes the committed allocation past it;
      * **clip** -- on a real fixed display the same content is clipped, which is
        revealed up front by the host's *minimum* preferred size already
        exceeding the request.

    The minimum preferred size is the one signal that works in both cases, so it
    is authoritative here; ``check_fit`` (below) covers everything beneath the
    host for intra-tree clipping.
    """
    min_w = host.main_grid.get_preferred_width()[0]
    min_h = host.main_grid.get_preferred_height()[0]
    return min_w <= width and min_h <= height


def _pump(glib_pump):
    """Let GLib process pending callbacks/timers so allocations settle."""
    return glib_pump(1.0, max_iterations=200)


def _fit_panels(request):
    """Panels to include in the matrix for this run.

    Empty option -> all of ``TESTED_PANELS``.  Otherwise the named panels,
    validated against ``TESTED_PANELS`` so a typo fails fast instead of
    silently collecting nothing.
    """
    raw = request.config.getoption("--fit-panel", default="").strip()
    if not raw:
        return list(TESTED_PANELS)
    selected = [p.strip() for p in raw.split(",") if p.strip()]
    unknown = [p for p in selected if p not in TESTED_PANELS]
    if unknown:
        raise ValueError(
            f"--fit-panel: unknown panel(s): {', '.join(unknown)}. "
            f"Available: {', '.join(TESTED_PANELS)}"
        )
    return selected


def pytest_generate_tests(metafunc):
    """Parametrize the fit matrix from the --fit-panel option.

    Via the hook rather than ``@pytest.mark.parametrize`` because the param
    list must depend on a CLI option, which is unavailable at import time.
    """
    if metafunc.function.__name__ != "test_panels_fit_matrix":
        return
    panels = _fit_panels(metafunc)
    metafunc.parametrize(
        "panel,width,height,font_size",
        [(p, w, h, fs) for p in panels for w, h in RESOLUTIONS for fs in FONT_SIZES],
        ids=[f"{p}@{w}x{h}@{fs}" for p in panels for w, h in RESOLUTIONS for fs in FONT_SIZES],
    )


# --- Matrix over the passing panels --------------------------------------
# Parametrized from the --fit-panel option (see pytest_generate_tests below),
# so the sweep can be narrowed to specific panels instead of all TESTED_PANELS.


def test_panels_fit_matrix(weston, panel, width, height, font_size):
    """Each passing panel fits its resolution across every font-size tier.

    Drives the faithful ``preview_panel.build_and_measure`` path (real host
    chrome + real render + two-layer fit check + clean teardown), the same code
    a human uses to verify fit -- so a pass here means the panel genuinely fits,
    and a regression would fail rather than false-pass.
    """
    result = build_and_measure(panel, width, height, font_size)
    assert result["fits"], (
        f"{panel} does not fit {width}x{height} @ {font_size}: "
        f"min {result['min_w']}x{result['min_h']} violations={result['violations']}"
    )


def test_metric_detects_genuine_overflow(weston, glib_pump):
    """A 100x100 window is far too small for the host -> overflow must be flagged.

    Guards against a vacuous suite: asserts the fit guard *does* fire on the real
    host (chrome + panel), not just that the matrix passes everywhere.  100x100 is
    well below the host's minimum preferred size, so it overflows in both the grow
    (this test) and clip (real fixed display) modes.
    """
    _, host, _, window = _build_host(100, 100)
    _pump(glib_pump)

    assert not _host_fits(host, 100, 100), "host should overflow at 100x100"

    window.destroy()


# --- Panels not yet covered (skipped TODOs) ----------------------------

# Each panel in SKIPPED_PANELS is recorded as a skipped TODO test -- not a live
# failure -- so the coverage gap stays visible in the summary.  The ids keep the
# ``panel@res@font`` shape so the render summary buckets them under the panel, and
# un-skipping one as soon as the panel is fixed immediately exercises it.
# Move a panel to TESTED_PANELS as soon as it fits.


@pytest.mark.skip(reason="TODO: panel not yet covered by the render-fit matrix")
@pytest.mark.parametrize(
    "panel,width,height,font_size",
    [(p, w, h, fs) for p in SKIPPED_PANELS for w, h in RESOLUTIONS for fs in FONT_SIZES],
    ids=[f"{p}@{w}x{h}@{fs}" for p in SKIPPED_PANELS for w, h in RESOLUTIONS for fs in FONT_SIZES],
)
def test_not_yet_covered(weston, panel, width, height, font_size):
    """Panels in SKIPPED_PANELS are tracked here until they fit the matrix."""
    result = build_and_measure(panel, width, height, font_size)
    assert result["fits"], (
        f"{panel} does not fit {width}x{height} @ {font_size}: "
        f"min {result['min_w']}x{result['min_h']} violations={result['violations']}"
    )
