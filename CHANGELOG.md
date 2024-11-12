# Changelog
This just tracks the most notable changes, if you want all the details checkout the commit history.
Probably all versions contain changes regarding documentation, translation, fixes and other minor refactors

## v0.4.5-*

* menu buttons can have an 'active' status to change their appearance
* basic lockscreen for shows or kids

## v0.4.5  (Oct 28, 2024)

* allow calling KlipperScreen panels from gcode
* bed_mesh: automatically call for z_tilt or quad_level if not applied
* show battery status in the topbar
* macros: keyboard to keypad input switch with auto pre-selection

## v0.4.4  (Sep 16, 2024)
* support for different moonraker routes
* allow showing/hiding cursor from the settings
* some wpa-eap support, adds the security type selector and user field
* extrude: wait for temp or open temp panel automatically close #1416
* extrude: show more filament sensors (up to 9)
* notifications: change icon if warnings were issued
* notifications: add clear close #1178
* notifications: klipper config warnings

## v0.4.3  (Jun 29, 2024)
* prompts: add regular buttons and groups
* refactor: always ignore and hide console temp responses
* gcodes: vertical: remove left icons if low resolution
* keypad: support floating point temp
* gcodes: add extra info to confirm print
* zcalibrate: add a dropdown with the function name to select
* job_status: auto-estimated time: use last print time if available
* gcodes: add option to delete in the confirmation

