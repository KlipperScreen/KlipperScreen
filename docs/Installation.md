# Installation

## First Steps

1. **Install the Screen**: Follow the manufacturer’s instructions for installing your screen. Some screens may require additional software, while others might not.
2. **Test the Screen**: Ensure your hardware is functioning correctly by testing it with RaspberryOS, Ubuntu, or your preferred distribution.
3. **Proceed to Install KlipperScreen**: Once you’ve confirmed that the screen is working, you can proceed with installing KlipperScreen.

## Setup

The installation script is designed for RaspberryOS Lite, but it should work on other Debian derivatives as well.

## Auto Install

[KIAUH](https://github.com/dw-0/kiauh) is a tool that helps you install or upgrade Klipper, Moonraker, Mainsail, and other extensions.

![KIAUH Screenshot](img/install/KIAUH.png)

Visit [KIAUH on GitHub](https://github.com/dw-0/kiauh) to learn more and view its documentation.

## Manual Install

Follow these steps to manually install KlipperScreen:

Clone the KlipperScreen repository and run the installation script:
```sh
cd ~/
git clone https://github.com/KlipperScreen/KlipperScreen.git
./KlipperScreen/scripts/KlipperScreen-install.sh
```
This script will install the necessary packages, create a Python virtual environment at `~/.KlipperScreen-env`, and install a systemd service file.

!!! tip
    If you need a custom location for the configuration file, you can add the `-c` or `--configfile` option to the systemd file and specify the desired location.

## Moonraker Configuration

1. Ensure that the IP of the device is a trusted client in `moonraker.conf`:
    ```ini
    [authorization]
    trusted_clients:
      127.0.0.1
    ```
   Alternatively, add the [Moonraker API key](https://moonraker.readthedocs.io/en/latest/installation/#retrieving-the-api-key) to `KlipperScreen.conf`.

2. To use the update manager feature of Moonraker for KlipperScreen, add the following block to `moonraker.conf`:
    ```ini
    [update_manager KlipperScreen]
    type: git_repo
    path: ~/KlipperScreen
    origin: https://github.com/KlipperScreen/KlipperScreen.git
    virtualenv: ~/.KlipperScreen-env
    requirements: scripts/KlipperScreen-requirements.txt
    system_dependencies: scripts/system-dependencies.json
    managed_services: KlipperScreen
    ```

!!! tip
    If you see warnings in other UIs, ignore them until KlipperScreen finishes installing and Moonraker is restarted.

## Printer Configuration

Add the following basic configurations to your `printer.cfg` file for correct functionality:
```ini
[virtual_sdcard]
path: ~/printer_data/gcodes
[display_status]
[pause_resume]
```

## Macros

You may need additional macros for the printer to function as expected. For more information, [read the macros page](macros.md).