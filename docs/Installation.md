# Installation

#### First steps

Install the screen, following the instructions provided by the manufacturer, Some screens don't neeed extra software but some need to be installed with a script.
It's strongly recommended to test it and ensure your hardware is working with Raspbian, Ubuntu or any distro you like.
Once you stablished that the screen is working, then proceed installing KlipperScreen.

#### Setup Raspberry Pi
This install process is meant for Raspbian non-desktop version aka Raspbian Lite, but it works on other versions.

If you want to use it on Raspbian desktop (GUI version), then use `sudo raspi-config` to set boot to console by choosing the following options in order:

```
1System Options
└──S5 Boot / Auto Login
   └──B1 Console
```

Note: Other distros will be different on how to boot to console.

### Auto install

#### Installing KlipperScreen with KIAUH

[KIAUH](https://github.com/th33xitus/kiauh) is a tool that helps you install or upgrade Klipper, Moonraker, Mainsail, and other extensions.

![Screenshot](img/install/KIAUH.png)

You can visit [KIAUH on GitHub](https://github.com/th33xitus/kiauh) to learn more and view its documentation.


### Manual Install

#### Klipper and Moonraker Installation

Follow the instructions to install Klipper and Moonraker.

* klipper: https://www.klipper3d.org/Installation.html
* moonraker: https://moonraker.readthedocs.io/en/latest/installation/

#### Moonraker configuration

In moonraker.conf ensure that 127.0.0.1 is a trusted client:

```
[authorization]
trusted_clients:
  127.0.0.1
```
Note: `force_logins: true` requires the moonraker api key in [KlipperScreen.conf](Configuration.md)

If you wish to use the update manager feature of moonraker for KlipperScreen, add the following block to the moonraker.conf:

```
[update_manager KlipperScreen]
type: git_repo
path: ~/KlipperScreen
origin: https://github.com/jordanruthe/KlipperScreen.git
env: ~/.KlipperScreen-env/bin/python
requirements: scripts/KlipperScreen-requirements.txt
install_script: scripts/KlipperScreen-install.sh
```
Note: you may receive warnings in other UIs since KlipperScreen is not installed yet, you can safely ignore them at this point.

#### KlipperScreen Installation
Execute the following commands:

```
cd ~/
git clone https://github.com/jordanruthe/KlipperScreen.git
cd ~/KlipperScreen
./scripts/KlipperScreen-install.sh
```

This script will install packages that are listed under manual install, create a python virtual environment at
~/.KlipperScreen-env and install a systemd service file.

If you need a custom location for the configuration file, you can add -c or --configfile to the systemd file and specify
the location of your configuration file.

At this point KlipperScreen should be working, if it doesn't start then go to the [troubleshooting page](Troubleshooting.md)
