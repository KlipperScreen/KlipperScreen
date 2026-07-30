# Live G-code Renderer

## Current KlipperScreen architecture

KlipperScreen is a GTK 3 application rooted in [screen.py](/D:/007-CODEX/KlipperScreen/screen.py).
Panels are loaded dynamically from the `panels/` package through `KlipperScreen.show_panel()`, and the active panel receives printer updates through `KlipperScreen.process_update()`.

The printer state model lives in [ks_includes/printer.py](/D:/007-CODEX/KlipperScreen/ks_includes/printer.py). Moonraker websocket and UDS callbacks are marshalled back onto the GTK main thread with `GLib.idle_add()` in [ks_includes/KlippyWebsocket.py](/D:/007-CODEX/KlipperScreen/ks_includes/KlippyWebsocket.py) and [ks_includes/KlippyUDS.py](/D:/007-CODEX/KlipperScreen/ks_includes/KlippyUDS.py).

The current print panel is [panels/job_status.py](/D:/007-CODEX/KlipperScreen/panels/job_status.py). It already consumes `print_stats`, `virtual_sdcard`, `motion_report`, and file metadata updates, so the live toolpath feature can integrate without changing print control behavior.

File metadata and thumbnail discovery are handled by [ks_includes/files.py](/D:/007-CODEX/KlipperScreen/ks_includes/files.py). REST access to Moonraker-backed file resources is handled by [ks_includes/KlippyRest.py](/D:/007-CODEX/KlipperScreen/ks_includes/KlippyRest.py).

GTK worker-thread usage already exists through the shared `ThreadPoolExecutor` in [ks_includes/KlippyGtk.py](/D:/007-CODEX/KlipperScreen/ks_includes/KlippyGtk.py). The renderer implementation should reuse that executor for parsing and cache IO, while keeping all widget mutation on the GTK main thread.

GTK drawing widgets in this repository already use Cairo, for example [ks_includes/widgets/heatergraph.py](/D:/007-CODEX/KlipperScreen/ks_includes/widgets/heatergraph.py). The live renderer follows that pattern instead of introducing a browser, WebGL, or extra rendering dependency.

There is no existing automated test tree in this checkout, so parser, cache, and progress mapping tests will be added as isolated Python unit tests that do not require GTK, Moonraker, or printer hardware.

## Implemented design

- `panels/gcode_viewer.py` owns the GTK panel, touch controls, and async load lifecycle.
- `panels/gcodes.py` can now open `gcode_viewer` in `selected_file` context directly from the file list.
- `ks_includes/gcode_renderer/parser.py` parses `G0`, `G1`, `G90`, `G91`, `M82`, `M83`, and `G92`.
- `ks_includes/gcode_renderer/model.py` stores toolpath segments, real start/end Z values, layer ranges, and byte-offset progress mapping.
- `ks_includes/gcode_renderer/cache.py` stores parsed models outside the repository using a file fingerprint.
- `ks_includes/gcode_renderer/geometry.py` keeps the 2D viewport math isolated from GTK.
- `ks_includes/gcode_renderer/projection.py` keeps 3D camera state, yaw/pitch math, orthographic projection, and projected-fit helpers isolated from GTK and Cairo.
- `ks_includes/gcode_renderer/renderer.py` renders either the existing 2D top-down view or the new 3D toolpath scene through Cairo with shared parsed model data.
- `ks_includes/gcode_renderer/preview.py` resolves explicit preview context and selected-file navigation state without GTK dependencies.

## Preview contexts

The viewer now supports two explicit contexts:

- `selected_file`
  Used by the file list Preview action before printing.
- `active_print`
  Used by Print Control Preview during an active print.

Context rules:

- `selected_file` always uses the explicitly supplied filename.
- `selected_file` never replaces that filename from `print_stats.filename`.
- `active_print` keeps the existing robust filename resolution against `print_stats` and `virtual_sdcard`.
- unknown context values fall back to a safe idle state instead of silently mixing behaviors.

## 2D and 3D views

The panel now supports two display views backed by the same parsed `ToolpathModel` instance:

- `2d` keeps the existing top-down toolpath renderer, including pan, zoom, in-plane rotation, fit, reset, current-layer modes, travel visibility, and live progress styling.
- `3d` renders the G-code path itself as a stacked spatial toolpath using real X, Y, and Z move coordinates.

The 3D path is not an STL mesh renderer and does not synthesize filled surfaces between layers.

Switching between `2d` and `3d`:

- does not reload the G-code file
- does not reparse the file
- does not restart the panel
- does not reset selected-file layer or move selection
- does not interrupt printing

## Selected-file navigation

`selected_file` context adds two temporary, non-persistent navigation controls:

