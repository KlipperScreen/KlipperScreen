# Configuration

In the KlipperScreen folder, a file _KlipperScreen.config_ allows for configuration of the screen. The configuration
file is a json formatted file. There are three main options to configure.
```
{
    "preheat_options",
    "mainmenu",
    "printmenu"
}
```

## Preheat Options
Under preheat options, you may specify pre-defined temperatures for easy warmup. Each material should be formatted as
follows:
```
"Material": {      
    "tool": 195,
    "bed": 40
}
```
Tool is the extruder temperature, bed is the heated bed temperature. An example configuration for PLA and abs would be
like this:
```
"preheat_options": {
    "PLA":  {
        "tool": 195,
        "bed":  40
    },
    "ABS":{
        "tool": 220,
        "bed": 90
    }
}
```

## Main menu
This allows a custom configuration for the menu displayed while the printer is idle. You can use sub-menus to group
different items and there are several panel options available. It is possible to have a gcode script run on a menu
button press.

Available panels:
* bed_level: Manual bed level
* extrude: Controls for extrusion
* fan: Controls fan speed
* finetune: Controls for fine-tuning print settings such as z-babystepping or extrustion rate
* menu: Allows for a sub-menu
* move: Controls the print head
* network: Network information panel
* preheat: Preheat bed/tools
* system: System information panel
* temperature: Controls temperature settings
* zcalibrate: Calibrating a probe

A menu item is configured as follows:
```
{
    "name": "Name displayed",
    "icon": "file name from icons folder",
    "panel": "panel from above options",
    # Optional parameters
    "items": [] # Items for a submenu
    "method": "printer.gcode.script" # Moonraker method for a request
    "params": {} # Parameters for the moonraker method
}
```

A sample configuration of a main menu would be as follows:
```
"mainmenu": [
    {
        "name": "Homing",
        "icon": "home",
        "panel": "menu",
        "items": [
            {
                "name": "Home All",
                "icon": "home",
                "method": "printer.gcode.script",
                "params": {"script": "G28"}
            },
            {
                "name": "Home X",
                "icon": "home-x",
                "method": "printer.gcode.script",
                "params": {"script": "G28 X"}
            },
            {
                "name": "Home Y",
                "icon": "home-y",
                "method": "printer.gcode.script",
                "params": {"script": "G28 Y"}
            },
            {
                "name": "Home Z",
                "icon": "home-z",
                "method": "printer.gcode.script",
                "params": {"script": "G28 Z"}
            }
        ]
    },
    {
        "name": "Preheat",
        "icon": "heat-up",
        "panel": "preheat"
    },
    {
        "name": "Actions" ,
        "icon": "actions",
        "panel": "menu",
        "items": [
            {
                "name": "Move",
                "icon": "move",
                "panel": "move"
            },
            {
                "name": "Extrude",
                "icon": "filament",
                "panel": "extrude"
            },
            {
                "name": "Fan",
                "icon": "fan",
                "panel": "fan"
            },
            {
                "name": "Temperature",
                "icon": "heat-up",
                "panel": "temperature"
            },
            {
                "name": "Disable Motors",
                "icon": "motor-off",
                "method": "printer.gcode.script",
                "params": {"script": "M18"},
            }
        ]
    },
    {
        "name": "Configuration",
        "icon": "control",
        "panel": "menu",
        "items": [
            {
                "name": "Bed Level",
                "icon": "bed-level",
                "panel": "bed_level"
            },
            {
                "name": "ZOffsets",
                "icon": "z-offset-increase",
                "panel": "zcalibrate"
            },
            {
                "name": "Network",
                "icon": "network",
                "panel": "network"
            },
            {
                "name": "System",
                "icon": "info",
                "panel": "system"
            }
        ]
    },
    {
        "name": "Print",
        "icon": "print",
        "panel": "print"
    }
]
```

## Print menu
The print menu controls items that are available during a print job. Certain panels, such as movement or homing, are
panels that shouldn't be displayed during a print as they could cause print errors. A default configuration is below:

```
"printmenu": [
    {
        "name": "Temperature",
        "icon": "heat-up",
        "panel": "temperature"
    },
    {
        "name": "Tuning",
        "icon": "fan",
        "panel": "finetune"
    },
    {
        "name": "Network",
        "icon": "network",
        "panel": "network"
    },
    {
        "name": "System",
        "icon": "info",
        "panel": "system"
    },
    {
        "name": "Extrude",
        "icon": "filament",
        "panel": "extrude"
    }
]
```
