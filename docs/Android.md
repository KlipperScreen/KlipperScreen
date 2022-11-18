# Android

This article describes how to use KlipperScreen from an android device

!!! important
    The experience may not be equal to run KlipperScreen natively,
    depending on the device there maybe performance degradation or other issues

1. [First installl KlipperScreen on the Pi](Installation.md)
2. Install [XServer-XSDL](https://play.google.com/store/apps/details?id=x.org.server) on the android device
3. Choose [USB(ADB)](#adb) or [WIFI](#wifi)

### ADB

!!! warning
    Leaving the phone always connected it's not recommended, remove the battery to avoid issues.

* Install ADB on the Pi
```bash
sudo apt-get install android-tools-adb
```
* Put your Android phone/tablet in Debug mode.

Usually it involves enabling developer mode and "USB debugging" but this varies on different vendors and versions of the device
search "how to enable android debugging on device-model-and-brand"

* Copy the launcher script

```bash
cd ~/KlipperScreen/scripts
cp sample-android-adb.sh launch_KlipperScreen.sh
chmod +x launch_KlipperScreen.sh
```

* Go to [Startup](#startup)

### WIFI

* Create a launcher script

```bash
cd ~/KlipperScreen/scripts
touch launch_KlipperScreen.sh
chmod +x launch_KlipperScreen.sh
nano launch_KlipperScreen.sh
```

* Paste this into the script (replace the example IP)
```bash
DISPLAY=192.168.150.122:0 $KS_XCLIENT
```

!!! important
    It's recommended to use a static address, because if the address changes your connection will stop working.

* Go to [Startup](#startup)

## Startup

Start Xserver-XSDL On the android device

On the splash-screen of the app go to:
```
“CHANGE DEVICE CONFIGURATION”
└──Mouse Emulation Modde
    └──Desktop, No Emulation
```
if you missed it, restart the app.

on the Pi
```bash
sudo service KlipperScreen stop
sudo service KlipperScreen start
```

## Stop Screen Blanking in Xserver-XSDL

Even after enabling the "Stay Awake" option in the Developer/USB Debugging options of your Android device, the Xserver-XSDL may still go to a black screen but keep the backlight of your device on.  To keep the screen always active, upon start up of Xserver-XSDL app, select the `Change Device Configuration` at the top of the splash screen and then select the `Command line parameters, one argument per line` option. Append the following argument (must be on seperate lines):
```
-s
0
```
This will disable the screen-saver in Xserver and keep KlipperScreen always active.

## Migration from other tutorials

KlipperScreen says error option "service" is not supported anymore.

Stop the other service and Remove it, for example if the service is `KlippyScreenAndroid`:

```bash
sudo service KlippyScreenAndroid stop
sudo rm /etc/systemd/system/KlippyScreenAndroid.service
```

Follow this guide on how to setup the new launcher script with [USB(ADB)](#adb) or [WIFI](#wifi) and restart KS.

## Help

[The Discourse thread has old instructions but you may get some help if needed](https://klipper.discourse.group/t/how-to-klipperscreen-on-android-smart-phones/1196)

[#klipper-screen channel on Discord](https://discord.klipper3d.org/)