- a vertical `Layer` slider for parsed layer selection
- a horizontal `Preview Progress` slider for movement-sequence navigation inside the selected layer

These controls:

- use the parsed layer table and segment ordering directly
- respect variable layer heights through `ToolpathModel.layer_zs`
- include travel moves in sequence ordering even when travel rendering is hidden
- do not trigger reparsing, file reloads, or executor submissions while dragging
- preserve camera, zoom, pan, yaw, and pitch unless the user explicitly presses `Fit` or `Reset`

The default selected-file state is the final printable layer at the beginning of that layer.

Mode behavior for `selected_file`:

- `current_layer`: selected layer only
- `current_and_previous`: previous layers shown as completed, selected layer shown with simulated progress
- `full_model`: previous layers completed, selected layer simulated, future layers pending

## Active print behavior

`active_print` continues to use live printer progress:

- `virtual_sdcard.file_position` remains authoritative
- manual sliders are not created for this context
- live toolhead tracking remains unchanged
- screen blanking inhibition remains active only for `active_print` + `3d`

## 3D projection and camera

The Cairo 3D path uses a lightweight software projection pipeline:

1. translate model coordinates around the selected toolpath center
2. rotate around Z by yaw
3. rotate around X by pitch
4. apply orthographic projection
5. apply zoom
6. apply pan
7. translate to the canvas center
8. invert screen Y for Cairo coordinates

Coordinate conventions:

- model X and Y use printer toolpath coordinates
- model Z uses the parsed move height, including Z-hop travel when present
- positive screen-up comes from the final Cairo Y inversion

Default 3D camera values:

- yaw: `45` degrees
- pitch: `35` degrees
- projection: `orthographic`

Pitch is clamped to keep the view stable on touch hardware.

## 3D fit and depth ordering

3D `Fit` uses visible extrusion bounds first and falls back to travel bounds only when no printable extrusion exists.

For the current visible layer range, it:

- builds a real 3D bounding box from visible segment endpoints
- projects the box corners through the current yaw and pitch
- computes zoom with a safety margin
- recenters the projected result with pan

The 3D renderer sorts projected line segments by camera-space depth when the camera or visible geometry changes, then reuses that cached projected scene for live progress updates. This keeps status refreshes from rebuilding the static projection unnecessarily.

## Progress mapping

Live progress in `active_print` is mapped from `virtual_sdcard.file_position`.

Each rendered segment records the source byte offset of the line that produced it. During live updates the panel converts the current Moonraker file position into:

- completed segments
- current segment
- current rendered layer

This avoids relying on repeated XYZ coordinates.

In `selected_file`, the panel instead synthesizes `ProgressInfo` from:

- selected parsed layer index
- selected ordered move index inside that layer

This keeps the renderer styling path shared between live and pre-print previews.

## Cache behavior

The cache fingerprint uses:

- full G-code path
- file size
- modification timestamp

The default cache directory is:

- `~/printer_data/.cache/KlipperScreen/gcode_renderer` when `~/printer_data` exists
- otherwise `~/.cache/KlipperScreen/gcode_renderer`

Cache corruption and stale entries are treated as recoverable misses.

## Performance decisions

- Parsing is delegated to KlipperScreen's shared executor instead of the GTK main loop.
- Rendering is limited to visible layer ranges when possible.
- Progress lookup uses precomputed segment end offsets.
- Selected-file move navigation uses direct layer range indexes instead of reparsing or scanning the full file on every drag.
- The preview timer only queues redraws when the rendered state changes.
- The 3D renderer caches projected segments for the current camera, visible layer range, and canvas allocation.
- Live progress recolors the existing projected scene instead of rebuilding projection data when the camera is unchanged.
- Large 3D drags may temporarily sample visible segments to keep touch interaction responsive on lower-power hardware.

## Known limitations

- `G2` and `G3` are not rendered yet.
- The current implementation downloads the selected G-code file as a single payload before parsing.
- The 3D view is still a Cairo software renderer, so extremely large visible layer ranges can be slower than the 2D top-down mode.
- If 3D projection encounters invalid segment coordinates, those segments are skipped and the panel stays responsive.
- The selected-file preview currently reuses the existing file-list print workflow instead of adding a new dedicated Print button inside the viewer.
- Translation catalogs were updated manually in this environment because GNU gettext tools were unavailable.

## Testing

Current automated coverage exercises:

- absolute and relative motion
- absolute and relative extrusion
- `G92`
- travel and retraction detection
- layer detection with and without slicer comments
- malformed lines and unsupported commands
- byte offset tracking
- cache invalidation
- render-range selection helpers
- explicit preview context resolution
- selected-file layer and move mapping
- file-list Preview action routing
- selected-file and active-print progress separation
