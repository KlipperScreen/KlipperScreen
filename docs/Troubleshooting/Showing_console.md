# Screen shows console instead of KlipperScreen

If the screen is connected via HDMI and the board has more than one HDMI try the other port

## LCD-show

when using Waveshare-LCD-show repo to install screens add `lite` at the end to properly install the screen on the lite version of the os.
This is also applicable to the old version of good-tft

for example:
```
sudo ./LCD35-show lite
```

## Using wrong framebuffer

This is usually the result of not adding `lite` at the end of the command when installing a screen that requires LCD-show.
Follow [above](LCD-show) first if this is the case.

If you have multiple framebuffers, you may need to fix the X11 configuration,
list the available framebuffers and check the current one:
```sh
ls /dev/fb*
```

If you more than one, try changing it:

the file could be: 
- 99-fbturbo.conf
- 99-fbusb.conf
- 99-fbdev.conf

check if one of those or similar exist with:

```sh
ls /usr/share/X11/xorg.conf.d/
```

For example if 99-fbturbo.conf is there then edit it:

```sh
sudo nano /usr/share/X11/xorg.conf.d/99-fbturbo.conf
```

for example: change `/dev/fb0` to `/dev/fb1`

!!! important
    do `ls /dev/fb*` as said before to check if the other fb exists do not change it blindly

Once you have saved that file, restart KlipperScreen.
```sh
sudo service KlipperScreen restart
```

## FBturbo failing

in the system log (`sudo systemctl status KlipperScreen`) this appears:

`xinit[948]: /usr/lib/xorg/Xorg: symbol lookup error: /usr/lib/xorg/modules/drivers/fbturbo_drv.so: undefined symbol: shadowUpdatePackedWeak`

Fix it by removing fbturbo driver

`sudo apt purge xserver-xorg-video-fbturbo`
