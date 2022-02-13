#!/bin/bash

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
KSPATH=$(sed 's/\/scripts//g' <<< $SCRIPTPATH)
KSENV="${HOME}/.KlipperScreen-env"

PKGLIST="xserver-xorg-video-fbturbo xdotool xinit xinput x11-xserver-utils libopenjp2-7 python3-distutils"
PKGLIST="${PKGLIST} python3-virtualenv virtualenv matchbox-keyboard wireless-tools"
PKGLIST="${PKGLIST} libatlas-base-dev fonts-freefont-ttf"
PKGLIST="${PKGLIST} libgirepository1.0-dev gcc libcairo2-dev pkg-config python3-dev gir1.2-gtk-3.0"

Red='\033[0;31m'
Green='\033[0;32m'
Cyan='\033[0;36m'
Normal='\033[0m'

echo_text ()
{
    printf "${Normal}$1${Cyan}\n"
}

echo_error ()
{
    printf "${Red}$1${Normal}\n"
}

echo_ok ()
{
    printf "${Green}$1${Normal}\n"
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
            echo_error "Unable to fix broken packages. These must be fixed before KlipperScreen can be installed"
            exit 1
        fi
    else
        echo_ok "No broken packages"
    fi

    echo_text "Installing KlipperScreen dependencies"
    sudo apt-get install -y $PKGLIST
}

create_virtualenv()
{
    echo_text "Creating virtual environment"
    if [ ! -d ${KSENV} ]; then
        GET_PIP="${HOME}/get-pip.py"
        virtualenv --no-pip -p /usr/bin/python3 ${KSENV}
        curl https://bootstrap.pypa.io/pip/3.6/get-pip.py -o ${GET_PIP}
        ${KSENV}/bin/python ${GET_PIP}
        rm ${GET_PIP}
    fi

    source ${KSENV}/bin/activate
    while read requirements; do
        pip install $requirements
        if [ $? -gt 0 ]; then
            echo "Error: pip install exited with status code $?"
            echo "Unable to install dependencies, aborting install."
            deactivate
            exit
        fi
    done < ${KSPATH}/scripts/KlipperScreen-requirements.txt
    deactivate
    echo_ok "Virtual enviroment created"
}

install_systemd_service()
{
    if [ -f "/etc/systemd/system/KlipperScreen.service" ]; then
        echo_text "KlipperScreen unit file already installed"
        sudo systemctl unmask KlipperScreen.service
        sudo systemctl daemon-reload
        sudo systemctl enable KlipperScreen
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

start_KlipperScreen()
{
    echo_text "Starting service..."
    sudo systemctl start KlipperScreen
}
if [ "$EUID" == 0 ]
    then echo_error "Plaease do not run this script as root"
    exit
fi
install_packages
create_virtualenv
modify_user
install_systemd_service
update_x11
echo_ok "KlipperScreen was installed"
start_KlipperScreen
