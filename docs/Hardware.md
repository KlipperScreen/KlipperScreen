# Hardware

There are no recommended screens, but here are some guidelines:

* There is no support for vertical/portrait mode, only widescreen
* Minimum resolution of 480x320

#### Hardware known to work

* [BTT PI TFT50](https://www.biqu.equipment/collections/lcd/products/bigtreetech-pi-tft50-v1-0-tft-display-for-raspberry-pi-3d-printer-part)
* [Raspberry PI 7" Touchscreen](https://www.raspberrypi.org/products/raspberry-pi-touch-display/)
* [Hyperpixel 4](https://shop.pimoroni.com/products/hyperpixel-4)
* [3.5" Elegoo](https://www.elegoo.com/de/products/elegoo-3-5-inch-tft-lcd-screen)
* [3.5" RPi Display](http://www.lcdwiki.com/3.5inch_RPi_Display)
* [5" HDMI Display-B](http://lcdwiki.com/5inch_HDMI_Display-B)
* [VoCore](https://klipper.discourse.group/t/hardware-known-to-work-with-klipperscreen/35/7)
* [Android Phone](https://klipper.discourse.group/t/how-to-klipperscreen-on-android-smart-phones/1196)
* [WAVESHARE 4.3 inch DSI LCD](https://www.waveshare.com/4.3inch-dsi-lcd.htm)
* [DFrobot DFR0550](https://wiki.dfrobot.com/5%27%27TFT-Display_with_Touchscreen_V1.0_SKU_DFR0550)

* [More known hardware in the klipper discourse](https://klipper.discourse.group/t/hardware-known-to-work-with-klipperscreen/35)

#### Configuration

Follow the manufacturer instructions on how to install your screen. In general if you see a white screen, then it's not properly installed, ensure that you at least see a console, Then ![install](Installation.md) KlipperScreen, if you are having troubles refer to the ![troubleshooting page](Troubleshooting.md) for further information.

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

It will output somehting like:
```
Section "InputClass"
        Identifier      "calibration"
        MatchProduct    "ADS7846 Touchscreen"
        Option  "Calibration"   "3951 242 190 3885"
        Option  "SwapAxes"      "1"
EndSection
```
paste that into `sudo nano /etc/X11/xorg.conf.d/99-calibration.conf` replace the contents if necessary

restart KlipperScreen


#### Touchscreen touch rotation
If your touchscreen isn't registering touches properly after the screen has been rotated, you will need to apply a
transformation matrix. You can have the matrix be one of the following:

* 0°: `1 0 0 0 1 0 0 0 1`
* 90° Clockwise: `0 -1 1 1 0 0 0 0 1`
* 90° Counter-Clockwise: `0 1 0 -1 0 1 0 0 1`
* 180°: `-1 0 1 0 -1 1 0 0 1`

To check the current matrix, you will need your `<screen name>`
(which can be found via the last section, ex: "wch.cn USB2IIC_CTP_CONTROL").
Run the following command: `xinput list-props "wch.cn USB2IIC_CTP_CONTROL"`

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

You can test a change by running: `xinput set-prop "<screen name>" 'Coordinate Transformation Matrix' <matrix>`

Replace matrix with one of the options above, such as: `1 0 0 0 1 0 0 0 1`

To make this permanent, modify the file `/etc/udev/rules.d/51-touchscreen.rules` and add following line:

```
ACTION=="add", ATTRS{name}=="<screen name>", ENV{LIBINPUT_CALIBRATION_MATRIX}="<matrix>"
```
