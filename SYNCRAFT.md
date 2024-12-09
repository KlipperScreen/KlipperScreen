# Syncraft

This is a modification of the original software, adapted to meet the specific needs of Syncraft printers.

## Extra panels

### `filament.py`

Used to set the [printer variables](https://www.klipper3d.org/Config_Reference.html#save_variables) `nozzle0` or `nozzle1` based on the currently active extruder.

This ensures the printer can cancel a print via `PARAMETERS_MATCH` macro if its 3D model has been sliced for a different nozzle.