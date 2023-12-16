
# Troubleshooting

## First Steps

The first step to troubleshooting any problem is getting the cause of the error.

* Find KlipperScreen.log:

!!! warning "Important"
    This log file should be provided if you ask for support.

Depending on your setup the file could be accessible from the web interface alongside other logs

Mainsail | Fluidd
:-:|:-:
![mainsail_logs](img/troubleshooting/logs_mainsail.png) | ![fluidd_logs](img/troubleshooting/logs_fluidd.png)

if you can't find it in the web interface, use sftp to grab the log (for example Filezilla, WinSCP)
Located at `~/printer_data/logs`or in `/tmp/` if the former doesn't exist.

## System logs

If [KlipperScreen.log](#first-steps) doesn't exist open a terminal in the host (typically from SSH) and
copy all the relevant logs to the folder described above that can be seen and copied from the webui:

```sh
systemctl status KlipperScreen > ~/printer_data/logs/KliperScreen_systemctl.log
journalctl -xe -u KlipperScreen > ~/printer_data/logs/KliperScreen_journalctl.log
cp /var/log/Xorg.0.log ~/printer_data/logs/KliperScreen_Xorg.log
```


Alternatively you can inspect them directly on the terminal:

```sh
systemctl status KlipperScreen
```
```sh
journalctl -xe -u KlipperScreen
```
```sh
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
    This error is common on RaspberryOS when using FBturbo and it's not a related issue.

[Maybe it's the wrong framebuffer](Troubleshooting/Framebuffer.md)

If you can't fix it, [try using a desktop distro as described here.](Troubleshooting/Last_resort.md)

If you want to contribute a solution: [Contact](Contact.md)

## Screen is always ***white*** / ***black*** or ***`No signal`***

If the screen never shows the console even during startup, Then it's typically an improperly installed screen.

[Follow this steps](Troubleshooting/Physical_Install.md)


## The screen shows colors or 'No signal' when idle

In KliperScreen settings find 'Screen DPMS' and turn it off.

![dpms](img/troubleshooting/dpms.gif)

Your screen doesn't seem to support turning off via software.

KlipperScreen will enable an internal screensaver to make it all black, and hopefully avoid burn-in.
If you find a way of turning it off and you want to share it: [Contact](Contact.md)

## Touch issues


[Follow this steps](Troubleshooting/Touch_issues.md)

## Network panel doesn't list WI-FI networks

[Follow this steps](Troubleshooting/Network.md)

## OctoPrint

KlipperScreen was never intended to be used with OctoPrint, and there is no support for it.

## Other issues

If you found an issue not listed here, or can't make it work, please provide all the log files
a description of your hw, and a description of the issue when [asking for support](Contact.md)
