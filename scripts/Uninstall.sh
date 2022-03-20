#!/bin/bash

echo "Uninstalling KlipperScreen"
echo ""
echo "* Stopping service"
sudo service KlipperScreen stop
echo "* Removing unit file"
sudo rm /etc/systemd/system/KlipperScreen.service
echo "* Removing enviroment"
sudo rm -rf ~/.KlipperScreen-env
echo "!! Please remove $(dirname `pwd`) manually"
echo "Done"
