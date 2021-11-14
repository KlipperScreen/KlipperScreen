#!/bin/bash
wget https://github.com/prasmussen/gdrive/releases/download/2.1.1/gdrive_2.1.1_linux_arm.tar.gz
tar -xvf gdrive_2.1.1_linux_arm.tar.gz
mkdir ~/gdrive-sync
sudo chmod 755 gdrive
sudo cp ./gdrive /usr/bin/
sudo rm ./*.tar.gz
sudo rm ./gdrive