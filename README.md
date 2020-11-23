# KlipperScreen
KlipperScreen is an idea based from [OctoScreen](https://github.com/Z-Bolt/OctoScreen/), but instead of needing OctoPrint or to compile go, KlipperScreen is python based and interacts directly with Moonraker, Klipper's API service, so that it can be run with no dependencies besides Klipper.

Current feature list:
 - [x] Homing
 - [x] Preheating
 - [x] Job Status and control
 - [x] Temperature control
 - [x] Extrude control
 - [x] Fan control
 - [x] Disable steppers
 - [x] Configure Z Offset using PROBE_CALIBRATE
 - [x] Print tuning (Z Babystepping, Speed Control, Flow Control)
 - [x] Manual bed leveling assist
 - [x] Using thumbnails from prusa on job status page
 - [ ] Better system panel
 - [ ] Wifi selection
 - [ ] Scale UI based off of resolution


More details to come...

### Required Hardware
KlipperScreen should run on any HDMI touchscreen that you can connect to a computer. The required video driver may
be slightly different depending on what model you get. I am developing on a 1024x600 resolution screen. Due to this,
other resolutions may not be scaled properly at this moment. UI scaling is a future development item.

### Links
[Installation](docs/Installation.md)
[Configuration](docs/Configuration.md)
