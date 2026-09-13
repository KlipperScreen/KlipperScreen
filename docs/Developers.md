# Developer Guide

Basic setup for an environment to do development of KlipperScreen.

!!! note "Alfrix Note:"
    I use a standard Linux distro with a desktop environment.

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
cd ~/KlipperScreen
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/KlipperScreen-requirements.txt
# this one is optional:
pip install -r scripts/dev-requirements.txt
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

### Pre-commit hooks

This project uses [pre-commit](https://pre-commit.com/) to run linting and formatting checks before each commit.

Install the hooks:
```bash
cd ~/KlipperScreen
source .venv/bin/activate
pip install pre-commit
pre-commit install
```

This will automatically run `ruff check --fix` and `ruff format` on staged files before every commit.

## Optional: Configure the IDE

* Set interpreter to the virtual environment created
* Set the run configuration to `KlipperScreen/screen.py`

# Add-ons

Off by default. Turn on `Enable Add-ons` in Settings and restart -- it runs
code that did not come from this project.

Each `addons/<name>.py`, or `addons/<name>/__init__.py`, is then imported once
at startup and given `init(screen)` if it defines one.

```python
# addons/example.py
import logging


def init(screen):
    logging.info("example add-on starting")
```

* `init` runs before Moonraker connects, so `screen.printer` and the websocket
  are still `None`. Register what you need and act on the first update; do not
  query the printer here.
* Names beginning with `_` are skipped.
* Imported under a private `ks_addons` package, so `addons/json.py` cannot
  shadow the standard library.
* Every add-on that loads is named in the notification panel. One that raises
  is logged, skipped, and named in an error popup; it cannot stop KlipperScreen
  starting.
* `addons/` sits here rather than in the config directory, which is writable
  through Moonraker's file manager. It is gitignored, so an update recovering
  with `git clean -fd` does not delete it.
* The setting lives in `KlipperScreen.conf`, outside this repository, so it
  survives updates.
