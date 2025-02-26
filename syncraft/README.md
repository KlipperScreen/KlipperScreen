# Syncraft

This is a modification of [KlipperScreen](https://github.com/klipperscreen/klipperscreen.git), adapted to meet the specific needs of Syncraft printers. Within this directory you can find Syncraft additional assets.

--- 

## Extra panels

Panels from Syncraft have the `sx_` prefix.

### `sx_filament_(idex|x1).py`

Copy from original panel `extrude.py`. Used to set both nozzle and material from `extruder`.

### `sx_nozzle.py`

<!-- TODO: Change name of nozzle0 and nozzle1 variables -->
Used to set the [printer variables](https://www.klipper3d.org/Config_Reference.html#save_variables) `nozzle0` or `nozzle1` based on the currently active extruder.

This ensures the printer can cancel a print via `PARAMETERS_MATCH` macro if its 3D model has been sliced for a different nozzle.

A `sensor` boolean parameter can be passed, making it behave diferently at the function `on_image_clicked`.

### `sx_materials.py`

Uses the `materials.json` file to render the available materials to the current active extruder.

<!-- TODO: Change name of material_ext0 and material_ext1 variables -->
Used to set the [printer variables](https://www.klipper3d.org/Config_Reference.html#save_variables) `material_ext0` or `material_ext1` based on the currently active extruder.

This ensures the printer can cancel a print via `PARAMETERS_MATCH` macro if its 3D model has been sliced for a different material.

A `sensor` boolean parameter can be passed, making it behave diferently at the function `set_material`.

### `sx_welcome.py`

Setup panel that replaces `main_menu.py` if the option `welcome` from the `[syncraft]` section is set to `True` at the KlipperScreen configuration file (it is by default). After clicking on the finish button, the `welcome` will be set to `False`, so the panel `main_menu.py` will be the first panel in the next startup.

### `sx_calibrate.py` and `sx_calibrate_*.py` panels

#### `calibrate.py`

Menu to select Syncraft calibration panels more easiliy.

#### `calibrate_*.py`

Syncraft calibration panels.

### `sx_set_model.py`

Panel shown at startup when no `model` option is found at `[syncraft]` section in KlipperScreen configuration file.

---

## Modifications

### `config/*.conf`

- Hide and add menu panels.

### `config/defaults.conf`

- Disable `side_macro_shortcut`.
- Set default theme to `material-darker`.
- Default welcome screen when start screen.

### `KlippyGtk.py`

- Allow `Image` and `Button` functions to search from specific directory.

### `config.py`

- Remove `side_macro_shortcut` toggle option.
- Add Syncraft required variables
- Implement `if` statement on `validate_config` function to enable `[syncraft]` section on configuration.
- Implement `[syncraft]` options at `_create_configurable_options`. 

### `screen.py`

- Remove function `toggle_shortcut` related to `side_macro_shortcut` toggling.
- Retrieves options `[syncraft]` section to start screen with different panels dinamically at function `state_ready`.
- Add extra functions `delete_panel`, `run_state_callback`, `syncraft_get_model`, `finish_inserting_filament` and `save_variables_file`.
- Detect filament based on model at `process_update` before passing it to current panel.
- Add properties `detected_filament`, `inserting_filament`, and `variables` to help with filament detection.

### `panels/settings.py`

- Prevent some options from `KlipperScreenConfig` `configurable_options` to be shown:
	```python
	ignore_options = (...)
	if name in ignore_options:
		continue
	```

### `panels/menu.py`

- Hardcode `sx_filament` button behaviour at function `create_menu_items` to open different menu items based on the option `model` from `[syncraft]`.
