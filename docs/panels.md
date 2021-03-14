# Panels

### Main Menu
![Main Menu](img/main_panel.png)

### Job Status
![Job Status](img/job_status.png)

### Bed Level
type: bed_level
![Bed Level](img/bed_level.png)

The bed level panel has the ability to have preset locations from Klipper. Please see documentation on the following
Klipper Sections:
* [bed_screws](https://github.com/KevinOConnor/klipper/blob/master/docs/Config_Reference.md#bed_screws)
* [screws_tilt_adjust](https://github.com/KevinOConnor/klipper/blob/master/docs/Config_Reference.md#screws_tilt_adjust)

_Important Note: Due to Klipper using the bltouch/probe offsets in screws_tilt_adjust, if a bltouch/probe is enabled_
_KlipperScreen will add the offset to the defined screw values. This will not occur if bed_screws section is used._

This panel will favor screws_tilt_adjust over the bed_screws section. If screws_tilt_adjust is defined, an extra button
for _Screws Calibrate_ will appear. This button runs the SCREWS_TILT_CALCULATE command and shows the results on the
panel.

### Bed Mesh
type: bed_mesh
![Bed Mesh](img/bed_mesh.png)

### Extrude
type: extrude
![Extrude](img/extrude.png)

### Fan
type: fan
![Fan](img/fan.png)

### Fine Tune
type: fine_tune
![Fine Tune Panel](img/fine_tune.png)

### Gcode Macros
type: gcode_macros
![Gcode Macros Panel](img/gcode_macros.png)

### Menu
type: menu
![Menu Panel](img/menu.png)

### Move
type: move
![Move Panel](img/move.png)

### Network
type: network
![Network Panel](img/network.png)

### Power
type: power
![Power](img/power.png)

### Preheat
type: preheat
![Preheat Panel](img/preheat.png)

### Print
type: print
![Print Panel](img/print.png)

### Settings
type: settings
![Settings](img/settings.png)

### System
type: system
![System Panel](img/system.png)

### Temperature
type: temperature
![Temperature](img/temperature.png)

### Z Calibrate
type: zcalibrate
![Z Calibrate](img/zcalibrate.png)
