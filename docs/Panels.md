# Panels

### Main Menu
![Main Menu](img/panels/main_panel.png)

### Job Status
![Job Status](img/panels/job_status.png)

### Bed Level
type: bed_level

![Bed Level](img/panels/bed_level.png)

The bed level panel has the ability to have preset locations from Klipper. Please see documentation on the following
Klipper Sections:
* [bed_screws](https://www.klipper3d.org/Config_Reference.html#bed_screws)
* [screws_tilt_adjust](https://www.klipper3d.org/Config_Reference.html#screws_tilt_adjust)

_Important Note: Due to Klipper using the bltouch/probe offsets in screws_tilt_adjust, if a bltouch/probe is enabled_
_KlipperScreen will add the offset to the defined screw values. This will not occur if bed_screws section is used._

This panel will favor screws_tilt_adjust over the bed_screws section. If screws_tilt_adjust is defined, an extra button
for _Screws Calibrate_ will appear. This button runs the SCREWS_TILT_CALCULATE command and shows the results on the
panel.

### Bed Mesh
type: bed_mesh theme:material-dark

![Bed Mesh](img/panels/bed_mesh.png)

### Extrude
type: extrude theme:material-dark

![Extrude](img/panels/extrude.png)

### Fan
type: fan

![Fan](img/panels/fan.png)

### Fine Tune
type: fine_tune theme:custom

![Fine Tune Panel](img/panels/fine_tune.png)

### Gcode Macros
type: gcode_macros theme: material-darker

![Gcode Macros Panel](img/panels/gcode_macros.png)

### Menu
type: menu

![Menu Panel](img/panels/menu.png)

### Move
type: move

![Move Panel](img/panels/move.png)

### Network
type: network

![Network Panel](img/panels/network.png)

### Power
type: power

![Power](img/panels/power.png)

### Print
type: print

![Print Panel](img/panels/print.png)

### Settings
type: settings theme:colorized

![Settings](img/panels/settings.png)

### System
type: system

![System Panel](img/panels/system.png)

### Temperature
type: temperature theme:custom

![Temperature](img/panels/temperature.png)

### Z Calibrate
type: zcalibrate

![Z Calibrate](img/panels/zcalibrate.png)

### Limits
type: limits theme: material-dark

![Limits](img/panels/limits.png)
