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
KlipperScreen should run on any HDMI touchscreen that you can connect to a raspberry pi. The required video driver may
be slightly different depending on what model you get. I am developing on a 1024x600 resolution screen. Due to this,
other resolutions may not be scaled properly at this moment. UI scaling is a future development item.

#### Configure Hardware

Add the following to _/boot/config.txt_. You can alter the hdmi_cvt to your screen specifications. This example is setup
for a resolution of 1024x600 and a refresh rate of 60hz.
```
hdmi_cvt=1024 600 60 6 0 0 0
hdmi_group=2
hdmi_mode=87
hdmi_drive=2
```
* Development has been using 1024x600 for a screen resolution. Other resolutions may have issues currently

After changing _/boot/config.txt_ you must reboot your raspberry pi. Please also ensure you followed setting up your screen via the screen instructions. This will likely have a xorg.conf.d file for input from the touchscreen that you need to create.

### Installation

Follow the instructions to install klipper and moonraker.
klipper: https://github.com/KevinOConnor/klipper/
moonraker: https://github.com/Arksine/moonraker

Ensure that 127.0.0.1 is a trusted client for moonraker, such as in this example:
```
[authorization]
trusted_clients:
  127.0.0.1
```

For moonraker, ensure that 127.0.0.1 is a trusted client:

Run _scripts/KlipperScreen-install.sh_
This script will install packages that are listed under manual install, create a
python virtual environment at ${HOME}/.KlipperScreen-env and install a systemd
service file.

As an option to do development or interact with KlipperScreen from your computer, you may install tigervnc-scraping-server and VNC to your pi instance. Follow tigervnc server setup procedures for details on how to do that.
