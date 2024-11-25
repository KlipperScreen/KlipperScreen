# Configuration

Usually you don't need to create a configuration file, but if you need to change something that is not changeable in the UI
create a blank file in `~/printer_data/config/KlipperScreen.conf`, if the file already exist then just edit it.

Write in the file only the options that need to be changed, and restart KlipperScreen.


!!! failure "Critical"
    Each configuration option should be on a newline, as they are presented here.

    The line endings should be of UNIX style (LF).


## Main Options
The options listed here are not editable from within the user interface.
```{ .ini .no-copy }
[main]

# Time in seconds before the Job Status page closes itself after a successful job/print
# 0 means disabled
# job_complete_timeout: 0

# Time in seconds before the Job Status closes itself if an error is encountered
# job_error_timeout: 0

# If multiple printers are defined, this can be set the name of the one to show at startup.
# default_printer: MyPrinter

# To define a full set of custom menus (instead of merging user entries with default entries)
# set this to False. See Menu section below.
# use_default_menu: True

# Define one or more moonraker power devices that turn on/off with the screensaver (CSV list)
# screen_on_devices: example1, example2
# screen_off_devices:  example1, example2

# Define the password to use when locking the screen, this is not secure
# it's saved as plain text, it's meant to be a deterrent for kids or people at shows
# it will be redacted from the logs.
# default is no password
# lock_password: example_password
```

!!! tip
    It is strongly recommended that you do not add settings to the config file if you don't need them

## Printer Options
Multiple printers can be defined
```{ .ini .no-copy }
# Define printer and name. Name is anything after the first printer word
[printer MyPrinter]
# Define the moonraker host/port if different from 127.0.0.1 and 7125
moonraker_host: 127.0.0.1
moonraker_port: 7125
# Use HTTPS/WSS. Defaults to True for ports 443 or 7130, False for any other port
# moonraker_ssl: False
# If you're using the route_prefix option in your moonraker config, specify it here.
# This can be useful for running multiple printers behind a path-based reverse proxy.
# Most installs will not need this. 
# moonraker_path: printer1
# Moonraker API key if this host is not connecting from a trusted client IP
# moonraker_api_key: False

# Define the z_babystep intervals in a CSV list. Currently only 2 are supported, the last value is default
# z_babystep_values: 0.01, 0.05

# For the 'Power on' button on the splash screen:
# Define one or more moonraker power devices that turn on this printer (CSV list)
# By Default it tries to match the printer name defined in this section header to the moonraker power device name.
# power_devices: example1, example2

# Define what items should be shown in titlebar besides the extruder and bed
# the name must be the same as defined in the klipper config
# valid options are temperature_sensors or temperature_fans, or heater_generic
# titlebar_items: chamber, MCU, Pi

# The style of the user defined items in the titlebar
# Can be 'full' indicating that the full name is shown, 'short' for the first letter, or None (default) for no name
# titlebar_name_type: None

# Z probe calibrate position
# By default it tries to guess the correct location
# it will try using zero reference position, safe_z, mesh midddle, middle of axis length, etc
# example:
# calibrate_x_position: 100
# calibrate_y_position: 100

# Custom commands for zcalibrate
# the zcalibrate panel provides quick access to test_z, accept and cancel commands
# zcalibrate_custom_commands: CUSTOM_CALIBRATE, CUSTOM_CALIBRATE method=manual, CUSTOM_TEST

# Rotation is useful if the screen is not directly in front of the machine.
# It will affect the bed mesh visualization.
# Valid values are 0 90 180 270
# screw_rotation: 0

# Define distances and speeds for the extrude panel. CSV list 2 to 4 integers the second value is default
# extrude_distances: 5, 10, 15, 25
# extrude_speeds: 1, 2, 5, 25

# Define distances for the move panel. comma-separated list with 2 to 7 floats and/or integers
# move_distances: 0.1, 0.5, 1, 5, 10, 25, 50

# Camera needs to be configured in moonraker:
# https://moonraker.readthedocs.io/en/latest/configuration/#webcam
```

## Preheat Options

!!! question "Added one the others disappeared, Is this normal?"
    Adding a custom preheat section will cause the defaults to not load, this is
    the intended behaviour.

```ini
[preheat my_temp_setting]
extruder: 195
extruder1: 60
heater_bed: 40
# Use the name
chamber: 60
# or the full name
heater_generic chamber: 60
# or for example apply the same temp to devices of the same type
temperature_fan: 40
heater_generic: 60
# optional GCode to run when the option is selected
gcode: MY_HEATSOAK_MACRO
```

There is a special preheat setting named cooldown to *do additional things* when the _cooldown_ button is pressed
*do not* add `TURN_OFF_ALL_HEATERS` or you will remove the ability to turn off individual heaters with this button.
for example:

```ini
[preheat cooldown]
gcode: M107
```

## Include files
```{ .ini .no-copy }
# [include conf.d/*.conf]
# Include another configuration file. Wildcards (*) will expand to match anything.
```

