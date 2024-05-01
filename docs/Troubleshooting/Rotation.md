# Screen rotation
Configure the server to start in the desired orientation, there are many ways to achieve this,
here are some examples:

!!! warning
    Rotation is handled by the OS and not by KlipperScreen,
    if you can't rotate your screen it's usually an issue with the OS configuration

## Examples of rotation

???+ example "Universal xorg configuration"

    #### Universal xorg configuration
    Find the identifier use xrandr

    ```sh
    DISPLAY=:0 xrandr
    ```

    it will output something like:
    ```
    Screen 0: minimum 320 x 200, current 1024 x 600, maximum 8192 x 8192
    HDMI-1 connected primary 1024x600+0+0 (normal left inverted right x axis y axis) 800mm x 450mm
    ```

    Take not that the screen is `HDMI-1` (it could be `HDMI-A-1` or many other names)

    Create /usr/share/X11/xorg.conf.d/90-monitor.conf
    ```bash
    sudo nano /usr/share/X11/xorg.conf.d/90-monitor.conf
    ```
    Paste this section modifying the options to suit your needs:
    ```kconfig title="90-monitor.conf"
    Section "Monitor"
        Identifier "HDMI-1"
        # This identifier would be the same as the name of the connector printed by xrandr
        # for example  "DVI-I-1 connected primary" means that the identifier is "DVI-I-1"
        # another example "Unknown19-1 connected primary" some GPIO screens identify as Unknown19

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

    if KlipperScreen doesn't restart:
    ```bash
    sudo reboot
    ```

    you may have to adjust the [touch rotation](../Touch_issues/#touch-rotation-and-matrix)

??? example "Raspberry Pi using kernel cmdline"

    #### Raspberry Pi using kernel cmdline
    To set screen orientation when in console mode, you will need to edit the kernel command-line
    to pass the required orientation to the system.

    ```bash
    sudo nano /boot/firmware/cmdline.txt
    ```

    To rotate by 90 degrees clockwise, add the following to the cmdline, making sure everything is on the same line,
    do not add any carriage returns. Possible rotation values are 0, 90, 180 and 270.

    For example a DSI screen:
    ```bash
    video=DSI-1:800x480@60,rotate=90
    ```

    To find the identifier on a terminal run:
    ```bash
    DISPLAY=:0 xrandr
    ```
    it will output something like:

    ```bash
    Screen 0: minimum 320 x 200, current 1024 x 600, maximum 8192 x 8192
    HDMI-1 connected primary 1024x600+0+0 (normal left inverted right x axis y axis) 800mm x 450mm
    ```

    in this case the identifier is HDMI-1 and a simple cmdline arg would be something like:
    ```bash
    video=HDMI-1:1024x600@60
    ```

    To apply changes do a reboot:
    ```bash
    sudo reboot
    ```
    [Read the official docs for more info](https://www.raspberrypi.com/documentation/computers/config_txt.html)

    [Raspberry Display docs](https://www.raspberrypi.com/documentation/accessories/display.html)

??? example "Raspberry Pi legacy mode (works with vc4-fkms-v3d)"

    #### Raspberry Pi legacy mode (works with vc4-fkms-v3d)
    add to config.txt
    ```bash
    display_lcd_rotate=2
    ```

    To apply changes do a reboot:
    ```bash
    sudo reboot
    ```

    !!! warning
        At the moment of writing Pi4 didn't support 90 and 270 degrees with this method,  [see the official docs](https://www.raspberrypi.com/documentation/computers/config_txt.html#display_hdmi_rotate)

    | Value      | result |
    | ---------- | ---------- |
    | 0          | no rotation |
    | 1          | rotate 90 degrees clockwise |
    | 2          | rotate 180 degrees clockwise |
    | 3          | rotate 270 degrees clockwise |
    | 0x10000h   | horizontal flip |
    | 0x20000    | vertical flip |

    [Read the official docs for more info](https://www.raspberrypi.com/documentation/computers/config_txt.html)

??? example "Using a screen installed with goodtft-LCD-show"

    ####  Using a screen installed with goodtft-LCD-show
    ```bash
    cd LCD-show/
    sudo ./rotate.sh 90
    ```

??? example "Using Waveshare screen that is installed with LCD-show"

    ####  Using Waveshare screen that is installed with LCD-show
    ```bash
    cd LCD-show/
    sudo ./LCD43-show 270 lite
    ```


## Touchscreen touch rotation

[See touch rotation](./Touch_issues.md#touch-rotation-and-matrix)
