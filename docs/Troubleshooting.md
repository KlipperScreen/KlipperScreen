
# First Steps

The first step to troubleshooting any problem is getting the cause of the error.

* Find KlipperScreen.log:

!!! important
    This log file should be provided if you ask for support.

Depending on your setup the file could be accessible from the web interface alongside other logs

Mainsail | Fluidd
:-:|:-:
![m_logs](img/troubleshooting/logs_mainsail.png) | ![f_logs](img/troubleshooting/logs_fluidd.png)

if you can't find it in the web interface, use sftp to grab the log (for example Filezilla, WinSCP)
Located at `~/printer_data/logs`or in `/tmp/` if the former doesn't exist.

If KlipperScreen.log doesn't exist, run `systemctl status KlipperScreen`<br>
(or `journalctl -xe -u KlipperScreen`)

Check the file `/var/log/Xorg.0.log` where you can find issues with the X server.

## Cannot open virtual Console

If you see this line in the logs (`systemctl status KlipperScreen`):
```sh
xf86OpenConsole: Cannot open virtual console 2 (Permission denied)
```
[Follow this steps](Troubleshooting/VC_ERROR.md)

## Screen shows console instead of KlipperScreen

You may see this line in the logs (`systemctl status KlipperScreen`):

```sh
KlipperScreen-start.sh: (EE) no screens found(EE)
```
[Follow this steps](Troubleshooting/Showing_Console.md)

## Screen is all white or blank or no signal

If the screen never shows the console even during startup, Then it's typically an improperly installed screen,

You may see this line in the logs (`systemctl status KlipperScreen`):

```sh
KlipperScreen-start.sh: (EE) no screens found(EE)
```

[Follow this steps](Troubleshooting/Physical_Install.md)


## The screen shows colors or 'No signal' when idle

In KliperScreen settings find 'Screen DPMS' and turn it off.
Your screen doesn't seem to support turning off via software, the best you can do is to turn it all black.

## Touch issues


[Follow this steps](Troubleshooting/Touch_issues.md)

## Network panel doesn't list WI-FI networks

[Follow this steps](Troubleshooting/Network.md)

## OctoPrint

KlipperScreen was never intended to be used with OctoPrint, and there is no support for it.

## Other issues

If you found an issue not listed here, or can't make it work, please provide all the log files
a description of your hw, and a description of the issue when asking for support.
