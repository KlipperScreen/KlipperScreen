# Panels

### Main Menu
![Main Menu](img/panels/main_panel.png)

### Job Status
```py
panel: job_status
```
![Job Status](img/panels/job_status.png)

### Bed Level
```py
panel: bed_level
```
![Bed Level](img/panels/bed_level.png)

The bed level panel has the ability to have preset locations from Klipper. Please see documentation on the following
Klipper Sections:
* [bed_screws](https://www.klipper3d.org/Config_Reference.html#bed_screws)
* [screws_tilt_adjust](https://www.klipper3d.org/Config_Reference.html#screws_tilt_adjust)

!!! important:
    `[bed_screws]` uses Nozzle positions and `[screws_tilt_adjust]` uses Probe positions

This panel will favor `[bed_screws]` but if it's not defined,
the probe offset will be applied to the defined screw values in `[screws_tilt_adjust]`,
this way the position buttons behave like if `[bed_screws]` was defined.

### Bed Mesh
```py
panel: bed_mesh
```
![Bed Mesh](img/panels/bed_mesh.png)

### Extrude
```py
panel: extrude theme:material-dark
```
![Extrude](img/panels/extrude.png)

### Fan
```py
panel: fan
```
![Fan](img/panels/fan.png)

### Fine Tune
```py
panel: fine_tune
```
![Fine Tune Panel](img/panels/fine_tune.png)

### Gcode Macros
```py
panel: gcode_macros
```
![Gcode Macros Panel](img/panels/gcode_macros.png)

### Menu
![Menu Panel](img/panels/menu.png)

### Move
```py
panel: move
```
![Move Panel](img/panels/move.png)

### Network
```py
panel: network
```
![Network Panel](img/panels/network.png)

### Power
```py
panel: power
```
![Power](img/panels/power.png)

### Print
```py
panel: print
```
![Print Panel](img/panels/print.png)

### Settings
```py
panel: settings
```
![Settings](img/panels/settings.png)

### System
```py
panel: system
```
![System Panel](img/panels/system.png)

### Temperature
```py
panel: temperature
```
![Temperature](img/panels/temperature.png)

### Z Calibrate
```py
panel: zcalibrate
```
![Z Calibrate](img/panels/zcalibrate.png)

### Limits
```py
panel: limits
```
![Limits](img/panels/limits.png)

### Retraction
```py
panel: retraction
```
![Limits](img/panels/retraction.png)

### Input Shapers
```py
panel: input_shaper
```
![Limits](img/panels/input_shaper.png)
