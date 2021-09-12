# Installation

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
path: ~/KlipperScreen
origin: https://github.com/jordanruthe/KlipperScreen.git
env: ~/.KlipperScreen-env/bin/python
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
Most people don't need to calibrate, but if you do need to calibrate your touchscreen, follow the below steps.

Run this command:
```
DISPLAY=:0 xinput_calibrator --list
```
It will output something such as:
```
Device "wch.cn USB2IIC_CTP_CONTROL" id=6
```

Find the ID of your display and put it in the following command:
```
DISPLAY=:0 xinput_calibrator -v --device <id from last command>
```

#### Touchscreen touch rotation
If your touchscreen isn't registering touches properly after the screen has been rotated, you will need to apply a
transformation matrix. You can have the matrix be one of the following:
0°: `1 0 0 0 1 0 0 0 1`
90° Clockwise: `0 -1 1 1 0 0 0 0 1`
90° Counter-Clockwise: `0 1 0 -1 0 1 0 0 1`
180°: `-1 0 1 0 -1 1 0 0 1`

To check the current matrix, you will need your `<screen name>` (which can be found via the last section, ex:
"wch.cn USB2IIC_CTP_CONTROL"). Run the following command:
`xinput list-props "wch.cn USB2IIC_CTP_CONTROL"`

It will output something such as:
```
Device '<screen name>':
        Device Enabled (115):   1
        Coordinate Transformation Matrix (116): 1.000000, 0.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000, 0.000000, 1.000000
        libinput Calibration Matrix (247):      -1.000000, 0.000000, 1.000000, 0.000000, -1.000000, 1.000000, 0.000000, 0.000000, 1.000000
        libinput Calibration Matrix Default (248):      -1.000000, 0.000000, 1.000000, 0.000000, -1.000000, 1.000000, 0.000000, 0.000000, 1.000000
        libinput Send Events Modes Available (249):     1, 0
        libinput Send Events Mode Enabled (250):        0, 0
        libinput Send Events Mode Enabled Default (251):        0, 0
        Device Node (252):      "/dev/input/event0"
        Device Product ID (253):        6790, 58083
```

You can verify by checking that the 'Coordinate Transformation Matrix' or 'libinput Calibration Matrix'.

You can test a change by running:
`xinput set-prop "<screen name>" 'Coordinate Transformation Matrix' <matrix>`
Replace matrix with one of the options above, such as: `1 0 0 0 1 0 0 0 1`

To make this permanent, modify the file `/etc/udev/rules.d/51-touchscreen.rules` and put the following line in:
```
ACTION=="add", ATTRS{name}=="<screen name>", ENV{LIBINPUT_CALIBRATION_MATRIX}="<matrix>"
```
