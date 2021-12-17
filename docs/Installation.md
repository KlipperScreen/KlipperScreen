# Installation

#### Setup Raspberry Pi
This install process is meant for Raspbian non-desktop version aka Raspbian Lite.

If you have installed it on the GUI version, then use `sudo raspi-config` to set boot to console by choosing the following options in order:

* 1 System Options
    * S5 Boot / Auto Login
        * B1 Console

#### Klipper and Moonraker Installation

Follow the instructions to install Klipper and Moonraker.
* klipper: https://www.klipper3d.org/Installation.html
* moonraker: https://moonraker.readthedocs.io/en/latest/installation/

In moonraker.conf ensure that 127.0.0.1 is a trusted client for moonraker, such as in this example:
```
[authorization]
trusted_clients:
  127.0.0.1
```

Note: `force_logins: true` requires the moonraker api key in [KlipperScreen.conf](Configuration.md)

If you wish to use the update manager feature of moonraker for KlipperScreen, add the following block into the moonraker
configuration:
```
[update_manager KlipperScreen]
type: git_repo
path: ~/KlipperScreen
origin: https://github.com/jordanruthe/KlipperScreen.git
env: ~/.KlipperScreen-env/bin/python
requirements: scripts/KlipperScreen-requirements.txt
install_script: scripts/KlipperScreen-install.sh
```

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

If your screen needs additional software, proceed with the manufacturer instructions if they are provided
and check out the [hardware page](Hardware.md)

At this point KlipperScreen should be working, if it doesn't start then go to the [troubleshooting page](Troubleshooting.md)
