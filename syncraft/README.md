# Syncraft

This is a modification of [KlipperScreen](https://github.com/klipperscreen/klipperscreen.git), adapted to meet the specific needs of Syncraft printers. Within this directory you can find Syncraft additional assets.

--- 

## Extra panels

Panels that are not original from KlipperScreen.

### `filament.py`

Copy from original panel `extrude.py`. Used to set both nozzle and material from `extruder`.

### `nozzle.py`

<!-- TODO: Change name of nozzle0 and nozzle1 variables -->
Used to set the [printer variables](https://www.klipper3d.org/Config_Reference.html#save_variables) `nozzle0` or `nozzle1` based on the currently active extruder.

This ensures the printer can cancel a print via `PARAMETERS_MATCH` macro if its 3D model has been sliced for a different nozzle.

### `materials.py`

Uses the `materials.json` file to render the available materials to the current active extruder.

<!-- TODO: Change name of material_ext0 and material_ext1 variables -->
Used to set the [printer variables](https://www.klipper3d.org/Config_Reference.html#save_variables) `material_ext0` or `material_ext1` based on the currently active extruder.

This ensures the printer can cancel a print via `PARAMETERS_MATCH` macro if its 3D model has been sliced for a different material.

---

## Modifications

### `config/*.conf`

- Hide these menu panels:
	- `extrude.py`
	- `temperature.py`
	- `gcode_macros.py`
- Add these menu panels:
	- `filament.py`

### `KlippyGtk.py`

- Allow `Image` and `Button` functions to search from specific directory.

### `config.py`

- Remove `side_macro_shortcut` toggle option.
- Add Syncraft required variables

### `screen.py`

- Remove function `toggle_shortcut` related to `side_macro_shortcut` toggling.