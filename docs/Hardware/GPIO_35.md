
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

## Wrong colors

Some screens will not behave correctly and display wrong colors,
this usually due to the wrong [SPI](https://en.wikipedia.org/wiki/Serial_Peripheral_Interface) speed
In my case I had to use 16 Mhz (default is 24Mhz)
```
dtoverlay=piscreen,drm,speed=16000000
```

## Rotation

You can rotate the screen adding a rotate line with the degrees [0, 90, 180, 270]
```
dtoverlay=piscreen,drm,speed=16000000,rotate=180
```
Screen rotation will require adjusting the touch matrix see [Touch issues](../../Troubleshooting/Touch_issues/)