## v0.4.2  (Jun 10, 2024)
* job_status: remove the status message and use the titlebar for that
* shutdown: add restart ks
* extrude: move firmware retraction into the panel, add pressure advance control closes #724
* screen: theme doesn't need a restart anymore
* splash: show the message when klipper is shutdown
* rename print panel to gcodes
* job_status: add extra info to print list and dialog
* network: new NetworkManager backend using sdbus (#1269)
* drop python 3.7 support (#1271)

## v0.4.1  (May 24, 2024)
* vertical layout: increase font size
* main_menu and temp: change layout to accomodate a bigger graph and list in vertical mode
* pins: add pwm_tool
* menu: add pins panel access while printing
* move and zcalibrate: changes in z invert
* system: add cpu and memory usage tracking
* add system info panel
* updater: add distro name
* menu: rename system to update
* allow 2 different screen timeouts, one while printing the other if not
* settings: Add tooltips
* printer_select: support custom icons #1240
* bed_mesh: show round bed without padded values
* macros: send gcode style (G/M) macros without =
* bed_mesh: bedmap draw axis
* zcalibrate: add support for axis twist compensation
* zcalibrate: add confirmation for abort close #1326

## v0.4.0  (Apr 14, 2024)
* move: support rescaling the slider if machine limits are changed
* bed_mesh: add support for rotation and inversion to the meshMap
* bed_level: add a warning for the screws not being used
* heatergraph: add the ability to go fullscreen when clicked close #740
* Add an alternative to X close #1289 (#1306) (Wayland)
* limits: change to minimum cruise ratio
* heatergraph: add power representation (if set to show power in settings)
* base_panel: titlebar: turn red if high cpu or memory is in use, show usage
* create the shutdown panel, add it to the action bar, remove items from system panel
* job_status: show current offset when saving to endstop close #1286

## v0.3.9  (Feb 29, 2024)
* print panel refactor and new features (#1270)
    Adds a grid/thumbnail mode (switchable to the list mode)
    last mode used is saved
    faster load and less memory usage
    add sort by size

* extrude: add an extruder selector for machines with more than 5 extruders (#1249)
* pins: make the non pwm pins on-off pwm pins as a scale
* popups: rate limit to every second close #1225
* feat: macro prompts close #1216 (#1219)

## v0.3.8  (Dec 23, 2023)
* add move_distances config option (#1211)
* printer_select: do not sort, this allows the users to sort how they want by defining them in the config in the order they want

## v0.3.7  (Nov 24, 2023)
* wifi: add icons
* initial notifications panel
* add moonraker warnings

## v0.3.6  (Sep 24, 2023)
* LED light control, close #991 (#1106)
* pause will auto-open extrude
* macros: hide the panel if there are no elegible macros
* job_status: click thumbnail for fullscreen thumbnail

## v0.3.5  (Aug 21, 2023)
* camera: relative url support close #1086 (#1088)
* Spoolman support close #1060
* Use callbacks to disable and enable buttons to improve user feedback
* main_menu: allow closing the keypad with the back button
* camera: add support for moonraker cameras, deprecates camera_url

## v0.3.4  (Jul 30, 2023)
* fine_tune: split speed and flow selectors close #935
* job_status: show save to endstop to apply offset for deltas close #916
* job_status: change progress percentage to time-based instead of file-based

## v0.3.3  (Jul 2, 2023)
* Menu reorganization (#1029)
* temp: add pid calibrate to the keypad (#1026)
* bed_level: add center screw close #863

## v0.3.2  (Feb 20, 2023)
* add ability to style and template menu buttons (#866)
* Update on-screen keyboard (#874)

## v0.3.1  (Dec 11, 2022)
* feat: camera support, using mpv as backend
* resizability
* print: add move/rename, make delete a visible button close #636

## v0.3.0  (Dec 5, 2022)
* feat: turn on_off power devices with the screensaver close #518
* macros add parameters
* print: allow directory deletion
* job_status: add eta
* Added support for network manager
* settings: add extra large font close #798

## v0.2.9  (Nov 18, 2022)
* job_status: use the new print_stats layer info
* functions: logging: use printer_data
* keyboard: add spanish and german, change backscpace, clear and accept to icons

## v0.2.8  (Oct 27, 2022)
* config: add printer_data to default config search locations
* extrude: make the speed and distance configurable close #673
* limits and retraction: infinite sliders
* print: hide files and directories starting with .

## v0.2.7  (Oct 4, 2022)
* exclude: graph (#743)
* Add current heater power % to job status (#708)

## v0.2.6  (Sep 2, 2022)
* Change URL protocol to HTTPS and WSS when connecting to port 443
* main temp: add the ability to hide the graph
* system: add shutdown and restart host
* exclude: add exclude objects support

## v0.2.5  (Aug 1, 2022)
* system: Add check for updates close #681
* bed_level: support 3 screws close #606
* job_status: now works without extruders or fans
* print: add delete file
* screen: Always ask to save config if we detect it on responses
* output_pin panel close #546
* built-in keyboard

## v0.2.4  (Jul 3, 2022)
* Enable users to inject a custom script to start KlipperScreen (#660)
* basic support for extruder_stepper
* fan: add max and stop buttons

## v0.2.3  (May 31, 2022)
* job_status: ask for confirmation, and show saved offset
* extrude: add filament sensor support
* limits: add reset, allow to set above the configured maximum but turn the slider red
* job_status: animate filename if it's too long
* macros: allow reverse sorting
* Add Input Shaper panel
* zcalibrate: show the saved offset and offset to be saved
* Allow setting 0 in preheat options (#612)

## v0.2.2  (May 1, 2022)
* Improve Job status (#592)

    Adds heater_generic and/or temp_sensors besides extruder/bed (because of the limited space maybe only 1)

    Temps are now buttons and act as a shortcut to the temp panel

    Adds fan_generic to the fan label and it's now a shortcut to the fan panel

    The colors and size of the progress circle were changed to be more subtle.

    Margins between items were augmented, because they are buttons now

    Adds 3 information pages: move, extrusion and time:
    * move can be opened with speed or z buttons
    * time with elapsed/remaining buttons
    * extrusion with the extrude_factor / flowrate button

* limits: add units
* Add firmware retraction panel close #101
* Add possibility to define custom code for cooling (#579)
* job_status: add save z button to save babystepping
* console: hide temps, clear button, button icons

## v0.2.1  (Apr 1, 2022)
* Vertical mode (#480)
* Use extruder icon without number if there is only 1
* Screensaver if dpms is off
* fine_tune: add reset button, do not set babystepping prior to homing, reorganize a bit
* menu and printer_select: support more than 8 items
* zcalibrate: add selector for the different modes zcalibrate supports
* system: feature: add Full Update
* Added option to select default printer at startup. (#542)
* Show fan speed according to max_power and off_below (#543)
* console: add switch to turn off autoscroll (#540)
* base_panel: allow titlebar items to be configured
* splash_screen: allow power_devices to be configured
* Bed_level: Support 6 and 8 Screws and rotation (#484)
* Show position including offsets in the move panel (#516)
* Start in configurations without fans or extruders or temp devices
* Extrude panel: Support 5 extruders (#441)
* Support hiding by name using underscore (#437)
* Support Manual Mesh calibration (#388)
* Support the "enter" key from a physical keyboard (#379)
* Support multiple power devices. (#350)
* add speed as parameter to UN/LOAD_FILAMENT macro (#359)

## v0.2.0  (Dec 7, 2021)
The Project changed maintainer [alfrix](github.com/alfrix)
(Thats the reason for the version jump)

* Temp graph (#357)
* Create keypad widget and include set temp on the main menu
* Switch from vext.gi to PyGObject (#348)
* Add the full message of the commits in the updater (#343)
* Wakeup touch block (#340)
* screen: RESPOND echo will now show a message on the screen.
* Zcal panel: Support for Z_ENDSTOP_CALIBRATE (#327)
* Move panel: Add Z-tilt/Quad-gantry-level/HomeXY button (#326)
* Add temperature_fan to heaters (#325)
* Configurable xy position for z-calibrate (#310)
* Material themes (#297)
* Support custom themes (#288)
* Allow gcode commands with preheat options (#274)
* Add printer limits panel
* Add unload/load and reorganize extrude panel (#250)
* Font Size Selector (#245)
* Wake the screen at print start and end (#229)
* system: Add restart option to services that moonraker supports
* base_panel: Add extruder/heater bed temperatures to the title bar

## v0.1.6  (May 13, 2021)
* Wifi manager: Updates to include ability to change wifi networks

## v0.1.5  (May 10, 2021)
* New Style - Solarized (#144)
* M117 messages display (#150)
* print: Include refresh button for files
* bed_mesh: Include ability to view mesh Added ability to visualize bed meshes. The active bed mesh will have more points available to view than inactive bed meshes.
* Multiple printers (#85)
* screen: Enable DPMS so screens can power down.
* screen: Allow cursor to be displayed #51
* temperature: add heater_generic
* screen: Only process current panel's subscription

## v0.1.4  (Feb 15, 2021)
* network: Show wifi information
* screen_panel: Put icons on a sidebar instead of on the header
* printer: Include quad_gantry_level
* wifi: Initial wifi class
* job_status/settings: Allow different file estimation methods
* print: Allow sorting by date and name.

## v0.1.3  (Jan 7, 2021)
* gcode_macros: Update to hide macros based on settings
* settings: Create settings panel for KlipperScreen settings
* job_status: updates to show active extruder
* KlippyWebsocket: changes to allow for moonraker api key
* gcode_macros: add a panel for gcode macros
* screen: allow custom moonraker url/port
* config: Allow specifying configfile location from command line
* UI scaling (#28)
* move: Allow inverting of the axis
* bed_level: include screws_tilt_calculate command
* fine_tune: Remove fan from fine tune panel. Add fan to print menu
* configuration: hide extrude while printing
* bed_mesh: Add panel for bed_mesh
* screen: add popup message capability

## v0.1.2  (Dec 2, 2020)
* Change panel layout. Add title and move back button
* system: add klipper version

## v0.1.1  (Nov 28, 2020)
* Add power panel
* menu: add ability to hide certain menus
* Dynamically load panels
* Add HOME XY button
* Highlight all heaters by default on preheat panel

## v0.1.0  (Nov 14, 2020)
* first release

## v0.0.0  (Jul 6, 2020)
* first commit
