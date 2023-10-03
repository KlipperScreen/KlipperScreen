# Macros

## Hidden by the interface

All gcode_macros with the attribute `rename_existing` are hidden , because these are default Klipper Gcodes
and these should be implemented in KlipperScreen itself with buttons already.
[This is the same behaiviour of other UIs](https://docs.mainsail.xyz/overview/features/hide-macros-outputs-or-fans#macros-with-rename_existing)

[LOAD_FILAMENT and UNLOAD_FILAMENT are also hidden](#load_filament-unload_filament)

## Hide Macros

Macros can be completely hidden in the interface by prefixing the name with an underscore.

```ini
[gcode_macro MY_AWESOME_GCODE]
gcode:
    _MY_HELPER_CODE

[gcode_macro _MY_HELPER_CODE]
gcode:
    M300
```

`MY_AWESOME_GCODE` appears in your interface settings, but `_MY_HELPER_CODE` does not.

## Extrude Panel

### LOAD_FILAMENT / UNLOAD_FILAMENT

This macros are used in the Extrude panel `Load` and `Unload` buttons. and they will be hidden from the macros panel.

The selected speed in the panel is transferred as a parameter.

The following examples show how this can be used:

```ini
[gcode_macro LOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(300) %}
    {% set max_velocity = printer.configfile.settings['extruder'].max_extrude_only_velocity %}
    SAVE_GCODE_STATE NAME=load_state
    M300 # beep
    G91
    G92 E0
    G1 E350 F{max_velocity * 60} # fast-load
    G1 E25 F{speed} # purge
    M300
    M300
    RESTORE_GCODE_STATE NAME=load_state
```

```ini
[gcode_macro UNLOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(300) %}
    {% set max_velocity = printer.configfile.settings['extruder'].max_extrude_only_velocity %}
    SAVE_GCODE_STATE NAME=unload_state
    G91
    M300 # beep
    G92 E0
    G1 E25 F{speed} # purge
    G1 E-420 F{max_velocity * 60} # fast-unload
    M300
    M300
    RESTORE_GCODE_STATE NAME=unload_state
```
