# Zcalibrate
This panel supports various modes of operation to assist in the calibration of the Z axis of the machine.
It's strongly suggested to read Klipper documentation about [Bed level](https://www.klipper3d.org/Bed_Level.html)

![Screenshot](../img/panels/zcalibrate.png)


## Buttons
* "Start" will initiate the only method available, or ask the user if multiple methods are available.
!!! note
    KlipperScreen will automatically Home(`G28`) if needed
* The raise(+) and lower(-) buttons send `TESTZ Z=distance` where distance is selected in the bottom row.
* Accept will send `ACCEPT`
* Abort will send `ABORT`


## Calibration methods

### Probe (`PROBE_CALIBRATE`)
Available when a probe is defined. (BL-Touch is a probe)

KlipperScreen will try to position the probe in the correct place before sendind a `PROBE_CALIBRATE`

??? info "Search order to select location"

    1. `calibrate_x_position` and `calibrate_y_position` in [KlipperScreen.conf](https://klipperscreen.readthedocs.io/en/latest/Configuration/#printer-options)
    Both need to be configured, probe offsets are not applied. This is considered an override
    2. Probe at the [zero reference position of the mesh](https://www.klipper3d.org/Bed_Mesh.html#configuring-the-zero-reference-position)
    3. If `[safe_z_home]` is defined, those values are used. Unless `Z_ENDSTOP_CALIBRATE` is available.
    In other words, only use `[safe_z_home]` if `z_virtual_endstop` is used
    4. If the kinematics are `delta` probe is placed at 0, 0
    5. Probe at the center of the `bed_mesh`
    6. Probe at the center of the axes (`position_max` / 2)


Klipper documentation: [Calibrating probe Z offset](https://www.klipper3d.org/Probe_Calibrate.html#calibrating-probe-z-offset)

### Endstop (`Z_ENDSTOP_CALIBRATE`)
Available when a physical endstop is defined for `[stepper_z]`

Klipper documentation: [Calibrating a Z endstop](https://www.klipper3d.org/Manual_Level.html#calibrating-a-z-endstop)

### Bed mesh (`BED_MESH_CALIBRATE`)
Available when a probe is not defined and `[bed_mesh]` is defined

this mode lets you create a mesh leveling bed using the paper test in various points.

!!! warning
    DO NOT adjust the bed screws while using this mode.

    Adjust the screws using the [bed screws](Screws.md) panel before running this tool.

### Delta Automatic/Manual (`DELTA_CALIBRATE`)
Available when the kinematics are defined as delta.

Klipper documentation: [Delta calibration](https://www.klipper3d.org/Delta_Calibrate.html)

### Axis Twist Compensation (`AXIS_TWIST_COMPENSATION_CALIBRATE`)
Available when `[axis_twist_compensation]` is defined in the Klipper configuration.

Klipper documentation: [Axis Twist Compensation](https://www.klipper3d.org/Axis_Twist_Compensation.html)
