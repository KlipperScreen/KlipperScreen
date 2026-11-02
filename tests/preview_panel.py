"""Open or sweep a real KlipperScreen panel, fully rendered, to verify fit.

Two modes share ONE faithful build path (``_build``), which mirrors
``screen.attach_panel`` exactly -- the same tree that renders on the touch
screen:

    host = BasePanel(screen, title); host.set_ks_printer_cfg(...)
    host.add_content(panel)                     # base_panel.add_content(panel)
    panel.process_update("notify_status_update", printer.data)   # labels filled
    panel.activate()                            # e.g. job_status attaches buttons

...then maps the whole tree (titlebar + action bar + panel content) into a real
window on the current Wayland session and measures the two-layer fit
(minimum preferred size vs. resolution + nothing beneath it clips; see
``render.fit``).  Loading the shipped CSS + theme is part of the build, so
CSS-driven sizing (button padding, keypad, title bar) is exercised for real.

Interactive (default): renders the actual window and waits for you to close it
(or Ctrl-C), logging ``[SIZE]`` / ``[WARN]`` as you resize -- the "does this look
right?" path.

--random: animate the live feed, sweeping each field between 0 and
its nominal value in ``tests/assets/mock_printer_state.json``.

--extruders N: preview only, build the printer with N extruders
(extruder, extruder1, ...) instead of one -- the rest of the suite stays
single-extruder.

--sweep: renders every panel across the resolution x font matrix, auto-closing
after each measurement (no human needed), prints a table, and exits non-zero if
any panel won't fit -- the "is the fit test faithful?" path.  This is the code
path the render-fit test suite drives (see ``build_and_measure``).

No X11: GDK_BACKEND=wayland, current WAYLAND_DISPLAY / XDG_RUNTIME_DIR used as-is.
Run under a headless Weston for CI (``weston --backend=headless``): the window is
created and laid out for real, there is simply nothing to display it.
"""

