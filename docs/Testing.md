# Testing

This document covers the development/testing work added on top of KlipperScreen
for verifying that panels actually render correctly on the target hardware
profile: a small touchscreen, rendered by real GTK under a headless Weston compositor.

It is split into four parts:

1. [The fit test](#the-fit-test) — the authoritative "does this panel fit its
   screen" check.
2. [The preview tool](#the-preview-tool) — "open a panel to view it".
3. [The fakes](#the-fakes) — `tests/fakes/runtime.py` and what it mirrors.
4. [TODO / remaining work](#todo--remaining-work).

---

## The fit test

### Files

| File | Role |
| --- | --- |
| `tests/render/test_fit_matrix.py` | The test. Builds the real host, injects a panel, asserts it fits. |
| `tests/render/fit.py` | `check_fit()` (the clip metric) + `realize()` (map into a window). |
| `tests/render/conftest.py` | Session-scoped headless Weston fixture + a bounded GLib pump. |
| `tests/conftest.py` | Makes `tests`/`tests/fakes`/repo importable and installs the **real** translations. |

### What it checks — two layers

The fit is verified in two independent layers:

1. **Host fits the resolution** (`_host_fits`). The host `main_grid`'s
   *minimum* preferred size must fit the requested resolution:
   `main_grid.get_preferred_width()[0] <= width` and
   `main_grid.get_preferred_height()[0] <= height`
2. **Nothing beneath is clipped** (`check_fit`). Over the whole tree — chrome
   and panel, every widget level — no visible, non-scrollable, non-expanding
   widget's natural size exceeds its *parent's* allocation.

### How the fit paths use these layers

The matrix (`test_panels_fit_matrix`) drives `preview_panel.build_and_measure`
for every panel × resolution × font. Its `fits` is the **host-min** signal —
`main_grid`'s minimum preferred size fits the resolution. `check_fit` violations
are reported for reference but are **not** the gate, because compressible /
ellided containers (a homogeneous grid squeezing, an ellipsized combobox) are
handled, not unreachable — gating on them would false-fail healthy panels such
as `zcalibrate` and `job_status`.

### Why not a bare `panel.content` test

The panel never renders alone:

```python
overlay.add_overlay(base_panel.main_grid)  # titlebar + action bar + battery/time
base_panel.add_content(panel)  # the panel inside the chrome
```

so the tree that actually appears on the touch screen is **`main_grid`** — the
chrome *plus* the panel. The titlebar and action bar consume real pixels, so
`panel.content` is laid out inside a **smaller, chrome-adjusted region** (e.g.
720×461 on an 800×480 screen, not 800×480). A test that maps `panel.content`
into a bare window gives it more space than reality and would **false-pass**
anything that clips against the chrome boundary. That is worthless.

So this test does the real thing:

1. Build the **real `BasePanel`** host.
2. Inject the panel via `add_content` (the same path as `screen.attach_panel`).
3. Realize `host.main_grid` into a real window at the target resolution.
4. Run the two fit layers above over the whole tree.

Loading the shipped CSS + theme is essential — see below — otherwise the layout
is bare Adwaita and any CSS-driven sizing (e.g. button padding) is inert, so the
check would false-pass.

### The clip metric — `check_fit(root)`

A widget is **clipped** when GTK gives it less space than it asks for and the
excess falls outside the box it lives in — on a touch screen that clipped
content is unreachable, which is the failure we guard against.

GTK lays a child out to at most its parent's allocated size. So a widget that
does **not** expand clips when its *natural* preferred size exceeds its
**parent's** allocated size. An expanding widget is stretched to fill its parent,
so its natural size is irrelevant and it never clips. Therefore, for a visible
widget in a live container:

```
non-scrollable widget clips  iff  natural_size > parent_allocation
                                 (per dimension it does not expand)
```

`check_fit` walks the whole tree and flags every **visible, non-scrollable,
non-expanding** widget whose natural size exceeds its parent's allocation. Three
cases are deliberately excluded, because they are not screen overflow:

* **Hidden widgets** (`get_visible() == False`) are not rendered.
* **Widgets inside a parent allocated ≤ 2px** are already collapsed with that
  parent (an empty/hidden container).
* **Anything inside a `Gtk.ScrolledWindow`** overflows by design (scrolling), so
  it is not a fit failure.

`check_fit` covers everything *beneath* the host; the host-vs-screen fit is the
caller's job, done by `_host_fits`. The numbers come from real GTK allocation, so
the view cannot be faked.

### Why the minimum-prefixed signal (and not the anchor alone)

On this test host the window is **unfixed** and, under Wayland, cannot be forced
to clip — there is no `set_max_size` on `GdkWaylandWindow`. So an overflowing
panel here does not clip: it **grows**, pushing the committed allocation past the
request. A real fixed display, by contrast, clips immediately.

The host's **minimum preferred size** is the one signal that reveals both
failures: if it already exceeds the request, the content will either grow the
window (here) or clip (on a real fixed display). That is why `_host_fits` is
authoritative and the exact-equality anchor is secondary.

### Resolutions and font sizes

The test sweeps the full `resolution × font_size` matrix. Vertical mode is
derived from width/height.

| Resolution (w × h) | Mode |
| --- | --- |
| 480 × 320 | landscape |
| 800 × 480 | landscape |
| 1024 × 600 | landscape |
| 320 × 480 | portrait |
| 480 × 800 | portrait |
| 600 × 1024 | portrait |

```python
FONT_SIZES = ["small", "medium", "large", "extralarge", "max"]
```

`test_metric_detects_genuine_overflow` is the negative case: at **100×100** the
window is far below the host's minimum preferred size, so `_host_fits` must fail
— a suite that only ever passes proves nothing.

### Running a single panel

The matrix is parametrized from the `--fit-panel` CLI option, so you can check
one panel (or a comma-separated list) instead of the whole sweep:

```bash
# Only bed_level: 6 resolutions x 5 fonts = 30 cases, not the full matrix.
pytest -m render --fit-panel bed_level

# A few panels at once.
pytest -m render --fit-panel bed_level,zcalibrate,temperature
```

The option is registered in the early-load shared `tests/conftest.py` (a
per-directory conftest loads too late to register a CLI option), so it works from
the repo root. Unknown panel names fail fast rather than collecting nothing. With
no `--fit-panel`, the full `TESTED_PANELS` matrix runs. (This is the same fit path
the `--sweep` flag in `tests/preview_panel.py` drives; that tool also opens a
single panel interactively with `python tests/preview_panel.py [panel]`.)

### No X11

Only Weston is used, and it is Wayland-only. `GDK_BACKEND=wayland` forces GTK to
never fall back to X11 (deprecated). There is deliberately
no Xvfb, no XWayland, no X-linked fallback. The Weston socket lives in a fresh
temp `XDG_RUNTIME_DIR`; the fixture restores the environment afterwards, so the
live session is untouched.

---

## The preview tool

### File

`tests/preview_panel.py`

### Purpose

A way to **open any panel, fully rendered, so a human can eyeball it** — the real
base-panel chrome plus the panel plus realistic live data — on the current
Wayland session, without any hoops. It is *not* a bare `panel.content` preview.

### Usage

```bash
python tests/preview_panel.py [panel] [OPTIONS]
```

Examples:

```bash
python tests/preview_panel.py temperature
python tests/preview_panel.py temperature -w 1280 -h 720
python tests/preview_panel.py main_menu -t material-light
python tests/preview_panel.py job_status --random
```

All of the data the tool seeds — the deterministic active-print state and the
temp-graph time-store parameters — lives in one editable file,
`tests/assets/mock_printer_state.json`. Change a target temp, the filename, or
progress there and re-run; no code edits needed. `--random` (job_status only)
animates the live feed, sweeping each field between `0` and its nominal value
from that file.

It builds the real `BasePanel` host, injects the panel the way `screen.attach_panel`
does, seeds realistic data (device temps **and** the temperature-graph time store
so the chart paints), maps `main_grid` into a real window, and leaves it open —
close the window (or Ctrl-C) to quit.

While it runs it logs layout problems:

- `[SIZE] <user|auto> … size changed AxB -> CxD` whenever the committed window
  size changes. `user` is tagged when the pointer is dragging the window;
  otherwise it is `auto`. On Wayland the configure/size-allocate signals don't
  fire reliably, so this tag is a best-effort hint (pointer-drag state) — the
  won't-fit decision does not depend on it.
- `[WARN] … layout won't fit …` when the panel's *own minimum size request*
  already exceeds the requested resolution (`main_grid` min width > width or
  min height > height) — on a real fixed display the content is clipped at the
  requested resolution. This is the reliable host-level signal. (The committed
  window's "grow" is intentionally *not* used here: under headless Weston the
  window gains a constant frame, so `committed` exceeds the request for every
  panel regardless of content and cannot distinguish fit from overflow. The
  `--sweep` programmatic path uses the same min-size signal — see
  `build_and_measure`.)

This is how you catch e.g. a panel whose minimum is 840px wide but is requested
at 800×480 — the layout won't fit at that resolution.

The `--theme` option selects a theme under `styles/` (default `material-dark`).
It is applied exactly like the main app: `screen.load_base_styles()` then
`screen.change_theme(theme)` before the content panel is built, so the panel
renders with the real theme CSS rather than bare Adwaita.

---

## The fakes

### File

`tests/fakes/runtime.py`

### Design

The fakes are deliberately *thin but faithful*: they reproduce the **exact data
structures** the real objects expose, populated from a representative printer, so
the real panel construction path runs against reality-equivalent input. They do
**not** stub behavior — a panel that reads `printer.get_fans()` gets a method
that returns a real fan list derived from the fake config.

```
config: printer, extruder, heater_bed, fan, output_pin extruder_led, led extruder
data:   extruder0, extruder, heater_bed, fan, toolhead, gcode_move,
        virtual_sdcard, exclude_object, manual_probe, webhooks, print_stats, idle_timeout
```

### What each fake mirrors

| Fake | Mirrors | Notes |
| --- | --- | --- |
| `FakeConfig` | `KlipperScreenConfig` | A real `configparser`. `get_main_config`, `get_config`, `get_printers`, `get_preheat_options`, plus `get_configurable_options`, `lang_list`, `get_language_name`, `get_menu_name`, `get_menu_items`. |
| `FakePrinter` | `Printer` | Query methods derived from config/data: `get_temp_devices/heaters/temp_sensors/temp_fans`, `get_temp_store`/`get_tempstore_size`, `get_tools`/`get_tool_number`, `get_fans`/`get_fan_speed`, `get_pwm_tools`/`get_output_pins`, `get_leds`/`get_led_color_order`, `get_gcode_macros`/`get_macro`, `get_filament_sensors`, `get_probe`, `get_pin_value`, `config_section_exists`, plus `get_stat`/`set_stat`. Attributes `available_commands`, `system_info`, `cameras`, `tempstore`. |
| `FakeState` | `State` | printer name, connection state, `notification_log`. |
| `FakeScreen` | `Screen` | Wires the above together with the **real `KlippyGtk`**. Also loads `gtk.color_list` from `styles/base.conf` `graph_colors` — without it `get_temp_color()` returns `(False, False)` and the `HeaterGraph` crashes with an `IndexError` on `rgb[2]`. |
| `_FakeWs` | `screen._ws` | Interaction only; `send_method` + an `api` proxy that no-ops any method. |
| `_FakeFiles` | `screen.files` | Thumbnails + file-callback/info methods. |
| `_FakeSpoolmanAPI` / `_FakeNotificationHandler` | `Screen.spoolman_api` / `Screen._notification_handler` | Minimal surface used at construction. |
| `_ResetTimeout` | `screensaver` / `lock_screen` | `reset_timeout`, `close`, `lock` no-ops. |

### Important construction-time detail

`ScreenPanel.__init__` reads `screen._config/files/printer/gtk`, and the
`ks_printer_cfg` class attribute is only set later by `base_panel.set_ks_printer_cfg`.
So during construction **every** `if self.ks_printer_cfg is not None:` branch is
skipped — panels that only differ by printer-specific config (screw rotation,
invert flags, power devices, titlebar items, custom z-calibrate commands) build
against the shared defaults. The `set_ks_printer_cfg(...)` call in the test and
preview tool still exists to match production.

---

## TODO

To have a more complete testing environment

- [ ] **Detail-pane checks**: split panels (temperature, job_status) should verify
        the detail pane opens and fits within the chrome-adjusted region.
- [x] **job_status host overflow** (KNOWN BUG): the minimum preferred size
        exceeds the resolution at 3 combinations
        (600x1024 large min 604>600, 600x1024 extralarge min 608>600,
        800x480 extralarge min 812>800); captured as a skipped test in
        `tests/render/test_fit_matrix.py` and fixed there.
- [ ] `SpoolmanAPI` returning spools (spoolman spool_editor panels).
- [x] `screws_tilt_adjust` + `probe` config for the `bed_level` panel (a 3x3
        screw grid + probe offsets) -- `bed_level` is now in the fit matrix.
- [ ] `get_config_section("bed_mesh")` / `stepper_z` / `quad_gantry_level`
        config sections for the remaining leveling panels.
- [ ] `screen.moonraker_endpoint` + `api.get_dir_info`/`get_file_roots` returning
       canned file listings (system, gcodes, updater).
- [ ] `screen.show_popup_message` / dialog helpers that record calls for assertion.
