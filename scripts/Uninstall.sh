#!/bin/bash

if [ "$EUID" -eq 0 ]; then
    echo "Please do not run this script as root"
    exit 1
fi

echo "Uninstalling KlipperScreen"
echo ""

echo "* Stopping service"
sudo systemctl stop KlipperScreen.service
sudo systemctl disable KlipperScreen.service

echo "* Removing unit file"
sudo rm /etc/systemd/system/KlipperScreen.service
sudo systemctl daemon-reload
sudo systemctl reset-failed

echo "* Removing environment"
sudo rm -rf ~/.KlipperScreen-env

echo ""
echo "* Uninstallation nearly complete. Please run:"
echo "cd && rm -rf KlipperScreen"
echo "to remove the source files"
echo ""
echo "Done"