import json
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO, os.path.join(REPO, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

THUMBNAILS = os.path.join(REPO, "tests", "assets", "thumbnails")
THUMBNAIL = os.path.join(THUMBNAILS, "voron_foot_0.2_FLEX-300x300.png")

# Single source of truth for the preview tool's mock printer state: the
# deterministic active-print data and the temp-graph time-store parameters.
# Edit mock_printer_state.json to change what panels render -- no code needed.
MOCK_STATE_PATH = os.path.join(REPO, "tests", "assets", "mock_printer_state.json")
with open(MOCK_STATE_PATH) as _mf:
    MOCK_STATE = json.load(_mf)

import gettext

gettext.translation(
    "KlipperScreen",
    localedir=os.path.join(REPO, "ks_includes/locales"),
    languages=["en"],
    fallback=True,
).install(names=["gettext", "ngettext"])

import argparse

import gi

gi.require_version("Gtk", "3.0")
from fakes.runtime import FakePrinter, FakeScreen, build_printer
from gi.repository import GLib

# Canonical on-screen resolutions for the fit matrix.
RESOLUTIONS = [
    (480, 320),
    (800, 480),
    (1024, 600),
    (320, 480),
    (480, 800),
    (600, 1024),
]

# Every selectable font-size tier in the shipped config.
FONT_SIZES = ["small", "medium", "large", "extralarge", "max"]

# Representative panels the sweep covers by default.  ``--sweep all`` scans
# panels/ for anything defining ``class Panel`` instead.
PANELS = [
    "job_status",
    "move",
    "extrude",
    "retraction",
    "pressure_advance",
    "fan",
    "fine_tune",
    "limits",
    "temperature",
    "zcalibrate",
]

_SKIP_PANELS = {"base_panel", "example"}


def seed_tempstore(printer, ambient=None):
    """Populate the graph time-store with a heating ramp so the chart is real.

    Each device gets ``tempstore_size`` points: ambient for most of the history,
    then a ramp up toward a target over the last ``ramp`` points (what the graph
    shows at the right edge / "now").  ``size``, ``ramp``, ``ambient`` and the
    per-device ``targets`` all come from ``MOCK_STATE`` -- edit
    ``mock_printer_state.json`` to change the graph.
    """
    cfg = MOCK_STATE["tempstore"]
    size = cfg["size"]
    ramp = cfg["ramp"]
    if ambient is None:
        ambient = cfg["ambient"]
    targets = cfg["targets"]
    for device in printer.get_temp_devices():
        is_bed = device == "heater_bed"
        target = targets.get(device, 60.0 if is_bed else 200.0)
        vals = []
        for i in range(size):
            if i < size - ramp:
                v = ambient
            else:
                t = (i - (size - ramp)) / ramp
                v = ambient + (target - ambient) * min(1.0, t)
            vals.append(round(v, 1))
        printer.tempstore[device] = {
            "temperatures": vals,
            "targets": [target] * size,
        }
    printer.tempstore_size = size


def random_print_data(printer):
    """Random active-print data for the human interactive feed, so the animation
    has variety to eyeball.  Deterministic data (see :func:`seed_live_data`) is
    used for the fit sweep.

    Every field is randomized between ``0`` and its nominal value in
    ``mock_printer_state.json`` (the ``live`` section, or the temp ``targets``),
    so the sweep stays within realistic ranges instead of exploding.
    """
    live = MOCK_STATE["live"]
    targets = MOCK_STATE["tempstore"]["targets"]
    data = {
        "display_status": {"state": "printing", "message": "Printing..."},
        "toolhead": {
            "extruder": "extruder",
            "max_accel": int(random.uniform(0, live["toolhead"]["max_accel"])),
        },
        "extruder": {
            "pressure_advance": round(random.uniform(0, live["extruder"]["pressure_advance"]), 3)
        },
        "fan": {"speed": round(random.uniform(0, live["fan"]["speed"]), 3)},
    }
    for dev in printer.get_temp_devices():
        is_bed = dev == "heater_bed"
        nominal = live.get(dev, {})
        target = nominal.get("target", targets.get(dev, 60.0 if is_bed else 205.0))
        data[dev] = {
            "temperature": round(random.uniform(0, target), 1),
            "target": target,
            "power": round(random.uniform(0, nominal.get("power", 0.6)), 3),
        }
    nominal_pos = live["gcode_move"]["gcode_position"]
    pos = [random.uniform(0, nominal_pos[i]) for i in range(len(nominal_pos))]
    gcode = live["gcode_move"]
    data["gcode_move"] = {
        "gcode_position": pos,
        "live_position": pos,
        "extrude_factor": round(random.uniform(0.9, 1.1), 3),
        "speed_factor": round(random.uniform(0.9, 1.1), 3),
        "speed": round(random.uniform(0, gcode["speed"]), 2),
        "homing_origin": [0.0, 0.0, round(random.uniform(-0.5, 0.5), 3)],
    }
    motion = live["motion_report"]
    data["motion_report"] = {
        "live_position": pos,
        "live_velocity": round(random.uniform(0, motion["live_velocity"]), 2),
        "live_extruder_velocity": round(random.uniform(0, motion["live_extruder_velocity"]), 2),
    }
    stats = live["print_stats"]
    info = stats["info"]
    data["print_stats"] = {
        "state": "printing",
        "filename": stats["filename"],
        "filament_used": int(random.uniform(0, stats["filament_used"])),
        "info": {
            "current_layer": random.randint(1, info["total_layer"]),
            "total_layer": info["total_layer"],
        },
        "total_duration": round(random.uniform(0, stats["total_duration"]), 1),
        "print_duration": round(random.uniform(0, stats["print_duration"]), 1),
    }
    card = live["virtual_sdcard"]
    data["virtual_sdcard"] = {
        "progress": round(random.uniform(0, card["progress"]), 3),
        "file_position": round(random.uniform(0, card["file_position"]), 1),
    }
    return data


def seed_live_data(printer):
    """Seed deterministic, realistic *active-print* state so panels render the
    way they do on device (long filename, progress, live temps, gcode move).

    Deterministic on purpose: the fit check must be reproducible.  This is the
    data ``process_update("notify_status_update", ...)`` carries in production.
    All values come from ``mock_printer_state.json`` -- edit that file to change
    what renders.
    """
    live = MOCK_STATE["live"]
    targets = MOCK_STATE["tempstore"]["targets"]
    for stat, sub in live.items():
        printer.set_stat(stat, dict(sub))
    # Seed every temp device, not just the ones hand-listed in the JSON, so extra
    # extruders render heated instead of at target 0.  Fall back to the tempstore
    # target, then a sensible per-kind default.
    for dev in printer.get_temp_devices():
        if dev in MOCK_STATE["live"]:
            continue
        is_bed = dev == "heater_bed"
        target = targets.get(dev, 60.0 if is_bed else 205.0)
        printer.set_stat(dev, {"temperature": target, "target": target, "power": 0.6})
    seed_tempstore(printer)


def discover_panels():
    """Panel names (module short name) defined in panels/, minus stand-ins."""
    panels_dir = os.path.join(REPO, "panels")
    names = []
    for fname in os.listdir(panels_dir):
        if not fname.endswith(".py") or fname.startswith("__"):
            continue
        name = fname[:-3]
        if name in _SKIP_PANELS:
            continue
        names.append(name)
    return sorted(names)


def _build_printer(extruders=1):
    """A FakePrinter with ``extruders`` extruders (extruder, extruder1, ...).

    Derived from the shared ``build_printer`` config so the rest of the test
    suite stays single-extruder; only the preview opts in via ``--extruders``.
    """
    config, data = build_printer()
    for i in range(1, extruders):
        config[f"extruder{i}"] = dict(config["extruder"])
        data[f"extruder{i}"] = {"temperature": 23.5, "target": 0}
    return FakePrinter(config=config, data=data)


def _build(
    panel_name, width=800, height=480, font_size="medium", theme="material-dark", extruders=1
):
    """Faithfully build the real host+panel tree the way ``screen.attach_panel``
    does, map ``main_grid`` into a real window at the target resolution, and let
    the layout settle.  Returns ``(screen, host, panel, window)``.

    Does NOT block and does NOT tear down -- callers pump/measure/destroy.
    """
    from importlib import import_module

    from render.fit import realize

    from panels.base_panel import BasePanel

    screen = FakeScreen(
        width=width,
        height=height,
        font_size=font_size,
        theme=theme,
        printer=_build_printer(extruders),
    )
    screen._config.set("main", "show_heater_power", "True")
    screen.files.has_thumbnail = lambda filename: os.path.exists(THUMBNAIL)
    screen.files.get_thumbnail_location = lambda filename, small=False: ("file", THUMBNAIL)

    panel_mod = import_module(f"panels.{panel_name}")
    Panel = panel_mod.Panel

    host = BasePanel(screen, panel_name.title())
    host.set_ks_printer_cfg(screen.state.printer_name)
    screen.base_panel = host

    screen.load_base_styles()
    screen.change_theme(theme)

    panel = Panel(screen, panel_name.title())
    host.add_content(panel)

    printer = screen.printer
    seed_live_data(printer)

    # Faithful production path (screen.attach_panel 450-463): populate the
    # panel's labels from live data, then activate() (e.g. job_status attaches
    # its action-button row).  Neither is skipped.
    if hasattr(panel, "process_update"):
        panel.process_update("notify_status_update", printer.data)
    if hasattr(panel, "activate"):
        panel.activate()

    window = realize(host.main_grid, width, height)

    # Let recurring timers settle so preferred sizes / allocations are final.
    ctx = GLib.MainContext.default()
    for _ in range(20):
        while ctx.pending():
            ctx.iteration(False)

    return screen, host, panel, window


def build_and_measure(panel_name, width=800, height=480, font_size="medium", theme="material-dark"):
    """Faithfully build + measure one (panel, resolution, font) and tear down
    cleanly.  Returns a fit dict:

        {panel, width, height, font_size,
         min_w, min_h, fits, violations, error}

    ``fits`` is the "layout won't fit" signal: the host's minimum preferred size
    fits the resolution (see the note below).  Never blocks; always leaves the
    shared GLib context quiet.

    Teardown removes recurring timers (``panel.deactivate()`` where present)
    *before* ``window.destroy()``.  ``activate()`` registers GLib timeouts that
    otherwise outlive the window and fire a freed-widget callback on the next
    pump -- the segfault a naive in-process sweep hit.
    """
    from render.fit import check_fit

    screen, host, panel, window = _build(panel_name, width, height, font_size, theme)
    result = {
        "panel": panel_name,
        "width": width,
        "height": height,
        "font_size": font_size,
        "min_w": host.main_grid.get_preferred_width()[0],
        "min_h": host.main_grid.get_preferred_height()[0],
        "violations": [],
        "error": None,
    }
    try:
        # "Layout won't fit" signal: the host's minimum preferred size must fit
        # the resolution.  If the host's own minimum exceeds the request, the
        # panel cannot fit a fixed display (it clips here) -- this is exactly the
        # signal the interactive [WARN] reports.  Two things are deliberately NOT
        # the gate:
        #   * the committed window "grow" signal -- under headless Weston the
        #     window gains a constant ~frame, so committed exceeds the request for
        #     *every* panel regardless of content; it cannot distinguish fit from
        #     overflow.
        #   * intra-tree clipping (``check_fit``) -- reported in ``violations`` for
        #     manual inspection, but not a pass/fail signal, because compressible
        #     / ellided containers (a homogeneous grid squeezing, an ellipsized
        #     combobox) are handled, not unreachable.
        result["fits"] = result["min_w"] <= width and result["min_h"] <= height
        _, result["violations"] = check_fit(host.main_grid)
    except Exception as exc:  # pragma: no cover - defensive
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["fits"] = False
    finally:
        if hasattr(panel, "deactivate"):
            try:
                panel.deactivate()
            except Exception:
                pass
        window.destroy()
    return result


def open_panel(
    panel_name,
    width=800,
    height=480,
    font_size="medium",
    theme="material-dark",
    random=False,
    extruders=1,
):
    """Interactive: build, render the actual window, and wait for close.

    The human-facing "does this look right?" path -- real render, live
    job-status animation, [SIZE]/[WARN] logging while resizing.  ``random``
    animates the job_status feed with each field swept 0..nominal.
    """
    screen, host, panel, window = _build(
        panel_name, width, height, font_size, theme, extruders=extruders
    )
    window.set_title(f"KlipperScreen - {panel_name}")
    print(
        f"FONT '{font_size}' -> {screen.gtk.font_size:.1f}px "
        f"(ratio {screen.gtk.font_ratio}, vertical={screen.vertical_mode})",
        flush=True,
    )

    feed_timer = None
    if random:

        def _feed():
            data = random_print_data(screen.printer)
            for stat, sub in data.items():
                screen.printer.set_stat(stat, sub)
            panel.process_update("notify_status_update", screen.printer.data)
            host.main_grid.queue_draw()
            return True

        _feed()
        feed_timer = GLib.timeout_add(500, _feed)

    closed = {"flag": False}

    def _on_delete(_window, _event):
        closed["flag"] = True
        return True

    window.connect("delete_event", _on_delete)

    # Best-effort pointer-drag tracking so a size change can be tagged as
    # coming from the user dragging the window vs the panel/auto.  On Wayland
    # configure/size-allocate signals don't fire reliably, so this is only a
    # soft hint: the "won't fit" decision below does not depend on it.
    dragging = {"flag": False}

    def _on_press(_w, _e):
        dragging["flag"] = True
        return False

    def _on_release(_w, _e):
        dragging["flag"] = False
        return False

    window.connect("button-press-event", _on_press)
    window.connect("button-release-event", _on_release)

    window.show_all()
    host.main_grid.queue_draw()

    ctx = GLib.MainContext.default()
    for _ in range(20):
        while ctx.pending():
            ctx.iteration(False)

    def committed_size():
        w = window.get_allocated_width()
        h = window.get_allocated_height()
        if w and h:
            return w, h
        return host.main_grid.get_allocated_width(), host.main_grid.get_allocated_height()

    cw, ch = committed_size()
    print(
        f"OPENED '{panel_name}' on {os.environ.get('WAYLAND_DISPLAY')} "
        f"(GDK_BACKEND={os.environ.get('GDK_BACKEND', '(unset)')}) "
        f"requested {width}x{height}, committed {cw}x{ch} "
        f"(close the window or Ctrl-C to quit)",
        flush=True,
    )

    # "Layout won't fit" signal: the panel's own minimum size request already
    # exceeds the request -> on a fixed display the content is clipped at the
    # requested resolution.  This is the reliable host-level signal.  The
    # committed-window "grow" signal is NOT used here: under headless Weston the
    # window gains a constant ~frame, so committed exceeds the request for every
    # panel regardless of content (visible in the OPENED line above) and cannot
    # distinguish fit from overflow.  Use ``build_and_measure`` / the test matrix
    # for the programmatic check; the [WARN] here is for a quick eyeball.
    mw = host.main_grid.get_preferred_width()[0]
    mh = host.main_grid.get_preferred_height()[0]
    if mw > width:
        print(
            f"[WARN] '{panel_name}' content minimum width {mw} > requested {width}: "
            f"layout won't fit horizontally",
            flush=True,
        )
    if mh > height:
        print(
            f"[WARN] '{panel_name}' content minimum height {mh} > requested {height}: "
            f"layout won't fit vertically",
            flush=True,
        )

    prev = (cw, ch)
    try:
        while not closed["flag"]:
            while ctx.pending():
                ctx.iteration(False)
            cw, ch = committed_size()
            if (cw, ch) != prev:
                tag = "[user]" if dragging["flag"] else "[auto]"
                print(
                    f"[SIZE] {tag} '{panel_name}' size changed {prev[0]}x{prev[1]} -> {cw}x{ch}",
                    flush=True,
                )
                prev = (cw, ch)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print(f"CLOSED '{panel_name}' by Ctrl-C", flush=True)

    print(f"CLOSED '{panel_name}' by user", flush=True)

    if feed_timer is not None:
        GLib.source_remove(feed_timer)
    # Faithful teardown: remove recurring timers before destroying.
    if hasattr(panel, "deactivate"):
        try:
            panel.deactivate()
        except Exception:
            pass
    window.destroy()


def run_sweep(pnames, resolutions, fonts, theme="material-dark"):
    """Auto-close sweep: build+measure every (panel, res, font), print a table,
    and return 0 if all fit, 1 if any won't fit (so it can gate a test)."""
    any_failed = False
    print(
        f"\n=== sweep: {len(pnames)} panels x {len(resolutions)} res x {len(fonts)} font ===",
        flush=True,
    )
    for name in pnames:
        print(f"[{name}]", flush=True)
        for fs in fonts:
            row = []
            fails = []
            for w, h in resolutions:
                r = build_and_measure(name, w, h, fs, theme)
                if r["fits"]:
                    row.append("ok")
                else:
                    any_failed = True
                    row.append("FAIL")
                    fails.append((w, h, r))
            print(f"    {fs:11s} " + "  ".join(row), flush=True)
            for w, h, r in fails:
                detail = f"min {r['min_w']}x{r['min_h']}"
                if r["violations"]:
                    detail += f" clip {r['violations'][:2]}"
                if r["error"]:
                    detail += f" ERROR {r['error']}"
                print(f"        {w}x{h}: {detail}", flush=True)
    print(f"\n{'ALL FIT' if not any_failed else 'OVERFLOW DETECTED'}", flush=True)
    return 1 if any_failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Open or sweep a real KlipperScreen panel to verify fit.",
        add_help=False,
    )
    parser.add_argument(
        "panel",
        nargs="*",
        default=None,
        help="panel name(s); interactive default: temperature; for --sweep, "
        "the panels to sweep (default: all discovered)",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="sweep the panels across the resolution x font matrix (auto-close)",
    )
    parser.add_argument("-w", "--width", type=int, default=800)
    parser.add_argument("-h", "--height", type=int, default=480)
    parser.add_argument(
        "-f",
        "--font-size",
        default="medium",
        choices=["small", "medium", "large", "extralarge", "max"],
        help="font-size tier (interactive mode; default: medium)",
    )
    parser.add_argument(
        "-t",
        "--theme",
        default="material-dark",
        help="theme name under styles/ (default: material-dark)",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="animate job_status, sweeping each field 0..nominal "
        "(nominal values from mock_printer_state.json)",
    )
    parser.add_argument(
        "--extruders",
        type=int,
        default=1,
        help="preview only: build the printer with this many extruders (default 1)",
    )
    parser.add_argument(
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="show this help message and exit",
    )
    args = parser.parse_args()
    try:
        if args.sweep:
            pnames = args.panel if args.panel else discover_panels()
            sys.exit(run_sweep(pnames, RESOLUTIONS, FONT_SIZES))
        open_panel(
            args.panel[0] if args.panel else "temperature",
            args.width,
            args.height,
            args.font_size,
            args.theme,
            random=args.random,
            extruders=args.extruders,
        )
    except Exception:  # noqa: BLE001 - surface any panel failure to the user
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
