
How i installed the 3.5" (A) type of screen on RaspberryOS Bookworm (Debian 12)

![preview](../img/hardware/rpi35a.jpg)

!!! abstract
    this is based on my own experience and it's provided for general information
    and does not constitute as advice of any kind.


## Initial install

This screens connect to the [GPIO](https://en.wikipedia.org/wiki/General-purpose_input/output)
they were usually installed via  repositories named LCD-show ([1](https://github.com/waveshare/LCD-show), [2](https://github.com/goodtft/LCD-show)),
however in the bookworm release there is a simpler solution

```sh
sudo nano /boot/firmware/config.txt
```
at the bottom add:
```
dtoverlay=piscreen,drm
```

???+ info
    in this context drm stands for [Direct Rendering Manager](https://en.wikipedia.org/wiki/Direct_Rendering_Manager)

Close the nano editor using `ctrl`+`x` (exit), then `y` for yes (save).

```sh
sudo reboot
```

## Wrong colors or graphical corruption

Some screens will not behave correctly and/or display wrong colors,
this usually due to the wrong [SPI](https://en.wikipedia.org/wiki/Serial_Peripheral_Interface) speed
In my case the maximum i could achieve is 22.22Mhz (400mhz core / 18)
```
dtoverlay=piscreen,drm,speed=22222222
```
As you may predict speed has a big impact in usability as it dictates how often the display will refresh

reboot to test any changes.

## Rotation

!!! bug
    The current Rpi Kernel v6.1.77 has a bug in the dtb and rotate doesn't work, fix has been merged in v6.6
    you can copy the dtb from the new kernel into the old one if needed


You can rotate the screen adding a rotate line with the degrees [0, 90, 180, 270]
```
dtoverlay=piscreen,drm,rotate=180
```
Screen rotation will require adjusting the touch matrix see [Touch issues](../../Troubleshooting/Touch_issues/)

## Console

To make the console work:

```sh
sudo nano /boot/firmware/cmdline.txt
```

add at the start or end:

```
fbcon=map:11
```

!!! warning Important
    do not add newlines to the file,  it must be 1 line with the options separated by spaces
