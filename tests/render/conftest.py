"""Render fixtures -- real GTK under a headless Weston compositor.

Weston is the ONLY compositor we use, and it is Wayland-only.  We force
``GDK_BACKEND=wayland`` so GTK never falls back to X11 (which is being
deprecated on target distros).  There is deliberately no X11 anywhere: no
Xvfb, no XWayland, no X-linked fallback.
"""

import os
import shutil
import subprocess
import tempfile
import time

import pytest


def _weston_available():
    return shutil.which("weston") is not None


@pytest.fixture(scope="session", autouse=True)
def weston():
    """Start a headless Weston, point GTK at it, and tear it down cleanly.

    Runs once per session.  Repeated runs are safe: a fresh runtime dir and
    socket name are used each time.
    """
    if not _weston_available():
        pytest.skip("weston not installed (Wayland compositor required for render)")

    runtime = tempfile.mkdtemp(prefix="ks-weston-")
    os.chmod(runtime, 0o700)
    socket_name = "wayland-test"
    log_path = os.path.join(runtime, "weston.log")

    proc = subprocess.Popen(
        [
            "weston",
            "--backend=headless",
            f"--socket={os.path.join(runtime, socket_name)}",
            "--idle-time=0",
            f"--log={log_path}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for the socket to appear (bounded, so a broken start fails fast).
    socket_path = os.path.join(runtime, socket_name)
    for _ in range(50):  # up to ~5s
        if os.path.exists(socket_path):
            break
        if proc.poll() is not None:
            pytest.skip(f"weston exited early (see {log_path})")
        time.sleep(0.1)
    else:
        proc.terminate()
        pytest.skip(f"weston socket did not appear (see {log_path})")

    # Point the current process at this compositor.  GTK selects its backend
    # when the first display is opened, which happens lazily on first window
    # realization -- well after this fixture has set the environment.
    os.environ["WAYLAND_DISPLAY"] = socket_name
    os.environ["XDG_RUNTIME_DIR"] = runtime
    os.environ["GDK_BACKEND"] = "wayland"

    yield

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    shutil.rmtree(runtime, ignore_errors=True)
    for key in ("WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "GDK_BACKEND"):
        os.environ.pop(key, None)


@pytest.fixture
def glib_pump():
    """Run the default GLib main context for a bounded amount of time.

    Bounded by wall-clock *and* iteration count -- never "wait for idle",
    because panels have recurring timers / async work that make true
    idleness unreachable.  Returns the number of iterations processed.
    """
    from gi.repository import GLib

    def pump(seconds=1.0, max_iterations=200):
        ctx = GLib.MainContext.default()
        deadline = time.monotonic() + seconds
        iterations = 0
        while ctx.pending():
            ctx.iteration(False)
            iterations += 1
            if iterations >= max_iterations or time.monotonic() > deadline:
                break
        return iterations

    return pump


# --- Render-fit result summary -------------------------------------------
#
# pytest's default render output is a run of dots, which hides which panel /
# resolution / font is being validated and which one fails.  These hooks print
# a readable per-panel summary at the end of the session.

_RENDER_RESULTS = {}  # nodeid -> (outcome, reason)
_OUTCOME_RANK = {"passed": 0, "skipped": 1, "error": 2, "failed": 3}
_RESOLUTION_ORDER = [(480, 320), (800, 480), (1024, 600), (320, 480), (480, 800), (600, 1024)]


def pytest_runtest_logreport(report):
    """Record each render test's outcome for the end-of-session summary."""
    if "render" not in report.nodeid:
        return
    current = _RENDER_RESULTS.get(report.nodeid)
    if current is None or _OUTCOME_RANK.get(report.outcome, 0) > _OUTCOME_RANK.get(current[0], 0):
        _RENDER_RESULTS[report.nodeid] = (report.outcome, _failure_reason(report))


def pytest_sessionfinish(session, exitstatus):
    """Print a readable per-panel fit summary."""
    if not _RENDER_RESULTS:
        return
    term = session.config.pluginmanager.get_plugin("terminalreporter")
    write = term.line if term else print
    write("")
    for line in _render_summary_lines():
        write(line)


def _failure_reason(report):
    """Pull the assertion message out of a pytest traceback."""
    text = getattr(report, "longreprtext", "") or ""
    if not text:
        longrepr = getattr(report, "longrepr", None)
        text = getattr(longrepr, "text", "") if longrepr else ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("AssertionError:"):
            return stripped.split(":", 1)[1].strip()
    for line in text.splitlines():
        if line.startswith("E") and line[1:].strip():
            return line[1:].strip()
    return ""


def _render_summary_lines():
    """One block per panel: a tally, coverage, and any failures.

    Structured ids (``panel@res@font``) populate a matrix of ``(resolution,
    font)`` cells.  Any other render test -- the temperature regression, the
    overflow guard, a bare unparametrized test -- is a single non-matrix result
    kept in a ``plain`` list rather than keyed by ``None``.  Keying by ``None``
    both collided with the matrix and crashed the failures unpacking below
    (``for (r, f), ... in cells.items()`` cannot unpack a ``None`` key), so only
    the structured ``cells`` are iterated there.
    """
    buckets = []  # list of [name, {(res, font): (outcome, reason)}, [(outcome, reason)]]

    def _bucket(name):
        for b in buckets:
            if b[0] == name:
                return b
        b = [name, {}, []]
        buckets.append(b)
        return b

    for nodeid, (outcome, reason) in _RENDER_RESULTS.items():
        if "genuine_overflow" in nodeid:
            _bucket("overflow guard")[2].append((outcome, reason))
            continue
        if "[" in nodeid:
            parts = nodeid.split("[", 1)[1].rstrip("]").split("@")
            if len(parts) == 3:
                panel, resolution, font = parts
                _bucket(panel)[1][(resolution, font)] = (outcome, reason)
                continue

        # Non-structured render test: a single result, not part of a matrix.
        name = nodeid.split("::")[-1].replace("test_", "").strip("_") or "render"
        _bucket(name)[2].append((outcome, reason))

    lines = ["=== Render fit results ==="]
    for name, cells, plain in buckets:
        outcomes = [o for o, _ in cells.values()] + [o for o, _ in plain]
        passed = sum(1 for o in outcomes if o == "passed")
        skipped = sum(1 for o in outcomes if o == "skipped")
        failed = sum(1 for o in outcomes if o in ("failed", "error"))
        total = len(outcomes)

        resolutions = sorted({r for r, _ in cells}, key=_res_key)
        fonts = sorted({f for _, f in cells})
        coverage = ""
        if cells:
            coverage = f"  ({len(resolutions)} resolutions x {len(fonts)} font sizes)"

        matrix_failures = [
            (r, f, o, rs) for (r, f), (o, rs) in cells.items() if o in ("failed", "error")
        ]
        plain_failures = [(o, rs) for (o, rs) in plain if o in ("failed", "error")]

        # A panel whose matrix is entirely TODO-skipped carries no result to
        # report, so it is omitted rather than printed as a "N skipped" row.
        if skipped and not passed and not failed:
            continue

        lines.append(
            f"{name}: {passed}/{total} passed{coverage}"
            + (f", {skipped} skipped" if skipped else "")
        )
        for resolution, font, outcome, reason in sorted(
            matrix_failures, key=lambda t: (_res_key(t[0]), t[1])
        ):
            lines.append(f"  FAIL {resolution}  {font}  {outcome} - {reason}")
        for outcome, reason in plain_failures:
            lines.append(f"  {outcome} - {reason}")
    return lines


def _res_key(resolution):
    try:
        w, h = map(int, resolution.split("x"))
    except ValueError:
        return len(_RESOLUTION_ORDER)
    try:
        return _RESOLUTION_ORDER.index((w, h))
    except ValueError:
        return len(_RESOLUTION_ORDER)
