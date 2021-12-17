# Supported Macros
Klipperscreen supports gcode_macros in various panels.

## Extrude Panel

### LOAD_FILAMENT / UNLOAD_FILAMENT
Load and Unload Filament macro is used in the Extrude-Panel if it is available.
The selected speed is transferred to this macro.
The following example macros show how this can be used in the macro.

```
[gcode_macro LOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(500) %}
    G91
    G1 E50 F{speed}
    G1 E50 F{speed}
    G92
```
```
[gcode_macro UNLOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(500) %}
    G91
    G1 E-50 F{speed}
    G1 E-50 F{speed}
    G92
```

