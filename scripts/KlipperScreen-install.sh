#!/bin/bash

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
KSPATH=$(sed 's/\/scripts//g' <<< $SCRIPTPATH)
KSENV="${HOME}/.KlipperScreen-env"

PKGLIST="xserver-xorg-video-fbturbo xdotool xinit xinput x11-xserver-utils libopenjp2-7 python3-distutils python3-gi"
PKGLIST="${PKGLIST} python3-gi-cairo python3-virtualenv gir1.2-gtk-3.0 virtualenv matchbox-keyboard wireless-tools"
PKGLIST="${PKGLIST} libatlas-base-dev"
PKGLIST="${PKGLIST} python3-gst-1.0 vlc"

DGRAY='\033[1;30m'
NC='\033[0m'

echo_text ()
{
    printf "${NC}$1${DGRAY}\n"
}

install_packages()
{
    echo_text "Update package data"
    sudo apt-get update

    echo_text "Checking for broken packages..."
    output=$(dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' | grep -E ^.[^nci])
    if [ $? -eq 0 ]; then
        echo_text "Detectected broken pacakges. Attempting to fix"
        sudo apt-get -f install
        output=$(dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' | grep -E ^.[^nci])
        if [ $? -eq 0 ]; then
            echo_text "Unable to fix dependencies. These must be fixed before KlipperScreen can be installed"
            exit 1
        fi
    else
        echo_text "No broken packages"
    fi

    echo_text "Installing KlipperScreen dependencies"
    sudo apt-get install -y $PKGLIST
}

create_virtualenv()
{
    echo_text "Creating virtual environment"
    [ ! -d ${KSENV} ] && virtualenv -p /usr/bin/python3 ${KSENV}

    ${KSENV}/bin/pip install -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
    ${KSENV}/bin/pip install --no-binary :all: "vext.gi==0.7.4"
    ${KSENV}/bin/vext -e
}

install_systemd_service()
{
    if [ -f "/etc/systemd/system/KlipperScreen.service" ]; then
        echo_text "KlipperScreen unit file already installed"
        return
    fi
    echo_text "Installing KlipperScreen unit file"

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
        echo_text "Updating X11 Xwrapper"
        sudo sed -i 's/allowed_users=console/allowed_users=anybody/g' /etc/X11/Xwrapper.config
    else
        echo_text "Adding X11 Xwrapper"
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
echo "${NC}"
