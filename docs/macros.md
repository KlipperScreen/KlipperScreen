# Macros

## Recommended

!!! note
     If you have already installed other UIs then you may have this macros already, and it's usually asked by KIAUH

None of the following macros are strictly required for KlipperScreen, but they provide the toolhead parking at pause and cancel.

These can be assumed sane defaults, but should be checked and modified to your own needs.


### Pause
```yaml+jinja title="printer.cfg"
[gcode_macro PAUSE]
description: Pause the actual running print
rename_existing: PAUSE_BASE
gcode:
  PAUSE_BASE
  _TOOLHEAD_PARK_PAUSE_CANCEL
```

### Resume
```yaml+jinja title="printer.cfg"
[gcode_macro RESUME]
description: Resume the actual running print
rename_existing: RESUME_BASE
gcode:
  ##### read extrude from  _TOOLHEAD_PARK_PAUSE_CANCEL  macro #####

  {% set extrude = printer['gcode_macro _TOOLHEAD_PARK_PAUSE_CANCEL'].extrude %}
  #### get VELOCITY parameter if specified ####
  {% if 'VELOCITY' in params|upper %}
    {% set get_params = ('VELOCITY=' + params.VELOCITY)  %}
  {%else %}
    {% set get_params = "" %}
  {% endif %}
  ##### end of definitions #####
  {% if printer.extruder.can_extrude|lower == 'true' %}
    M83
    G1 E{extrude} F2100
    {% if printer.gcode_move.absolute_extrude |lower == 'true' %} M82 {% endif %}
  {% else %}
    {action_respond_info("Extruder not hot enough")}
  {% endif %}

  RESUME_BASE {get_params}
```

### Park

```yaml+jinja title="printer.cfg"
[gcode_macro _TOOLHEAD_PARK_PAUSE_CANCEL]
description: Helper: park toolhead used in PAUSE and CANCEL_PRINT
variable_extrude: 1.0
gcode:
  ##### set park positon for x and y #####
  # default is your max posion from your printer.cfg

  {% set x_park = printer.toolhead.axis_maximum.x|float - 5.0 %}
  {% set y_park = printer.toolhead.axis_maximum.y|float - 5.0 %}
  {% set z_park_delta = 2.0 %}
  ##### calculate save lift position #####
  {% set max_z = printer.toolhead.axis_maximum.z|float %}
  {% set act_z = printer.toolhead.position.z|float %}
  {% if act_z < (max_z - z_park_delta) %}
    {% set z_safe = z_park_delta %}
  {% else %}
    {% set z_safe = max_z - act_z %}
  {% endif %}
  ##### end of definitions #####
  {% if printer.extruder.can_extrude|lower == 'true' %}
    M83
    G1 E-{extrude} F2100
    {% if printer.gcode_move.absolute_extrude |lower == 'true' %} M82 {% endif %}
  {% else %}
    {action_respond_info("Extruder not hot enough")}
  {% endif %}
  {% if "xyz" in printer.toolhead.homed_axes %}
    G91
    G1 Z{z_safe} F900
    G90
    G1 X{x_park} Y{y_park} F6000
    {% if printer.gcode_move.absolute_coordinates|lower == 'false' %} G91 {% endif %}
  {% else %}
    {action_respond_info("Printer not homed")}
  {% endif %}
```

### Cancel

```yaml+jinja title="printer.cfg"
[gcode_macro CANCEL_PRINT]
description: Cancel the actual running print
rename_existing: CANCEL_PRINT_BASE
variable_park: True
gcode:
  ## Move head and retract only if not already in the pause state and park set to true

  {% if printer.pause_resume.is_paused|lower == 'false' and park|lower == 'true'%}
    _TOOLHEAD_PARK_PAUSE_CANCEL
  {% endif %}

  TURN_OFF_HEATERS
  CANCEL_PRINT_BASE
```

## Extrude Panel

### LOAD_FILAMENT / UNLOAD_FILAMENT

This macros are used in the Extrude panel `Load` and `Unload` buttons. and they will be hidden from the macros panel.

The selected speed in the panel is transferred as a parameter.

The following examples show how this can be used:

```yaml+jinja title="  printer.cfg"
[gcode_macro LOAD_FILAMENT]
variable_load_distance:  50
variable_purge_distance:  25
gcode:
    {% set speed = params.SPEED|default(300) %}
    {% set max_velocity = printer.configfile.settings['extruder'].max_extrude_only_velocity  * 60 %}
    SAVE_GCODE_STATE NAME=load_state
    G91
    G92 E0
    G1 E{load_distance} F{max_velocity} # fast-load
    G1 E{purge_distance} F{speed} # purge
    RESTORE_GCODE_STATE NAME=load_state
```

!!! warning
    `variable_load_distance` will depend on the printers distance from the extruder to the nozzle.

    For printers with long bowden tubes you may have to increase the extrude only distance in the configfile

    ```ini title="  printer.cfg"
    [extruder]
    max_extrude_only_distance: 600 # default is 50mm
    ```


```yaml+jinja title="  printer.cfg"
[gcode_macro UNLOAD_FILAMENT]
variable_unload_distance:  50
variable_purge_distance:  25
gcode:
    {% set speed = params.SPEED|default(300) %}
    {% set max_velocity = printer.configfile.settings['extruder'].max_extrude_only_velocity  * 60 %}
    SAVE_GCODE_STATE NAME=unload_state
    G91
    G92 E0
    G1 E{purge_distance} F{speed} # purge
    G1 E-{unload_distance} F{max_velocity} # fast-unload
    RESTORE_GCODE_STATE NAME=unload_state
```

if it loads too fast and your extruder can't keep up, you should adjust the `max_extrude_only_velocity` in `printer.cfg`


## Hidden by the interface

All gcode_macros with the attribute `rename_existing` are hidden , because these are default Klipper Gcodes
and these should be implemented in KlipperScreen itself with buttons already.
[This is the same behaiviour of other UIs](https://docs.mainsail.xyz/overview/features/hide-macros-outputs-or-fans#macros-with-rename_existing)

[LOAD_FILAMENT and UNLOAD_FILAMENT are also hidden](#load_filament-unload_filament)

## Hide Macros

Macros can be completely hidden in the interface by prefixing the name with an underscore.

```yaml+jinja title="  printer.cfg"
[gcode_macro MY_AWESOME_GCODE]
gcode:
    _MY_HELPER_CODE

[gcode_macro _MY_HELPER_CODE]
gcode:
    M300
```

`MY_AWESOME_GCODE` appears in your interface settings, but `_MY_HELPER_CODE` does not.

