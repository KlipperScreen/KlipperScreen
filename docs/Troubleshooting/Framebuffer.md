# Screen is using the wrong framebuffer


## LCD-show

when using [Waveshare-LCD-show](https://github.com/waveshare/LCD-show) to install screens add `lite` at the end
to properly install the screen on the lite version of the OS. this will typically change the framebuffer

for example:
```
sudo ./LCD35-show lite
```

## Manually change the framebuffer

If you have multiple framebuffers, you may need to fix the X11 configuration,
list the available framebuffers and check the current one:

```sh
ls /dev/fb*
```
!!! example "Output example"
    ```
    pi@raspberrypi ~ $ ls /dev/fb*
    /dev/fb0 /dev/fb1
    ```

!!! failure "Critical"
    if you only see one, for example `/dev/fb0` then this is not the issue. Go to [Troubleshooting](../Troubleshooting.md)

the file specifying the framebuffer could be:

- 99-fbturbo.conf
- 99-fbusb.conf
- 99-fbdev.conf

check if one of those or similar exist with:

```sh
ls /usr/share/X11/xorg.conf.d/
```

!!! failure "Critical"
    ***DO NOT CREATE A FILE***, and only edit if there is more than 1 framebuffer

!!! example
    you found 99-fbturbo.conf:

    ```sh
    sudo nano /usr/share/X11/xorg.conf.d/99-fbturbo.conf
    ```
    and the file specifies `/dev/fb0`

    since `ls /dev/fb*` returned `/dev/fb0 /dev/fb1` change it to `/dev/fb1`

    Save the file, restart KlipperScreen.

    ```sh
    sudo service KlipperScreen restart
    ```
