#!/bin/bash
# ZBS351303 https://drive.google.com/drive/u/1/folders/1f7yZrkks6bTBMGS3TvcQ_Kiv6pGPDDDp
. ~/gdrive-log/gdrive-sync.conf
DESTDIR=$id_dir#15ipmzr9QrcIq3mrngQNnbGv6XdmdEtKf
LOGDIR=/home/pi/klipper_logs
SOURCELOG=/tmp/*.log
cp $SOURCELOG $LOGDIR
gdrive sync upload $LOGDIR $DESTDIR