## Menu
This allows a custom configuration for the menu displayed while the printer is idle. You can use sub-menus to group
different items and there are several panel options available. It is possible to have a gcode script run on a menu
button press. There are two menus available in KlipperScreen, __main and __print. The __main menu is displayed while the
printer is idle. The __print menu is accessible from the printing status page.

!!! info
    A predefined set of menus is already provided

A menu item is configured as follows:
```{ .ini .no-copy }
[menu __main my_menu_item]
name: Item Name
#   To build a sub-menu of this menu item, you would next define [menu __main my_menu_item sub_menu_item]
#
#   --- The following items are optional ---
#
# icon: home
#   Icon name to be used, it can be any image in the directory:
#   KlipperScreen/styles/{theme}/images/ where {theme} is your current theme
#   Supported formats svg or png
#
# style: mycolor4
#   Icon style, defined as "button.mycolor4" (for example) in the theme css
#
# panel: preheat
#   Panel from the panels folder in the KlipperScreen folder
#
# enable: {{ 'screws_tilt_adjust' in printer.config_sections and printer.power_devices.count > 0 }}
#   Enable allows hiding of a menu if the condition is false. (evaluated with Jinja2)
#   Available variables are listed in the next section.
#
#   --- The items below do not work if you define a panel to be loaded ---
#
# method: printer.gcode.script
#   Moonraker method to call when the item is selected, you will need params below
#   the most common is is printer.gcode.script check out other methods in moonraker documentation:
#   https://moonraker.readthedocs.io/en/latest/web_api/#run-a-gcode
#
# params: {"script":"G28 X"}
#   Parameters that would be passed with the method above
#
# confirm: 'Are you sure?'
#   If present this option will give you a confirmation prompt with the text above.
#   It's recommended that you use a Macro-prompt instead of this option,
#   as the Macro-prompt will also be shown on other interfaces, and it's more flexible.
#   Macro-prompts are described in: https://klipperscreen.github.io/KlipperScreen/macros/#prompts
```


Variables to conditionally test the enable statement:
```{ .yaml .no-copy }
# Configured in Moonraker
moonraker.power_devices.count # Number of power devices
moonraker.cameras.count # Number of cameras
moonraker.spoolman # Has spoolman

# Printer specific
printer.pause_resume.is_paused # Printing job is paused
printer.extruders.count # Number of extruders
printer.temperature_devices.count # Number of temperature related devices (not extruders)
printer.fans.count # Number of fans
printer.output_pins.count # Number of pins configured
printer.gcode_macros.count # Number of gcode macros
printer.gcode_macros.list # List of names of the gcode macros
printer.leds.count # Number of leds
printer.config_sections # Array of section headers of Klipper config (printer.cfg)
printer.available_commands # List of all the commands that the printer supports
```


A sample configuration of a main menu would be as follows:
```{ .yaml+jinja .no-copy }
[menu __main homing]
name: Homing
icon: home

[menu __main homing homeall]
name: Home All
icon: home
method: printer.gcode.script
params: {"script":"G28"}

[menu __main homing mymacro]
name: My Macro
icon: home
method: printer.gcode.script
params: {"script":"MY_MACRO"}
enable: {{ 'MY_MACRO' in printer.gcode_macros.list }}

[menu __main preheat]
name: Preheat
icon: heat-up
panel: preheat
```

## KlipperScreen behaviour towards configuration

KlipperScreen will search for a configuration file in the following order:

1. _~/printer_data/config/KlipperScreen.conf_
2. _~/.config/KlipperScreen/KlipperScreen.conf_
3. _${KlipperScreen_Directory}/KlipperScreen.conf_

If you need a custom location for the configuration file, you can add [launch argument](#adding-launch-arguments)

If one of those files are found, it will be merged with the default configuration.
Default Preheat options will be discarded if a custom preheat is found.
If include files are defined then, they will be merged first.

The default config is included here: (do not edit use as reference)
_${KlipperScreen_Directory}/config/defaults.conf_

*Do not* copy the entire default.conf file, just configure the settings needed.

If no config file is found, then when a setting is changed in the settings panel, a new configuration file should be created automatically.

## Starting on a different monitor/display/screen

Add -m or --monitor as a launch argument, to specify the number of the monitor, that will show Klipperscreen (default: 0).

!!! warning
    Selecting the monitor is only allowed when KlipperScreen is set to launch fullscreen in standalone mode (no DE)


## Adding launch arguments

The recommended way to add launch arguments is:

1. Create a launch script:
    ```bash
    touch ~/KlipperScreen/scripts/launch_KlipperScreen.sh
    chmod +x launch_KlipperScreen.sh
    ```
2. Edit the script:
    ```bash
    nano ~/KlipperScreen/scripts/launch_KlipperScreen.sh
    ```
    Add the init and the launch argument, this example will launch KlipperScreen on the second monitor if exists:
    ```
    /usr/bin/xinit $KS_XCLIENT --monitor 1
    ```

    !!! tip
        you can use --configfile and --logfile to specify custom locations for those files
