# Troubleshooting

This page will have common problems and common solutions to those problems.

## First Steps

The first step to troubleshooting any problem is getting the cause of the error. KlipperScreen log output will occur
in two places. Check for the file `/tmp/KlipperScreen.log` and look at the contents by running
`cat /tmp/KlipperScreen.log` or grabbing the file over WinSCP or another scp program.

If that file is non-existent, there is a problem in KlipperScreen starting up. To get the error output in this case,
run `journalctl -xe -u KlipperScreen`.


## Common Errors

### Problems occurring before the log file appears

This section will detail problems that may happen before the log file has been created. Each section will start with a
relevant line from the journalctl output.

#### Cannot open virtual Console
```
xf86OpenConsole: Cannot open virtual console 2 (Permission denied)
```

* Check /etc/X11/Xwrapper.conf
This should have the line `allowed_users=anybody` in it
* Check /etc/group
Run the command `cat /etc/group | grep tty`. If you username is not listed under that line, you need to add it with the
following command (if you username is not 'pi' change 'pi' to your username):
`usermode -a -G tty pi`


### Problems occurring with the log file

#### Screen shows console instead of KlipperScreen
Run the command `ls /dev/fb*`. If you have multiple devices, you may need to fix the X11 configuration.

Run the command `cat /usr/share/X11/xorg.conf.d/99-fbturbo.conf | grep /dev/fb`. Try modifying the file (
`sudo nano /usr/share/X11/xorg.conf.d/99-fbturbo.conf`) and change `/dev/fb0` to a different file listed in the
previous command (i.e. `/dev/fb1`).

Once you have saved that file, restart KlipperScreen and it should show up on your display.

#### Screen is all white or blank

Improperly installed screen, follow the manufacturer instructions on how to physically connect the screen and install the proper drivers.
