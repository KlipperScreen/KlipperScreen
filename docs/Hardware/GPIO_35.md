
How i installed the 3.5" (A) type of screen on RaspberryOS Bookworm (Debian 12)

Update: I've tested Bullseye (Debian 11) and it works, but [rotation was not working](#rotation)

![preview](../img/hardware/rpi35a.jpg)

!!! abstract "Disclaimer"
    This is based on my own experience, and it's provided for general information
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

I had to comment out (add # at the start) vc4 or it would boot into a blackscreen

```
#dtoverlay=vc4-kms-v3d
```

Close the nano editor using `ctrl`+`x` (exit), then `y` for yes (save).

```sh
sudo reboot
```

## Wrong colors or graphical corruption

Some screens will not behave correctly and/or display wrong colors,
this usually due to the wrong [SPI](https://en.wikipedia.org/wiki/Serial_Peripheral_Interface) speed
In my case the maximum i could achieve is 22.22Mhz
```
dtoverlay=piscreen,drm,speed=22222222
```

??? info "About speed"

    As you may predict speed has a big impact in usability as it dictates how often the display will refresh

    If i understand the [involved drivers](https://github.com/torvalds/linux/blob/65d287c7eb1d14e0f4d56f19cec30d97fc7e8f66/drivers/spi/spi-bcm2835.c#L1068)
    correctly, the spi speed is calculated as:
    `core_clock / core_divisor`

    The divisor must be a multiple of 2, that ranges between 2 and 65536

    Core clock in the case of Pi 3 would be 400mhz

    So even if you can enter any number, it will be approximated to a value from that formula

    That's why i used 22.222.222 (400 / 18)

reboot to test any changes.

## Rotation

You can rotate the screen adding a rotate line with the degrees [0, 90, 180, 270]
```
dtoverlay=piscreen,drm,rotate=180
```
Screen rotation will require adjusting the touch matrix see [Touch issues](../../Troubleshooting/Touch_issues/)

!!! bug

    Raspberry linux Kernel v6.1.77 has a bug in the dtb and rotate doesn't work

    The fix has been merged in linux v6.6

    you can copy the dtb from the new kernel into the old one if needed

## Console

To make the console work:

```sh
sudo nano /boot/firmware/cmdline.txt
```

add at the start or end:

```
fbcon=map:11
```

!!! warning "Important"
    Do not add newlines to the file,  it must be 1 line with the options separated by spaces
