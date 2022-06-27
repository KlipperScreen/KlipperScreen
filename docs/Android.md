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

* Create a launcher script

```bash
cd ~/KlipperScreen
touch launch_klipperscreen.sh
chmod +x launch_klipperscreen.sh
nano launch_klipperscreen.sh
```

* Paste this into the script
```bash
#!/bin/bash
# forward local display :100 to remote display :0
adb forward tcp:6100 tcp:6000

adb shell dumpsys nfc | grep 'mScreenState=' | grep OFF_LOCKED > /dev/null 2>&1
if [ $? -lt 1 ]
then
    echo "Screen is OFF and Locked. Turning screen on..."
    adb shell input keyevent 26
fi

adb shell dumpsys nfc | grep 'mScreenState=' | grep ON_LOCKED> /dev/null 2>&1
if [ $? -lt 1 ]
then
    echo "Screen is Locked. Unlocking..."
    adb shell input keyevent 82
fi

# start xsdl
adb shell am start-activity x.org.server/.MainActivity

ret=1
timeout=0
echo -n "Waiting for x-server to be ready "
while [ $ret -gt 0 ] && [ $timeout -lt 60 ]
do
    xset -display :100 -q > /dev/null 2>&1
    ret=$?
    timeout=$( expr $timeout + 1 )
    echo -n "."
    sleep 1
done
echo ""
if [ $timeout -lt 60 ]
then
    DISPLAY=:100 /home/pi/.KlipperScreen-env/bin/python3 /home/pi/KlipperScreen/screen.py
    exit 0
else
    exit 1
fi
```
* Go to [Startup](#startup)

### WIFI

* Create a launcher script

```bash
cd ~/KlipperScreen
touch launch_klipperscreen.sh
chmod +x launch_klipperscreen.sh
nano launch_klipperscreen.sh
```

* Paste this into the script (edit the IP for example: 192.168.1.2:0)
```bash
DISPLAY=(ip address from blue screen):0 /home/pi/.KlipperScreen-env/bin/python3 /home/pi/KlipperScreen/screen.py
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

## Discourse

[it has old instructions but you may get some help if needed](https://klipper.discourse.group/t/how-to-klipperscreen-on-android-smart-phones/1196)
