# Developer Guide

Basic setup for an enviroment to do development of KlipperScreen.

!!! note "Alfrix Note:"
    I use a standard Linux distro with a desktop enviroment.

## Clone the repo
Clone your fork, for example:
```
cd ~
git clone https://github.com/klipperscreen/klipperscreen.git
```

## Install the dependencies on the host
The X11 or Wayland dependencies should not be needed if you are running a desktop GNU/Linux distro.
See [scripts/system-dependencies.json](https://github.com/KlipperScreen/KlipperScreen/blob/master/scripts/system-dependencies.json)

## Create a virtual environment
For example:
```bash
virtualenv -p /usr/bin/python3   ~/.KlipperScreen-env
source ~/.KlipperScreen-env/bin/activate
cd ~/KlipperScreen
pip install -r scripts/klipperscreen-requirements.txt
```
# Set configurations
Create klipperscreen.conf and place it on the repo folder
```
[main]
show_cursor=True
# disable screen timeouts
use_dpms=False
screen_blanking=off
# disable Fullscreen and start in a specified size
# 480 x 320 is the minimum size to target
width=480
height=320
# setting width or height will disable fullscreen and it's the intended behavior 
```

At this point you can add your actual printer section with the IP (and port of needed) to the config or/and add a virtual printer

# Optional: Virtual printer

You may use a virtual printer like it's described in the [klipper docs](https://www.klipper3d.org/Debugging.html#testing-with-simulavr), 
or it's [alternative that uses docker](https://github.com/mainsail-crew/virtual-klipper-printer)

Using a Virtual printer will need klipper and moonraker need to be installed in the machine too.

!!! note
    The virtual printer has various limitations,
    like constant temperature and limited availability of pins,
    it's not a limitation of klipperscreen

## Optional: Configure the IDE

* Set interpreter to the virtual environment created
* Set the run configuration to `KlipperScreen/screen.py`
