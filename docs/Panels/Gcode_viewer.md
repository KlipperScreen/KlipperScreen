# G-code Toolpath

The G-code toolpath panel supports two preview contexts with the same cached parser and renderer stack:

- `selected_file` previews a chosen G-code file before printing.
- `active_print` previews the file that is currently printing.

The panel still renders lightweight 2D and 3D toolpath views with GTK 3 and Cairo, so it stays suitable for low-power KlipperScreen hardware without a browser, OpenGL, or WebGL dependency.

## Entry Points

- `Print Control -> Preview` opens the viewer in `active_print` context.
- `Print -> list view -> Preview` opens the viewer in `selected_file` context for the chosen file.

The file-list Preview action does not start the print by itself.

## Shared Controls

- `2D` / `3D` switches instantly between the top-down view and the spatial toolpath view without reloading or reparsing the file.
- `Fit` recenters the current visible toolpath range.
- `Reset` returns 2D to the default fitted top-down view and 3D to the default isometric camera.
- `Mode` cycles between `Current layer`, `Current + previous`, and `Full model`.
- `Travel` toggles visibility of travel moves.
- In `2D`, dragging the canvas pans the view.
- In `3D`, dragging rotates yaw and pitch by default, and the compact `Rotate` / `Pan` toggle changes whether dragging rotates or pans.

## Selected File Preview

`selected_file` context uses the explicitly selected filename from the G-code file list and never follows `print_stats.filename`.

Additional controls appear only in this context:

- a vertical `Layer` slider for manual Z-layer selection using the parsed layer table
- a horizontal `Preview Progress` slider for movement-sequence navigation within the selected layer

Behavior:

- changing the layer slider resets movement progress to the beginning of the newly selected layer
- changing either slider does not reload, reparse, or submit a background worker
- the same `ToolpathModel` instance is reused for both 2D and 3D views
- switching between 2D and 3D preserves the selected layer and movement position

Mode behavior in `selected_file` context:

- `Current layer` shows only the selected layer
- `Current + previous` shows configured previous layers as completed and the selected layer with simulated progress
- `Full model` shows previous layers as completed, the selected layer with simulated progress, and future layers as pending

The selected-file preview does not use live printer progress and does not inhibit screen blanking.

## Active Print Preview

`active_print` context continues to use live printer state:

- filename resolution follows the current active-print logic
- progress comes from `virtual_sdcard.file_position`
- executed, current, and pending styling follow live print progress
- manual layer and movement sliders are not shown
- screen-blanking inhibition remains limited to active 3D preview only

## 3D Camera

- Default 3D camera: yaw `45` degrees, pitch `35` degrees, orthographic projection.
- `Fit` projects the visible 3D toolpath bounds through the current yaw and pitch before choosing zoom and pan.
- Previous layers remain at their real Z heights below the current layer.
- Travel moves, Z-hop, and non-planar moves use their real parsed Z coordinates when available.

## Limitations

- The current implementation renders `G0` and `G1` moves only.
- `G2` and `G3` arc commands are ignored safely and are not rendered yet.
- Very large files still require a full parse before the first preview appears.
- The 3D view uses Cairo software projection and depth-sorted line batches instead of OpenGL.
- If 3D projection fails, the panel falls back to 2D instead of crashing KlipperScreen.
- A dedicated `Print` action inside the selected-file preview has not been added yet; printing still uses the existing file-list workflow.
