# Screen is using the wrong framebuffer

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

## Use fbcp to copy from one framebuffer to the other

```sh
cd
git clone https://github.com/tasanakorn/rpi-fbcp.git
cd rpi-fbcp
mkdir build
cd build
cmake ..
make
sudo install fbcp /usr/local/bin/fbcp
sudo wget -O /etc/init.d/fbcp https://gist.github.com/notro/eac0fec51cac67bb99c7/raw/4804a36459db10b17d35451d98d4573a045084be/fbcp
sudo chmod +x /etc/init.d/fbcp
sudo update-rc.d fbcp defaults
sudo reboot
```

## Manually change the framebuffer


the file specifying the framebuffer could be:

- 99-fbturbo.conf
- 99-fbusb.conf
- 99-fbdev.conf

check if one of those or similar exist with:

```sh
ls /usr/share/X11/xorg.conf.d/
```

!!! example
    you found 99-fbdev.conf:

    ```sh
    sudo nano /usr/share/X11/xorg.conf.d/99-fbdev.conf
    ```
    ``` title="99-fbdev.conf"
    Section "Device"
            Identifier      "Allwinner A10/A13/A20 FBDEV"
            Driver          "fbdev"
            Option          "fbdev" "/dev/fb0"
            Option          "SwapbuffersWait" "true"
    EndSection
    ```

    since `ls /dev/fb*` returned `/dev/fb0 /dev/fb1` change it to `/dev/fb1`

    Save the file, restart KlipperScreen.

    ```sh
    sudo service KlipperScreen restart
    ```
