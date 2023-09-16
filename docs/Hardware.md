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
Configure the server to start in the desired orientation, there are many ways to achieve this,
here are some examples:

!!! warning
    Rotation is handled by the OS and not by KlipperScreen,
    if you can't rotate your screen it's usually an issue with the OS configuration


???+ example

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

[Moved to Touch issues](./Troubleshooting/Touch_issues.md)
