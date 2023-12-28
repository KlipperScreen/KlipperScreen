# Screen rotation
Configure the server to start in the desired orientation, there are many ways to achieve this,
here are some examples:

!!! warning
    Rotation is handled by the OS and not by KlipperScreen,
    if you can't rotate your screen it's usually an issue with the OS configuration

## Examples of rotation

???+ example "Universal xorg configuration"

    Create /usr/share/X11/xorg.conf.d/90-monitor.conf
    ```bash
    sudo nano /usr/share/X11/xorg.conf.d/90-monitor.conf
    ```

    Paste this section modifying the options to suit your needs:
    ```kconfig
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

??? example "Using Waveshare screen that is installed with LCD-show"

    ```bash
    cd LCD-show/
    sudo ./LCD43-show 270 lite
    ```

??? example "Using a screen installed with goodtft-LCD-show"

    ```bash
    cd LCD-show/
    sudo ./rotate.sh 90
    ```

??? example "Raspberry Pi"



    To set screen orientation when in console mode, you will need to edit the kernel command line to pass the required orientation to the system.

    ```bash
    sudo nano /boot/cmdline.txt
    ```

    To rotate by 90 degrees clockwise, add the following to the cmdline, making sure everything is on the same line, do not add any carriage returns. Possible rotation values are 0, 90, 180 and 270.

    ```bash
    video=DSI-1:800x480@60,rotate=90
    ```
    Other values can be "HDMI-0" "HDMI-1, "DPI-0" etc

    [Read the official docs for more info](https://www.raspberrypi.com/documentation/computers/config_txt.html)

    [Raspberry Display docs](https://www.raspberrypi.com/documentation/accessories/display.html)

??? example "Raspberry Pi legacy mode (works with vc4-fkms-v3d)"

    add to config.txt
    ```bash
    display_lcd_rotate=2
    ```
    Reboot

    !!! warning
        Pi4 doesn't support 90 and 270 degrees with this method,  [see the official docs](https://www.raspberrypi.com/documentation/computers/config_txt.html#display_hdmi_rotate)



    | Value      | result |
    | ---------- | ---------- |
    | 0          | no rotation |
    | 1          | rotate 90 degrees clockwise |
    | 2          | rotate 180 degrees clockwise |
    | 3          | rotate 270 degrees clockwise |
    | 0x10000h   | horizontal flip |
    | 0x20000    | vertical flip |

    [Read the official docs for more info](https://www.raspberrypi.com/documentation/computers/config_txt.html)

## Touchscreen touch rotation

[See touch rotation](../Touch_issues/#touch-rotation-and-matrix)
