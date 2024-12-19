# Frequently Asked Questions

## What is the minimum Python version required?

The minimum required version of Python is 3.8. This requirement is checked during installation.

??? "Using Older Python Versions"
    If you need to use Python 3.7, you can revert KlipperScreen to v0.4.1
    Connect to the printer via SSH and:
    ```sh
    cd ~/KlipperScreen
    git reset --hard v0.4.1
    ```

## Does KlipperScreen work with OctoPrint?

KlipperScreen is not designed to work with OctoPrint, and there are no plans to make it compatible.

## Can I use KlipperScreen as a desktop application?

Yes, you can use KlipperScreen as a desktop application. During installation, do not install it as a service. If you have already installed it as a service, you can disable it by running:
```sh
sudo systemctl disable KlipperScreen
```
Then, you can open the application via the menu when needed. You can also find the shortcut in `KlipperScreen/scripts/KlipperScreen.desktop`.

## Why did the title bar turn red and display CPU and RAM usage?

The red title bar indicating high CPU and RAM usage is a warning system. High resource usage can lead to issues, such as "timer too close" errors in Klipper. If this warning appears during an update or maintenance process, it is generally not an issue—just avoid starting a print job until the warning clears. You can use htop or similar tools from an SSH connection to check what’s consuming the resources.

## How can I switch between multiple printers?

KlipperScreen supports multiple printers. You can switch between them by configuring each printer's IP address in the KlipperScreen settings. This allows you to manage all your printers from a single interface, even if they are running on different hosts.

## Can I customize the KlipperScreen interface?

Yes, you can customize the KlipperScreen interface by editing the configuration files. Detailed instructions and options for customization can be found in the [documentation](https://klipperscreen.github.io/KlipperScreen/).

## What should I do if my touchscreen is not responding correctly?

If your touchscreen is not responding or has touch accuracy issues, check the [Touch Issues section](Troubleshooting/Touch_issues.md) in the troubleshooting guide. You may need to calibrate the touch settings or adjust the touch matrix.

## How do I update KlipperScreen?

To update KlipperScreen, follow the instructions in the [updating guide](Updating.md).

## What if I sometimes see the desktop instead of KlipperScreen?

If you sometimes see the desktop instead of KlipperScreen, and you only want to see KlipperScreen, you may have installed a distro with a full desktop environment. [Check these instructions](Troubleshooting/Desktop.md) on how to properly switch.
