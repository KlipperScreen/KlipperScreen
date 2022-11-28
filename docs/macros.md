# Supported Macros

## Extrude Panel

### LOAD_FILAMENT / UNLOAD_FILAMENT
Load and Unload Filament macros are used in the Extrude-Panel if it is available.
The selected speed is transferred to this macro.
The following example macros show how this can be used in the macro.

```jinja
[gcode_macro LOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(300) %}
    {% set max_velocity = printer.configfile.settings['extruder'].max_extrude_only_velocity %}
    SAVE_GCODE_STATE NAME=load_state
    M300 # beep
    G91
    G92 E0
    G1 E350 F{max_velocity} # fast-load
    G1 E25 F{speed} # purge
    M300
    M300
    RESTORE_GCODE_STATE NAME=load_state
```

```jinja
[gcode_macro UNLOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(300) %}
    {% set max_velocity = printer.configfile.settings['extruder'].max_extrude_only_velocity %}
    SAVE_GCODE_STATE NAME=unload_state
    G91
    M300 # beep
    G92 E0
    G1 E25 F{speed} # purge
    G1 E-420 F{max_velocity} # fast-unload
    M300
    M300
    RESTORE_GCODE_STATE NAME=unload_state
```
