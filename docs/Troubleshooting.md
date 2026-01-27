
# Troubleshooting

## First Steps

The first step to troubleshooting any problem is getting the cause of the error.

* Find KlipperScreen.log:

!!! warning "Important"
    This log file should be provided if you ask for support.

Depending on your setup the file could be accessible from the web interface alongside other logs

|                        Mainsail                         |                       Fluidd                        |
|:-------------------------------------------------------:|:---------------------------------------------------:|
| ![mainsail_logs](img/troubleshooting/logs_mainsail.png) | ![fluidd_logs](img/troubleshooting/logs_fluidd.png) |

if you can't find it in the web interface, you will need to grab the system logs as explained below

??? tip "Alternative: Using sftp to grab the logs"
    It is possible to use sftp to grab the log, with an application like Filezilla or WinSCP

    With some file-browsers like Dolphin, just type the address for example: `sftp://pi@192.168.1.105/home/`

    Locate the logs at `~/printer_data/logs`or in `/tmp/` if the former doesn't exist.

## System logs

If [KlipperScreen.log](#first-steps) doesn't exist open a terminal in the host (typically from SSH) and
run this commands:

??? info "Multiple printers on the same host"
    If the host is running multiple printers you may need to change `printer_data` to `printer_1_data`

```sh
systemctl status KlipperScreen > ~/printer_data/logs/KlipperScreen_systemctl.log
journalctl -xe -u KlipperScreen > ~/printer_data/logs/KlipperScreen_journalctl.log
cp /var/log/Xorg.0.log ~/printer_data/logs/KlipperScreen_Xorg.log
cp -n /tmp/KlipperScreen.log ~/printer_data/logs/KlipperScreen.log
```

This will copy all the relevant logs to the folder described above, so they can be downloaded from the browser.
With the method described in the first section. You may need to press refresh or reload the page


??? tip "Alternative: inspect them directly on the terminal:"
    !!! warning
        Please do not copy-paste the output of the terminal when providing info for an issue,
        most of the time this output will be incomplete, use the method described above
    ```sh
    systemctl status KlipperScreen
    journalctl -xe -u KlipperScreen
    cat /var/log/Xorg.0.log
    ```


## Screen shows console instead of KlipperScreen

![boot](img/troubleshooting/boot.png)



!!! abstract "If you see this line in the [system logs](#system-logs):"
    ```sh
    xf86OpenConsole: Cannot open virtual console 2 (Permission denied)
    ```
    [Follow this steps](Troubleshooting/VC_ERROR.md)

!!! abstract "If you see this line in the [system logs](#system-logs):"
    ```sh
    xinit[948]: /usr/lib/xorg/Xorg: symbol lookup error: /usr/lib/xorg/modules/drivers/fbturbo_drv.so: undefined symbol: shadowUpdatePackedWeak
    ```
    [Follow this steps](Troubleshooting/FBturbo.md)

!!! abstract "If you see this line in the [system logs](#system-logs):"
    ```sh
    KlipperScreen-start.sh: (EE) no screens found(EE)
    ```
    This is usually not the main cause of the error. [Start by checking the screen](Troubleshooting/Physical_Install.md)

    Drivers not installed or misconfigured can cause this too, continue looking the logs for more clues.

!!! abstract "If you see this line in the [system logs](#system-logs):"
    ```sh
    modprobe: FATAL: Module g2d_23 not found in directory /lib/modules/6.1.21-v8+
    ```
    This error is common on RaspberryOS when using FBturbo, it's not a related issue, it works correctly with the error present.

!!! abstract "If you see this line in the [system logs](#system-logs):"
    ```sh
    (EE) Cannot run in framebuffer mode. Please specify busIDs for all framebuffer devices
    ```

    [Follow this steps](Troubleshooting/Framebuffer_id.md)



[Maybe it's the wrong framebuffer](Troubleshooting/Framebuffer.md)

If you can't fix it, [try using a desktop distro as described here.](Troubleshooting/Last_resort.md)

If you want to contribute a solution: [Contact](Contact.md)

## Screen is always ***white*** / ***black*** or ***`No signal`***

If the screen never shows the console even during startup, Then it's typically an improperly installed screen.

[Follow this steps](Troubleshooting/Physical_Install.md)


## The screen shows colors or 'No signal' when idle

!!! warning
    Only applicable to X11 not for Wayland

In KliperScreen settings find 'Screen DPMS' and turn it off.

![dpms](img/troubleshooting/dpms.gif)

Your screen doesn't seem to support turning off via software.

KlipperScreen will enable an internal screensaver to make it all black, and hopefully avoid burn-in.
If you find a way of turning it off, please share it: [Contact](Contact.md)

## Touch issues

[Follow this steps](Troubleshooting/Touch_issues.md)

## Network panel doesn't list WI-FI networks

[Follow this steps](Troubleshooting/Network.md)

## I see the Desktop environment instead of KlipperScreen

[Follow this steps](Troubleshooting/Desktop.md)

## Unauthorized

Unauthorized means that you need add the IP of the device that runs KlipperScreen to the moonraker trusted clients
or the Moonraker api-key to klipperscreen.conf

[Follow this steps](Installation.md#moonraker-configuration)

## Other issues

If you found an issue not listed here, or can't make it work, please provide all the log files
a description of your hw, and a description of the issue when [asking for support](Contact.md)
