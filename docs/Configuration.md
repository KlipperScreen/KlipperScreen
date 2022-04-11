# Configuration

Usually you don't need to create a configuration file, but if you need to change something that is not changeable in the UI
create a blank file in `~/klipper_config/KlipperScreen.conf`, if the file already exist then just edit it.

Write in the file only the options that need to be changed, and restart KlipperScreen.

## Include files
```
[include conf.d/*.conf]
# Include another configuration file. Wildcards (*) will expand to match anything.
```


## Main Options
```
[main]
# Invert axis in move panel. Default is False. Change to true to invert
invert_x: False
invert_y: False
invert_z: False

# Time (seconds) before the Job Status page reverts to main menu after a successful job
job_complete_timeout: 30

# Time (seconds) before the Job Status page reverts to main menu after a successful job.
#   If this option is 0, the user must click on a button to go back to the main menu.
job_error_timeout: 0

# Specify the language
#   The language can be specified here instead of using the system default language.
language: en

# Allows the cursor to be displayed on the screen
show_cursor: False

# Allows to define custom systemctl command for restart like xrdp
service: KlipperScreen

# If multiple printers are defined, this can be set the name of the one to show at startup.
default_printer: Ender 3 Pro

# To define a full set of custom menues (instead of merging user entries with default entries)
# set this to False. See Menu section below.
use_default_menu: True

```

## Printer Options
Multiple printers can be defined
```
# Define printer and name. Name is anything after the first printer word
[printer Ender 3 Pro]
# Define the moonraker host/port if different from 127.0.0.1 and 7125
moonraker_host: 127.0.0.1
moonraker_port: 7125
# Moonraker API key if this is not connecting from a trusted client IP
moonraker_api_key: False

# Define the z_babystep intervals in a CSV list. Currently only 2 are supported
z_babystep_values: 0.01, 0.05

# Override the movement speed and set a specific for this printer.
# These setting overrides the settings configured in the UI. If specified,
# the values configured in the UI will not be used.
move_speed_xy: 500
move_speed_z: 300

# Define one or more moonraker power devices that turn on this printer (CSV list)
# Default is the printer name
power_devices: example1, example2

# Define what items should be shown in titlebar besides the extruder and bed
# the name must be the same as defined in the klipper config
# valid options are temperature_sensors or temperature_fans, or heater_generic
titlebar_items: chamber, MCU, Pi

# The style of the user defined items in the titlebar
# Can be 'full' indicating that the full name is shown, 'short' for the first letter, or None (default) for no name
titlebar_name_type: None

# Z probe calibrate position
# By default is the middle of the bed
calibrate_x_position: 100
calibrate_y_position: 100

# Screen DPMS
# By default DPMS is used to turn off the screen, this should prevent burn-in and save power.
# However if you find that your screen doesn't turn off because it doesn't support it
# Setting this to false will just turn the screen black.
use_dpms: True
```

## Preheat Options
```
[preheat my_temp_setting]
# Temperature for the heated bed
bed: 40
# Temperature for the tools
extruder: 195
# Temperature for generic heaters
heater_generic: 40
# Temperature controlled fans (temperature_fan in klipper config)
temperature_fan: 40
# optional GCode to run when the option is selected
gcode: MY_HEATSOAK_MACRO
```

There is an special preheat setting named cooldown to do additional things when the _cooldown_ button is pressed
for example:

```
[preheat cooldown]
gcode: M107
```

## Bed Screws
```
[bed_screws]
# Rotation is useful if the screen is not directly in front of the machine.
# Valid values are 0 90 180 270
rotation: 0
```

## Menu
This allows a custom configuration for the menu displayed while the printer is idle. You can use sub-menus to group
different items and there are several panel options available. It is possible to have a gcode script run on a menu
button press. There are two menus available in KlipperScreen, __main and __print. The __main menu is displayed while the
printer is idle. The __print menu is accessible from the printing status page.

A menu item is configured as follows:
```
[menu __main my_menu_item]
# To build a sub-menu of this menu item, you would next use [menu __main my_menu_item sub_menu_item]
name: Item Name
icon: home
# Optional Parameters
# Panel from the panels listed below
panel: preheat
# Moonraker method to call when the item is selected
method: printer.gcode.script
# Parameters that would be passed with the method above
params: {"script":"G28 X"}
# Enable allows hiding of a menu if the condition is false. This statement is evaluated in Jinja2
#   Available variables are listed below.
enable: {{ printer.power_devices.count > 0 }}
```
Available panels are listed here: [docs/panels.md](Panels.md)

Certain variables are available for conditional testing of the enable statement:
```
printer.bltouch # Available if bltouch section defined in config
printer.gcode_macros.count # Number of gcode macros
printer.idle_timeout # Idle timeout section
printer.pause_resume # Pause resume section of Klipper
printer.probe # Available if probe section defined in config
printer.power_devices.count # Number of power devices configured in Moonraker
```


A sample configuration of a main menu would be as follows:
```
[menu __main homing]
name: Homing
icon: home

[menu __main preheat]
name: Preheat
icon: heat-up
panel: preheat

[menu __main print]
name: Print
icon: print
panel: print

[menu __main homing homeall]
name: Home All
icon: home
method: printer.gcode.script
params: {"script":"G28"}
```

## KlipperScreen behaviour towards configuration

KlipperScreen will search for a configuration file in the following order:

1. _~/KlipperScreen.conf_
2. _${KlipperScreen_Directory}/KlipperScreen.conf_
3. _~/klipper_config/KlipperScreen.conf_

If you need a custom location for the configuration file, you can add -c or --configfile to the systemd file and specify
the location of your configuration file.

If one of those files are found, it will be merged with the default configuration.
Default Preheat options will be discarded if a custom preheat is found.
If include files are defined then, they will be merged first.

The default config is included here: (do not edit use as reference)
_${KlipperScreen_Directory}/ks_includes/default.conf_

Preferably *do not* copy the entire default.conf file, just configure the settings needed.

If no config file is found, then when a setting is changed in the settings panel, a new configuration file will be created automatically.
