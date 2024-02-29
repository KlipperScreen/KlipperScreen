
Screens that use HDMI should work out of the box

you may need to configure the resolution in RaspberryOS Bookworm
you can do this by editing the kernel commandline

```
sudo nano /boot/firmware/cmdline.txt
```

!!! tip "Important"
    Put all parameters in cmdline.txt on the same line, do not use carriage returns.

for example:
```
video=1920x1080
```

more complex example:
```
video=HDMI-A-1:1920x1080M@60,rotate=90,reflect_x
```

| Device      | 	Display                                        |
|-------------|-------------------------------------------------|
| HDMI-A-1    | HDMI 1 (sometimes HDMI 0 on PCB)                |
| HDMI-A-2    | HDMI 2 (sometimes HDMI 1 on PCB if starts at 0) |
| DSI-1       | DSI or DPI                                      |
| Composite-1 | Composite                                       |


Valid mode specifiers:
```
<xres>x<yres>[M][R][-<bpp>][@<refresh-rate>][i][m][eDd]
```
options on brackets are optional

| Option          | Description                                                                            |
|-----------------|----------------------------------------------------------------------------------------|
| M               | Calculate timings using [CVT](https://en.wikipedia.org/wiki/Coordinated_Video_Timings) |
| R               | CVT reduced blanking (refresh rate must be 60Hz)                                       |
| -<bpp>          | Bits per pixel, A.K.A. BitDepth usuallly 24                                            |
| @<refresh-rate> | acceptable refresh rates are 50, 60, 70 or 85 Hz only                                  |
| e               | Force enable                                                                           |
| D               | Force enable Digital mode                                                              |
| d               | Disable                                                                                |

For more info read [modedb default video mode support](https://docs.kernel.org/fb/modedb.html)
