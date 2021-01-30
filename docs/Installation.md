### Required Hardware
KlipperScreen should run on any HDMI touchscreen that you can connect to a computer. The required video driver may
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

#### Setup Raspberry Pi
This install process is meant for Raspbian non-desktop version. If you have installed it on the GUI version, use
`sudo raspi-config` to set boot to console by choosing the following options in order:
* 1 System Options
* S5 Boot / Auto Login
* B1 Console

#### Klipper and Moonraker Installation

Follow the instructions to install klipper and moonraker.
klipper: https://github.com/KevinOConnor/klipper/
moonraker: https://github.com/Arksine/moonraker

Ensure that 127.0.0.1 is a trusted client for moonraker, such as in this example:
```
[authorization]
trusted_clients:
  127.0.0.1
```

If you wish to use the update manager feature of moonraker for KlipperScreen, add the following block into the moonraker
configuration:
```
[update_manager client KlipperScreen]
type: git_repo
path: /home/pi/KlipperScreen
origin: https://github.com/jordanruthe/KlipperScreen.git
env: /home/pi/.KlipperScreen-env/bin/python
requirements: scripts/KlipperScreen-requirements.txt
install_script: scripts/KlipperScreen-install.sh
```

#### KlipperScreen Installation
To clone and install execute the following commands:
```
cd ~/
git clone https://github.com/jordanruthe/KlipperScreen.git
cd ~/KlipperScreen
./scripts/KlipperScreen-install.sh
```

This script will install packages that are listed under manual install, create a python virtual environment at
${HOME}/.KlipperScreen-env and install a systemd service file.

KlipperScreen will create a log file output at `/tmp/KlipperScreen.log`. If you are having issues and KlipperScreen has
not gotten to the point where the log file has been created. Run `journalctl -xe -u KlipperScreen` to view the ouput and
see any issues that may be happening.

As an option to do development or interact with KlipperScreen from your computer, you may install tigervnc-scraping-server and VNC to your pi instance. Follow tigervnc server setup procedures for details on how to do that.

If you need a custom location for the configuration file, you can add -c or --configfile to the systemd file and specify
the location of your configuration file.

#### Touchscreen Calibration
Most people don't need to calibrate, but if you do need to calibrate your touchscreen, follow this process:

```
DISPLAY=:0 xinput_calibrator --list
Device "wch.cn USB2IIC_CTP_CONTROL" id=6
DISPLAY=:0 xinput_calibrator -v --device <id from last command>
```
