# Quicktips
quick tips, without much explanation


## Hide macros, outputs or fans

You can also hide devices by prefixing the name with an underscore.

Lets hide a temperature_fan:

```ini
[temperature_fan fan1]
[temperature_fan _fan2]
```

fan1 will show in the interface, but _fan2 will be hidden.


## Layer Progress

Accurate layer progress as a message below the status:

PrusaSlicer/SuperSlicer > Printer Settings > Custom Gcode > After layer change Gcode

```ini
M117 Layer {layer_num+1}/[total_layer_count] : {filament_settings_id[0]}
```

![Layer_progress](img/quicktips/PS_SS_Layer_progress.png)

Accurate layer progress in the secondary screen of the printing panel:

The layer number in the secondary screen of the printing panelis calculated according to object height and provided layer height.
It will be innacurate when using variable layer height, but can be fixed by providing klipper with the correct data.

![speed_screenshot](img/panels/job_status_speed.png)

PrusaSlicer/SuperSlicer:

Printer Settings > Custom Gcode > Start Gcode

```ini
SET_PRINT_STATS_INFO TOTAL_LAYER=[total_layer_count]
```
Printer Settings > Custom Gcode > After layer change Gcode
```ini
SET_PRINT_STATS_INFO CURRENT_LAYER={layer_num + 1}
```
