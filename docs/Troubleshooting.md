
This page will have common problems and common solutions to those problems.

# First Steps

The first step to troubleshooting any problem is getting the cause of the error.

* Find KlipperScreen.log:

!!! important
    This log file should be provided if you ask for support.

Depending on your setup the file could be accesible from the web interface alongside other logs

Mainsail | Fluidd
:-:|:-:
![m_logs](img/troubleshooting/logs_mainsail.png) | ![f_logs](img/troubleshooting/logs_fluidd.png)

if you can't find it in the web interface, use sftp to grab the log (for example Filezilla, WinSCP)
Located at `~/printer_data/logs`or in `/tmp/` if the former doesn't exists.

If KlipperScreen.log doesn't exist, run `systemctl status KlipperScreen`<br>
(or `journalctl -xe -u KlipperScreen`)

Check the file `/var/log/Xorg.0.log` where you can find issues with the X server.

## Cannot open virtual Console
If you see this line in the logs:
```sh
xf86OpenConsole: Cannot open virtual console 2 (Permission denied)
```

* Run `cat /etc/X11/Xwrapper.config`

This should have the line `allowed_users=anybody` in it

* Run `cat /etc/group | grep tty`

If your username is not listed under that line, you need to add it with the following command:

```sh
usermod -a -G tty pi
```
(if your username is not 'pi' change 'pi' to your username)

Restart KlipperScreen:
```sh
sudo service KlipperScreen restart
```

If it's still failing as a last resort add `needs_root_rights=yes` to `/etc/X11/Xwrapper.config`:
```sh
sudo bash -c "echo needs_root_rights=yes>>/etc/X11/Xwrapper.config"
```

restart KS.

## Screen shows console instead of KlipperScreen

If you have multiple framebuffers, you may need to fix the X11 configuration,
list the available framebuffers and check the current one:
```sh
ls /dev/fb*
cat /usr/share/X11/xorg.conf.d/99-fbturbo.conf | grep /dev/fb
```

If you more than one, try changing it:
```sh
sudo nano /usr/share/X11/xorg.conf.d/99-fbturbo.conf
```

for example: change `/dev/fb0` to `/dev/fb1`

Once you have saved that file, restart KlipperScreen.
```sh
sudo service KlipperScreen restart
```

If you have multiple hdmi ports try the other one

## Screen is all white or blank or no signal

If the screen never shows the console even during startup, Then it's tipically an improperly installed screen,
follow the manufacturer instructions on how to physically connect the screen and install the proper drivers.

## The screen starts flashing colors or stays all blue/white or shows 'No signal' when idle

In KliperScreen settings find 'Screen DPMS' and turn it off.
Your screen doesn't seem to support turning off via software, the best you can do is to turn it all black.

## Touch not working on debian Bullseye

Some dsi screens have issues where touch doesn't work with debian bullseye, the current fix
(at least until upstream is fixed) consist in changing the driver:

Run `raspi-config` > go to Advanced > GL Driver > select G2 and reboot.

![config](img/troubleshooting/gldriver.png)

*Or*:

manually edit `/boot/config.txt` and change:

```sh
dtoverlay=vc4-kms-v3d
```

to:
```sh
dtoverlay=vc4-fkms-v3d
```
and reboot, that should make the touch work, if your screen is rotated 180 degrees, then you may need to adjust
[the touch rotation](Hardware.md) as described in the Hardware page.

## OctoPrint

KlipperScreen was never intended to be used with OctoPrint, and there is no support for it.

## WiFi networks not listed

This can be caused because of the user is not allowed to control the interface

* Edit `/etc/wpa_supplicant/wpa_supplicant.conf` and add this line if it's not there:

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
```

* Run `cat /etc/group | grep netdev`

If your username is not listed under that line, you need to add it with the following command:

```sh
usermod -a -G netdev pi
```
(if your username is not 'pi' change 'pi' to your username)

Then reboot the machine:

```
systemctl reboot
```

!!! tip
    It's possible to just restart KlipperScreen and networking

## Other issues

If you found an issue not listed here, or can't make it work, please provide all the log files
a description of your hw, and a description of the issue when asking for support.
