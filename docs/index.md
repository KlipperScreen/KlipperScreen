# KlipperScreen

KlipperScreen is touchscreen GUI for Klipper based 3D printers. KlipperScreen interfaces with [Klipper](https://github.com/kevinOConnor/klipper) via [Moonraker](https://github.com/arksine/moonraker).

Multiple printers update is here! Please check the configuration information for specifying several printers.


[Changelog](changelog.md)

### Required Hardware
KlipperScreen should run on any touchscreen that you can connect to a computer. The required video driver may be
slightly different depending on what model you get. KlipperScreen will scale to the resolution of the screen being used.
However, three resolutions are tested during development: 1024x600, 800x480, 480x320.

There are no recommended screens, but there are several screens that work with KlipperScreen. They include screens that
use HDMI/USB, Raspberry Pi GPIO, or the Rapsberry Pi DSI (ribbon cable) port.

### Links

[Installation](Installation.md)

[Configuration](Configuration.md)

[Panels](panels.md)


### Sample Panels

Main Menu
![Main Menu](img/main_panel.png)

Job Status
![Job Status](img/job_status.png)


### Inspiration
KlipperScreen was inspired by [OctoScreen](https://github.com/Z-Bolt/OctoScreen/) and the need for a touchscreen GUI that
will natively work with [Klipper](https://github.com/kevinOConnor/klipper) and [Moonraker](https://github.com/arksine/moonraker).
