# Syncraft

This is a modification of [KlipperScreen](https://github.com/klipperscreen/klipperscreen.git), adapted to meet the specific needs of Syncraft printers. Within this directory you can find Syncraft additional assets.

## Extra panels

### `filament.py`

Copy from original panel `extrude.py`.

### `nozzle.py`

<!-- TODO: Change name of nozzle0 and nozzle1 variables -->
Used to set the [printer variables](https://www.klipper3d.org/Config_Reference.html#save_variables) `nozzle0` or `nozzle1` based on the currently active extruder.

This ensures the printer can cancel a print via `PARAMETERS_MATCH` macro if its 3D model has been sliced for a different nozzle.

### `materials.py`

Uses the `materials.json` file to render the available materials to the current active extruder.

<!-- TODO: Change name of material_ext0 and material_ext1 variables -->
Used to set the [printer variables](https://www.klipper3d.org/Config_Reference.html#save_variables) `material_ext0` or `material_ext1` based on the currently active extruder.

This ensures the printer can cancel a print via `PARAMETERS_MATCH` macro if its 3D model has been sliced for a different material.

## Hidden panels

- `extrude.py`
- `temperature.py`
- `gcode_macros.py`