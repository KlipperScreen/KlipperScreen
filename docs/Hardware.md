# Hardware

There are no recommended screens, but the minimum supported resolution is 480x320.

In general, if the device can show a GNU/Linux desktop, then KlipperScreen should work too.

#### Hardware known to work

* [BTT PI TFT50](https://www.biqu.equipment/collections/lcd/products/bigtreetech-pi-tft50-v1-0-tft-display-for-raspberry-pi-3d-printer-part)
* [BTT HDMI5/7](https://biqu.equipment/products/bigtreetech-hdmi5-v1-0-hdmi7-v1-0)
* [Raspberry PI 7" Touchscreen](https://www.raspberrypi.org/products/raspberry-pi-touch-display/)
* [Hyperpixel 4](https://shop.pimoroni.com/products/hyperpixel-4)
* [3.5" Elegoo](https://www.elegoo.com/de/products/elegoo-3-5-inch-tft-lcd-screen)
* [3.5" RPi Display](http://www.lcdwiki.com/3.5inch_RPi_Display)
* [5" HDMI Display-B](http://lcdwiki.com/5inch_HDMI_Display-B)
* [VoCore](https://klipper.discourse.group/t/hardware-known-to-work-with-klipperscreen/35/7)
* [WAVESHARE 4.3 inch DSI LCD](https://www.waveshare.com/4.3inch-dsi-lcd.htm)
* [DFrobot DFR0550](https://wiki.dfrobot.com/5%27%27TFT-Display_with_Touchscreen_V1.0_SKU_DFR0550)
* [Android phone](Android.md)


* [More known hardware in the klipper discourse](https://klipper.discourse.group/t/hardware-known-to-work-with-klipperscreen/35)

### Configuration

Follow the manufacturer instructions on how to install your screen. In general if you see a white screen, then it's not properly installed, ensure that you at least see a console, Then [install](Installation.md) KlipperScreen, if you are having troubles refer to the [troubleshooting page](Troubleshooting.md) for further information.

## Screen rotation
Currently there is no support for rotation at runtime, do not use xrandr to rotate the screen.
Configure the server to start in the desired orientation, there are many ways to achieve this, here is one:


Create /usr/share/X11/xorg.conf.d/90-monitor.conf
```bash
sudo nano /usr/share/X11/xorg.conf.d/90-monitor.conf
```

Paste this section modifying the options to suit your needs:
```
Section "Monitor"
    Identifier "DPI-1"
    # This identifier would be the same as the name of the connector printed by xrandr.
    # it can be "HDMI-0" "DisplayPort-0", "DSI-0", "DVI-0", "DPI-0" etc

    Option "Rotate" "left"
    # Valid rotation options are normal,inverted,left,right


    Option "PreferredMode" "1920x1080"
    # May be necesary if you are not getting your prefered resolution.
EndSection
```
Save the file and restart KlipperScreen.

```bash
sudo service KlipperScreen restart
```


## Touchscreen touch rotation
If your touchscreen isn't registering touches properly after the screen has been rotated, you will need to apply a
transformation matrix.

First you will need your device name, on a terminal run:

```sh
DISPLAY=:0 xinput
```

Output:
```sh
⎡ Virtual core pointer                          id=2    [master pointer  (3)]
⎜   ↳ Virtual core XTEST pointer                id=4    [slave  pointer  (2)]
⎜   ↳ ADS7846 Touchscreen                       id=6    [slave  pointer  (2)]
⎣ Virtual core keyboard                         id=3    [master keyboard (2)]
    ↳ Virtual core XTEST keyboard               id=5    [slave  keyboard (3)]
```
In this case the device is the ADS7846 Touchscreen, yours may be different

You can test a change by running:

```sh
DISPLAY=:0 xinput set-prop "<device name>" 'Coordinate Transformation Matrix' <matrix>
```

Where the matrix can be one of the following options:

* 0°: `1 0 0 0 1 0 0 0 1`
* 90° Clockwise: `0 -1 1 1 0 0 0 0 1`
* 90° Counter-Clockwise: `0 1 0 -1 0 1 0 0 1`
* 180° (Inverts X and Y): `-1 0 1 0 -1 1 0 0 1`
* invert Y: `-1 0 1 1 1 0 0 0 1`
* invert X: `-1 0 1 0 1 0 0 0 1`

For example:

```sh
DISPLAY=:0 xinput set-prop "ADS7846 Touchscreen" 'Coordinate Transformation Matrix' -1 0 1 0 -1 1 0 0 1
```

To make this permanent, modify the file `/etc/udev/rules.d/51-touchscreen.rules` and add following line:

```sh
ACTION=="add", ATTRS{name}=="<device name>", ENV{LIBINPUT_CALIBRATION_MATRIX}="<matrix>"
```

As an alternative if the above doesn't work:

edit /usr/share/X11/xorg.conf.d/40-libinput.conf

for example:
```sh
Section "InputClass"
        Identifier "libinput touchscreen catchall"
        MatchIsTouchscreen "on"
        MatchDevicePath "/dev/input/event*"
        Driver "libinput"
        Option "TransformationMatrix" "0 -1 1 1 0 0 0 0 1"
EndSection
```

More info about input transformation can be found in:

* [Ubuntu wiki InputCoordinateTransformation](https://wiki.ubuntu.com/X/InputCoordinateTransformation)
* [Libinput docs](https://wayland.freedesktop.org/libinput/doc/1.9.0/absolute_axes.html)
