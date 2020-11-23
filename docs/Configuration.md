# Configuration

In the KlipperScreen folder, a file _KlipperScreen.conf_ allows for configuration of the screen. This document will detail how to configure KlipperScreen. A default config is included here: [ks_includes/KlipperScreen.conf](ks_includes/KlipperScreen.conf)


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

Available panels are listed here: [docs/panels.md](panels.md)

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
