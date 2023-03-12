#!/bin/bash

SCRIPTPATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
KSPATH=$(sed 's/\/scripts//g' <<< $SCRIPTPATH)
KSENV="${KLIPPERSCREEN_VENV:-${HOME}/.KlipperScreen-env}"

XSERVER="xinit xinput x11-xserver-utils xserver-xorg-input-evdev xserver-xorg-input-libinput"
FBDEV="xserver-xorg-video-fbdev"
PYTHON="python3-virtualenv virtualenv python3-distutils"
PYGOBJECT="libgirepository1.0-dev gcc libcairo2-dev pkg-config python3-dev gir1.2-gtk-3.0"
MISC="librsvg2-common libopenjp2-7 libatlas-base-dev wireless-tools libdbus-glib-1-dev autoconf"
OPTIONAL="xserver-xorg-legacy fonts-nanum fonts-ipafont libmpv-dev"

# moonraker will check this list when updating
# if new packages are required for existing installs add them below too.
PKGLIST="libdbus-glib-1-dev autoconf fonts-ipafont libmpv-dev"

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
        echo_text "Detected broken packages. Attempting to fix"
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
    sudo apt-get install -y $XSERVER
    if [ $? -eq 0 ]; then
        echo_ok "Installed X"
    else
        echo_error "Installation of X-server dependencies failed ($XSERVER)"
        exit 1
    fi
    sudo apt-get install -y $OPTIONAL
    echo $_
    sudo apt-get install -y $FBDEV
    if [ $? -eq 0 ]; then
        echo_ok "Installed FBdev"
    else
        echo_error "Installation of FBdev failed ($FBDEV)"
        exit 1
    fi
    sudo apt-get install -y $PYTHON
    if [ $? -eq 0 ]; then
        echo_ok "Installed Python dependencies"
    else
        echo_error "Installation of Python dependencies failed ($PYTHON)"
        exit 1
    fi
    sudo apt-get install -y $PYGOBJECT
    if [ $? -eq 0 ]; then
        echo_ok "Installed PyGobject dependencies"
    else
        echo_error "Installation of PyGobject dependencies failed ($PYGOBJECT)"
        exit 1
    fi
    sudo apt-get install -y $MISC
    if [ $? -eq 0 ]; then
        echo_ok "Installed Misc packages"
    else
        echo_error "Installation of Misc packages failed ($MISC)"
        exit 1
    fi
#     ModemManager interferes with klipper comms
#     on buster it's installed as a dependency of mpv
#     it doesn't happen on bullseye
    sudo systemctl mask ModemManager.service
}

create_virtualenv()
{
    echo_text "Creating virtual environment"
    if [ ! -d ${KSENV} ]; then
        virtualenv -p /usr/bin/python3 ${KSENV}
#         GET_PIP="${HOME}/get-pip.py"
#         virtualenv --no-pip -p /usr/bin/python3 ${KSENV}
#         curl https://bootstrap.pypa.io/pip/3.6/get-pip.py -o ${GET_PIP}
#         ${KSENV}/bin/python ${GET_PIP}
#         rm ${GET_PIP}
    fi

    source ${KSENV}/bin/activate
    pip --disable-pip-version-check install -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
    if [ $? -gt 0 ]; then
        echo_error "Error: pip install exited with status code $?"
        echo_text "Trying again with new tools..."
        sudo apt-get install -y build-essential cmake
        pip install --upgrade pip setuptools
        pip install -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
        if [ $? -gt 0 ]; then
            echo_error "Unable to install dependencies, aborting install."
            deactivate
            exit 1
        fi
    fi
    deactivate
    echo_ok "Virtual enviroment created"
}

install_systemd_service()
{
    echo_text "Installing KlipperScreen unit file"

    SERVICE=$(<$SCRIPTPATH/KlipperScreen.service)
    KSPATH_ESC=$(sed "s/\//\\\\\//g" <<< $KSPATH)
    KSENV_ESC=$(sed "s/\//\\\\\//g" <<< $KSENV)

    SERVICE=$(sed "s/KS_USER/$USER/g" <<< $SERVICE)
    SERVICE=$(sed "s/KS_ENV/$KSENV_ESC/g" <<< $SERVICE)
    SERVICE=$(sed "s/KS_DIR/$KSPATH_ESC/g" <<< $SERVICE)

    echo "$SERVICE" | sudo tee /etc/systemd/system/KlipperScreen.service > /dev/null
    sudo systemctl unmask KlipperScreen.service
    sudo systemctl daemon-reload
    sudo systemctl enable KlipperScreen
}

modify_user()
{
    sudo usermod -a -G tty $USER
}

update_x11()
{
    if [ -e /etc/X11/Xwrapper.config ]
    then
        echo_text "Updating X11 Xwrapper"
        sudo sed -i 's/allowed_users=console/allowed_users=anybody/g' /etc/X11/Xwrapper.config
    else
        echo_text "Adding X11 Xwrapper"
        echo 'allowed_users=anybody' | sudo tee /etc/X11/Xwrapper.config
    fi
}

add_desktop_file()
{
    DESKTOP=$(<$SCRIPTPATH/KlipperScreen.desktop)
    mkdir -p $HOME/.local/share/applications/
    echo "$DESKTOP" | tee $HOME/.local/share/applications/KlipperScreen.desktop > /dev/null
    sudo cp $SCRIPTPATH/../styles/icon.svg /usr/share/icons/hicolor/scalable/apps/KlipperScreen.svg
}

start_KlipperScreen()
{
    echo_text "Starting service..."
    sudo systemctl stop KlipperScreen
    sudo systemctl start KlipperScreen
}
if [ "$EUID" == 0 ]
    then echo_error "Please do not run this script as root"
    exit 1
fi
install_packages
create_virtualenv
modify_user
install_systemd_service
update_x11
echo_ok "KlipperScreen was installed"
add_desktop_file
start_KlipperScreen
