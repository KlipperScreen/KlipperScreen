Multiple instances of KlipperScreen

*Dificulty: Advanced*

This article describes different methods of adding remote desktop clients (VNC or Xserver-XSDL) that do not support installing KS directly.
If your remote device runs GNU/Linux then you should install KlipperScreen directly, instead of the methods described below.

The instances will be independent of each other and not a mirror.

## Notes on Performance

Beware that running multiple instances on the same device at the same time will consume more resources (memory and processing time)
and can be taxing on lower end hardware, in my testing even a Raspberry Pi 3A can run multiple instances of KS,
providing that it doesn't have any cameras or other advanced features.

!!! tip
    You can view the system resource usage in the "System" panel of KlipperScreen or directly at the console with htop
    Beware that even if the load seems okay at idle, during a print heavy dynamic loads can push the device over the threshold
    and that may result in a Klipper error/failure, if it's running on the same device.

Performance will heavily depend on the devices used,
if one of the devices is connected through the network, like for example a VNC client or Android Xserver-XSDL client,
then the network will influence the response time of the interface.

## Option 1: Using the startup script method

*Advantage:* relatively easy to setup

*Disadvantage:* starting or stopping the service will affect all the instances

The default KlipperScreen service will launch the script

```sh
nano $HOME/KlipperScreen/scripts/launch_KlipperScreen.sh
```

Example script:

```sh
#!/bin/bash
/usr/bin/xinit $KS_XCLIENT &
DISPLAY=192.168.18.147:0 $KS_XCLIENT -c $HOME/.config/KlipperScreen/tablet.cfg &
wait
```

In this example the script launches a local instance for a screen connected to the host
then it launches a server for xserver-xsdl client that is running at the defined IP,
notice that the second instance uses a configuration that is specific to itself.

Dont forget to restart the service to load the changes
```sh
sudo systemctl restart KlipperScreen
```

## Option 2: Using a separate service

*Advantage:* stopping and starting the service will only affect the desired instance

*Disadvantage:* configuration and setup is more complex

Create a new service unit file

```sh
sudo nano /etc/systemd/system/KlipperScreen_tablet.service
```

Example of a service unit for an android tablet: (change the IP and username)
```ini title="KlipperScreen_tablet.service"
[Unit]
Description=KlipperScreen Tablet
StartLimitIntervalSec=0
After=systemd-user-sessions.service plymouth-quit-wait.service
ConditionPathExists=/dev/tty0
Wants=dbus.socket systemd-logind.service
After=dbus.socket systemd-logind.service
After=moonraker.service

[Service]
Type=simple
Restart=always
RestartSec=2
SupplementaryGroups=klipperscreen
# username
User=pi
WorkingDirectory=/home/pi/KlipperScreen
Environment="DISPLAY=192.168.18.147:0"
# Absolute paths are required, separate config is optional
ExecStart=/home/pi/.KlipperScreen-env/bin/python /home/pi/KlipperScreen/screen.py -c /home/pi/.config/KlipperScreen/tablet.cfg

[Install]
WantedBy=multi-user.target
```

Test your new service
```sh
sudo systemctl start KlipperScreen_tablet
```

Optional: After veryfing it works, make it load when the system starts
```sh
sudo systemctl enable KlipperScreen_tablet
```

if you made a mistake in the config you'll have to reload the service unit
```sh
sudo systemctl daemon-reload
```

Add the new service to moonraker so it can be started and stopped from the UI
```sh
nano $HOME/printer_data/moonraker.asvc
```
In the example above it was `KlipperScreen_tablet`. Beware that is case sensitive

So in this case it would look something like this:
``` title="moonraker.asvc"
klipper_mcu
webcamd
MoonCord
KlipperScreen
KlipperScreen_tablet
moonraker-telegram-bot
moonraker-obico
sonar
crowsnest
octoeverywhere
```

Restart moonraker
```sh
sudo systemctl restart moonraker
```
