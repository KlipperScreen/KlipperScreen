# Configuration

KlipperScreen has some configuration options which are outlined below. KlipperScreen will search for a configuration
file in the following order:
_${HOME}/KlipperScreen.conf_
_${KlipperScreen_Directory}/KlipperScreen.conf_

If one of those files are found, it will be used over the default configuration. The default configuration will be
merged with the custom configuration, so if you do not define any menus the default menus will be used.The default
config is included here: [ks_includes/KlipperScreen.conf](/ks_includes/KlipperScreen.conf)

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

# Allows the cursor to be displayed on the screen
show_cursor: False

#
# The following main options are deprecated and will be removed in the near future
#

# Define the moonraker host/port if different from 127.0.0.1 and 7125
moonraker_host: 127.0.0.1
moonraker_port: 7125
# Moonraker API key if this is not connecting from a trusted client IP
moonraker_api_key: False
```

## Printer Options
Multiple printers can be defined, currently only the first one will be used until an update in the near future.
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
```


## Preheat Options
```
[preheat my_temp_setting]
# Temperature for the heated bed
bed: 40
# Temperature for the tools
extruder: 195
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
Available panels are listed here: [docs/panels.md](panels.md)

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
