
Screens that use HDMI should work out of the box

you may need to configure the resolution in RaspberryOS Bookworm
you can do this by editing the kernel commandline

```
sudo nano /boot/firmware/cmdline.txt
```

!!! warning "Important"
    Do not add newlines to the file, it must be 1 line with the options separated by spaces

for example:
```
video=1920x1080
```

more complex example:
```
video=HDMI-A-1:1920x1080M@60,rotate=90,reflect_x
```

???+ "Find the identifier use xrandr"
    on a terminal run:
    ```sh
    DISPLAY=:0 xrandr
    ```

    it will output something like:
    ```
    Screen 0: minimum 320 x 200, current 1024 x 600, maximum 8192 x 8192
    HDMI-1 connected primary 1024x600+0+0 (normal left inverted right x axis y axis) 800mm x 450mm
    ```
    in this case the identifier is HDMI-1 and a simple cmdline arg would be something like:

    `video=HDMI-1:1024x600@60`


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
