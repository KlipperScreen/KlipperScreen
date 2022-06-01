# Supported Macros

## Extrude Panel

### LOAD_FILAMENT / UNLOAD_FILAMENT
Load and Unload Filament macros are used in the Extrude-Panel if it is available.
The selected speed is transferred to this macro.
The following example macros show how this can be used in the macro.

```py
[gcode_macro LOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(500) %}
    G91
    G1 E50 F{speed}
    G1 E50 F{speed}
    G92
```
```py
[gcode_macro UNLOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(500) %}
    G91
    G1 E-50 F{speed}
    G1 E-50 F{speed}
    G92
```

this could be interesting to tweak the purge speed, this would be one Example Macro from alfrix:

```py
[gcode_macro LOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(300) %}
    {% set max_velocity = printer.configfile.settings['extruder'].max_extrude_only_velocity %}
    M300 # beep
    G91
    G92 E0
    G1 E350 F{max_velocity}
    G1 E25 F{speed} #purge
    M300
    M300
```

```py
[gcode_macro UNLOAD_FILAMENT]
gcode:
    {% set speed = params.SPEED|default(300) %}
    {% set max_velocity = printer.configfile.settings['extruder'].max_extrude_only_velocity %}
    G91
    M300 # beep
    G92 E0
    G1 E25 F{speed} # purge
    G1 E-420 F{max_velocity}
    M300
    M300
```
