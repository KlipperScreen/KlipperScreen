# Hardware

KlipperScreen should run on any touchscreen that you can connect to a computer. The required video driver may
be slightly different depending on what model you get. I am developing on a 1024x600 resolution screen. Due to this,
other resolutions may not be scaled properly at this moment. UI scaling is a future development item.

#### Configure Hardware

Add the following to _/boot/config.txt_. You can alter the hdmi_cvt to your screen specifications. This example is setup
for a resolution of 1024x600 and a refresh rate of 60hz.
```
hdmi_cvt=1024 600 60 6 0 0 0
hdmi_group=2
hdmi_mode=87
hdmi_drive=2
```
* Development has been using 1024x600 for a screen resolution. Other resolutions may have issues currently

After changing _/boot/config.txt_ you must reboot your raspberry pi. Please also ensure you followed setting up your screen via the screen instructions. This will likely have a xorg.conf.d file for input from the touchscreen that you need to create.

#### Hardware known to work

[Click here](https://klipper.discourse.group/t/hardware-known-to-work-with-klipperscreen/35) to go to a post on the Klipper discourse server for known hardware or see the below list.

[BTT PI TFT50](https://www.biqu.equipment/collections/lcd/products/bigtreetech-pi-tft50-v1-0-tft-display-for-raspberry-pi-3d-printer-part)
[Raspberry PI 7" Touchscreen](https://www.raspberrypi.org/products/raspberry-pi-touch-display/)
