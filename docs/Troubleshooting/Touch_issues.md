# Touchscreen issues

If the screen is connected over USB, issues with the cable may cause similar symptoms. For that, please see [this guide](Physical_Install.md#cable-issues).

## Touch not working

Some DSI screens have issues where touch doesn't work with Debian Bullseye, or even in Debian Buster after an update. There is currently (September 2023) still no fix in upstream Debian.

The current workaround/temporary fix involves changing the kernel driver module used for these displays. 

To apply this fix:

Edit `/boot/config.txt` and change

```sh
dtoverlay=vc4-kms-v3d
```

to

```sh
dtoverlay=vc4-fkms-v3d
```

**Reboot** to apply changes.

If that doesn't fix it, you can try commenting these lines out:

```sh
# dtoverlay=vc4-kms-v3d
# max_framebuffers=2
```

**Reboot** to apply changes.

## Touch rotation and matrix

If the touch works but registers touch input in a different location from the input, then you may need to apply an input transformation matrix.

First you will need your device name. On a terminal, run:

```sh
DISPLAY=:0 xinput
```

Output:

```text
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

 | Rotation  | Matrix |
 | - | - |
 | 0° | `1 0 0 0 1 0 0 0 1` |
 | 90° Clockwise | `0 -1 1 1 0 0 0 0 1` |
 | 90° Counter-Clockwise | `0 1 0 -1 0 1 0 0 1` |
 | 180° (Inverts X and Y) | `-1 0 1 0 -1 1 0 0 1` |
 | invert Y | `-1 0 1 1 1 0 0 0 1` |
 | invert X | `-1 0 1 0 1 0 0 0 1` |
 | expand to twice the size horizontally | `0.5 0 0 0 1 0 0 0 1` |

For more in-depth guidance on using Coordinate Transformation Matrices:

* [Ubuntu wiki InputCoordinateTransformation](https://wiki.ubuntu.com/X/InputCoordinateTransformation)
* [Libinput docs](https://wayland.freedesktop.org/libinput/doc/1.9.0/absolute_axes.html)

It has been reported that the touch expands with screens that don't use HDMI. This is due to the composite output,
which enables automatically as a fallback when no HDMI device is plugged in.
If this is the case, adding `enable_tvout=0` to `/boot/config.txt` and reboot.

!!! example

    ```sh
    DISPLAY=:0 xinput set-prop "ADS7846 Touchscreen" 'Coordinate Transformation Matrix' -1 0 1 0 -1 1 0 0 1
    ```

    To make this permanent, modify the file `/etc/udev/rules.d/51-touchscreen.rules` and add following line:

    ```sh
    ACTION=="add", ATTRS{name}=="<device name>", ENV{LIBINPUT_CALIBRATION_MATRIX}="<matrix>"
    ```

    ---
    As an alternative **if the above doesn't work**:

    edit `/usr/share/X11/xorg.conf.d/40-libinput.conf`

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
