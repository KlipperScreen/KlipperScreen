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
 - [ ] Print tuning (Z Babystepping, Speed Control, Flow Control)
 - [ ] Better system panel
 - [ ] Wifi selection
 - [ ] Manual bed leveling assist
 - [ ] Using thumbnails from prusa on job status page


More details to come...

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

### Manual Installation
```
sudo apt install -y xserver-xorg-video-fbturbo xinit xinput x11-xserver-utils python-gi python-gi-cairo gir1.2-gtk-3.0 python-requests python-websocket
```

Add the following to _/boot/config.txt_
```
hdmi_cvt=1024 600 60 6 0 0 0
hdmi_group=2
hdmi_mode=87
hdmi_drive=2
```
* Development has been using 1024x600 for a screen resolution. Other resolutions may have issues currently

After changing _/boot/config.txt_ you must reboot your raspberry pi. Please also ensure you followed setting up your screen via the screen instructions. This will likely have a xorg.conf.d file for inputs that you need to create.

Once that is done, follow the [Moonraker installation instructions](https://github.com/Arksine/moonraker/blob/master/docs/installation.md) to install the latest version of moonraker.

Using sudo, then run the service install script under _scripts/install_service.sh_ and perform _sudo systemctl daemon-reload_. You can then start KlipperScreen with systemctl such as _systemctl start KlipperScreen_





As an option to do development or interact with KlipperScreen from your computer, you may install tigervnc-scraping-server and VNC to your pi instance. Follow tigervnc server setup procedures for details on how to do that.
