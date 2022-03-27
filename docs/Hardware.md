# Hardware

There are no recommended screens, but the minimum supported resolution is 480x320

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


#### Touchscreen touch rotation
If your touchscreen isn't registering touches properly after the screen has been rotated, you will need to apply a
transformation matrix.

First you will need your device name.

Run: `DISPLAY=:0 xinput`

Output
```
⎡ Virtual core pointer                          id=2    [master pointer  (3)]
⎜   ↳ Virtual core XTEST pointer                id=4    [slave  pointer  (2)]
⎜   ↳ ADS7846 Touchscreen                       id=6    [slave  pointer  (2)]
⎣ Virtual core keyboard                         id=3    [master keyboard (2)]
    ↳ Virtual core XTEST keyboard               id=5    [slave  keyboard (3)]
```
In this case the device is the ADS7846 Touchscreen, yours may be different

You can test a change by running:

`DISPLAY=:0 xinput set-prop "<device name>" 'Coordinate Transformation Matrix' <matrix>`

Where the matrix can be one of the following options:

* 0°: `1 0 0 0 1 0 0 0 1`
* 90° Clockwise: `0 -1 1 1 0 0 0 0 1`
* 90° Counter-Clockwise: `0 1 0 -1 0 1 0 0 1`
* 180° (Inverts X and Y): `-1 0 1 0 -1 1 0 0 1`
* invert Y: `-1 0 1 1 1 0 0 0 1`
* invert X: `-1 0 1 0 1 0 0 0 1`

For example:

`DISPLAY=:0 xinput set-prop "ADS7846 Touchscreen" 'Coordinate Transformation Matrix' -1 0 1 0 -1 1 0 0 1`

To make this permanent, modify the file `/etc/udev/rules.d/51-touchscreen.rules` and add following line:

```
ACTION=="add", ATTRS{name}=="<device name>", ENV{LIBINPUT_CALIBRATION_MATRIX}="<matrix>"
```
More info about input transformation can be found in:

* [Ubuntu wiki InputCoordinateTransformation]("https://wiki.ubuntu.com/X/InputCoordinateTransformation")
* [Libinput docs]("https://wayland.freedesktop.org/libinput/doc/1.9.0/absolute_axes.html")
