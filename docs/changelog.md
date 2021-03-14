# Changelog

#### 2021 03 07
* Move fine tuning from control menu to job_status screen for easier access.

#### 2021 03 06
* Added ability to include configuration files.

#### 2021 03 05
* Multiple printers are now available in the main branch.

#### 2021 02 22
* Add configurable z_babystep intervals
* Add QUAD_GANTRY_LEVEL and Z_TILT_ADJUST to Homing menu
* Fixed cursor issue on startup
* Fixed font ratio for large, but short screens
* Configurable cursor display
* Re-vamped logging system

#### 2021 02 19
* Added support for heater generic

#### 2021 02 18
* Add directory support to print panel
* Add macros to print menu

#### 2021 02 17
* Fix issues with word wrapping in different languages

#### 2021 02 15
* Added action bar to left side (moves the Back, E-stop, and Home buttons)
* Added wifi manager. Will show current wifi details in network panel. Will allow switching networks in the future.
* Show printer name in main menu (user will need to configure the printer)

#### 2021 01 21
* Configure screen blanking from settings panel

#### 2021 01 21
* !! Important. matchbox-keyboard must be installed. Install script has changed to include this
* Added onscreen keyboard
* Can now add bed mesh profiles

#### 2021 01 20
* Add different time estimation methods to settings panel
* Job status panel will use time estimation method selected from settings panel
* Bugfixes to state tracking

#### 2021 01 10
* Added system reboot/shutdown buttons to systems panel.

#### 2021 01 09
* Better RTL support (most panels now properly support RTL)
* Fixes to install script for latest version of raspbian.

#### 2021 01 08
* Added settings panel. Invert axis and hiding macros can now be configured from within KlipperScreen

#### 2021 01 03
* Updated base language translation files with new phrases
* Allow translations from KlipperScreen.conf for
* Update menus for RTL languages
* Add fr_FR and he_IL language (courtesy of manu7irl)

#### 2020 12 21
* KlipperScreen doesn't have to be a trusted client. It can use the Moonraker API key
* Updates to job_status for multiple extruders. Will now show the current extruder.
* Updates to extrude panel to show multiple extruders and allow switching between them.

#### 2020 12 18
* Add gcode_macros panel

#### 2020 12 16
* Config file can now be specified when running from the command line
* Moonraker host/port can be specified in the configuration file

#### 2020 12 09
* Z value in job status now reflects the gcode Z value. This allows people with ABL to have a better understanding of Z

#### 2020 12 08
* Screen Width/Height are now definable in the configuration file
* Changed job page to allow for more information, display thumbnail of STL
* Job page will now say a job is complete and timeout to the main menu (time changeable from the config)
* Job page will now stay on the job page if there is an error.
* Restart option is available upon a completed/failed job

#### 2020 12 05
* Added ability to invert Z axis in move panel
* Fixed problem with metadata being retrieved constantly

#### 2020 12 04
* Removed fan options from fine tuning
* Add bed mesh panel
* Added more variables to the menu enable option
* Hide extrude panel during printing if the printer is not paused
* Add fan panel to print control menu
* Included screws_tilt_calculate gcode command into the bed level panel. This section must be configured in klipper.

#### 2020 12 02
* Change panel layout: Added Title, Back, Emergency Stop, and Home to panels.

#### 2020 11 28
* Add option for enable in menu for configuration. This can hide certain options
* Add Power panel to control power devices via moonraker
* Add klipper version to system panel

#### 2020 11 18
* Changed configuration file format.
* Moved default configuration file to an include folder.
* Added ability to do a confirm dialog from a menu item when running a script
* Added "Save Config" button to default configuration's Configuration menu.

#### 2020 11 14
* Update print panel to include line wrapping for longer filenames

#### 2020 11 13
* Fine Tuning Panel is now fully functional: Z BabyStepping, Fan Speed, Speed Factor, and Extrusion Factor
