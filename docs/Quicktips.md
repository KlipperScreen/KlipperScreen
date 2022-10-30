# Quicktips
quick tips, without much explanation


## Hide macros, outputs or fans
As you probably already noticed, you can show and hide the gcode macros in the interface settings,
but you can also hide gcode macros by prefixing the name with an underscore.

```py
[gcode_macro MY_AWESOME_GCODE]
gcode:
    _MY_HELPER_CODE
[gcode_macro _MY_HELPER_CODE]
gcode:
    M300
```

MY_AWESOME_GCODE appears in your interface settings, _MY_HELPER_CODE not.

Another example:

Lets hide a temperature_fan:

```py
[temperature_fan fan1]
[temperature_fan _fan2]
```

fan1 will show in the interface, but _fan2 will be hidden.


## Thumbnails

Moved to [Thumbnails](Thumbnails.md)


## Layer Progress
PrusaSlicer/SuperSlicer > Printer Settings > Custom Gcode > After layer change Gcode

`M117 Layer {layer_num+1}/[total_layer_count] : {filament_settings_id[0]}`

![Layer_progress](img/quicktips/PS_SS_Layer_progress.png)

## Supported Macros
[Macros](macros.md)
