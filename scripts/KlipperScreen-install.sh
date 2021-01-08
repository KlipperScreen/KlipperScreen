#!/bin/bash

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
KSPATH=$(sed 's/\/scripts//g' <<< $SCRIPTPATH)
KSENV="${HOME}/.KlipperScreen-env"

install_packages()
{
    echo "Update package data"
    sudo apt update

    echo "Installing package dependencies"
    sudo apt install -y \
        xserver-xorg-video-fbturbo \
        xinit \
        xinput \
        x11-xserver-utils \
        python3-distutils \
        python3-gi \
        python3-gi-cairo \
        python3-virtualenv \
        gir1.2-gtk-3.0 \
        virtualenv
}

create_virtualenv()
{
    echo "Creating virtual environment"
    [ ! -d ${KSENV} ] && virtualenv -p /usr/bin/python3 ${KSENV}

    ${KSENV}/bin/pip install -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
    ${KSENV}/bin/pip install --no-binary ":all" "vext.gi==0.7.4"
    ${KSENV}/bin/vext -e
}

install_systemd_service()
{
    echo "Installing KlipperScreen unit file"

    SERVICE=$(<$SCRIPTPATH/KlipperScreen.service)
    KSPATH_ESC=$(sed "s/\//\\\\\//g" <<< $KSPATH)
    KSENV_ESC=$(sed "s/\//\\\\\//g" <<< $KSENV)

    SERVICE=$(sed "s/KS_USER/$USER/g" <<< $SERVICE)
    SERVICE=$(sed "s/KS_ENV/$KSENV_ESC/g" <<< $SERVICE)
    SERVICE=$(sed "s/KS_DIR/$KSPATH_ESC/g" <<< $SERVICE)

    echo "$SERVICE" | sudo tee /etc/systemd/system/KlipperScreen.service > /dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable KlipperScreen
}

modify_user()
{
    sudo usermod -a -G tty $USER
}

update_x11()
{
    if [ -e /etc/X11/Xwrapper.conf ]
    then
        echo "Updating X11 Xwrapper"
        sudo sed -i 's/allowed_users=console/allowed_users=anybody/g' /etc/X11/Xwrapper.config
    else
        echo "Adding X11 Xwrapper"
        echo 'allowed_users=anybody' | sudo tee /etc/X11/Xwrapper.config
    fi
}

start_KlipperScreen() {
    sudo systemctl start KlipperScreen
}

install_packages
create_virtualenv
modify_user
install_systemd_service
update_x11
start_KlipperScreen
