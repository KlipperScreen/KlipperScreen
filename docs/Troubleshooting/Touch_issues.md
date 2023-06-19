# Touchscreen issues

## Touch not working

Some DSI screens have issues where touch doesn't work with Debian Bullseye, or even in Debian Buster after an update, the current fix
(at least until upstream is fixed) consist in changing the driver:

manually edit `/boot/config.txt` and change:

```sh
dtoverlay=vc4-kms-v3d
```

to:
```sh
dtoverlay=vc4-fkms-v3d
```
reboot to apply changes.

if that doesn't fix it, try removing the line or comment it out

```
#dtoverlay=vc4-kms-v3d
#max_framebuffers=2
```

reboot to apply changes

If the screen is connected via USB It maybe a cable issue [See this section](Physical_Install.md#cable-issues)


## Touch rotation and matrix
If the touch works but it's not in the right place, it may need a transformation matrix.

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
* expand to twice the size horizontally: `0.5 0 0 0 1 0 0 0 1`
* compress horizontally: 
it has been reported that the touch expands with non-hdmi screens because composite out is enabled when hdmi is unplugged.
if this is the case try adding `enable_tvout=0` to `/boot/config.txt` and reboot.


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
