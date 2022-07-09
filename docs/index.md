# KlipperScreen

KlipperScreen is a touchscreen GUI that interfaces with [Klipper](https://github.com/kevinOConnor/klipper) via [Moonraker](https://github.com/arksine/moonraker). It can switch between multiple printers to access them from a single location, and it doesn't even need to run on the same host, you can install it on another device and configure the IP address to access the printer.

### Required Hardware

KlipperScreen should run on any touchscreen that you can connect to a host (Raspberry, PC, Tablet), but not screens that connect directly to the printer MCU board.

A physical touchscreen is not strictly required, for example you may install a remote desktop server like tigervnc-scraping-server and connect from a client device, [check out the hardware page for further information.](Hardware.md)

### Sample Panels

Main Menu

![Main Menu](img/panels/main_panel.png)

Job Status

![Job Status](img/panels/job_status.png)

[More](Panels.md)

### Inspiration
KlipperScreen was inspired by [OctoScreen](https://github.com/Z-Bolt/OctoScreen/) and the need for a touchscreen GUI that
will natively work with [Klipper](https://github.com/klipper3d/klipper) and [Moonraker](https://github.com/arksine/moonraker).

[Changelog](Changelog.md)
