#!/bin/bash

SCRIPTPATH=$(dirname -- "$(readlink -f -- "$0")")
KSPATH=$(dirname "$SCRIPTPATH")
KSENV="${KLIPPERSCREEN_VENV:-${HOME}/.KlipperScreen-env}"

XSERVER="xinit xinput x11-xserver-utils xserver-xorg-input-evdev xserver-xorg-input-libinput xserver-xorg-legacy xserver-xorg-video-fbdev"
CAGE="cage seatd xwayland"
PYGOBJECT="libgirepository1.0-dev gcc libcairo2-dev pkg-config python3-dev gir1.2-gtk-3.0"
MISC="librsvg2-common libopenjp2-7 libdbus-glib-1-dev autoconf python3-venv"
OPTIONAL="fonts-nanum fonts-ipafont libmpv-dev"

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

install_graphical_backend()
{
  while true; do
    if [ -z "$BACKEND" ]; then
      echo_text ""
      echo_text "Choose graphical backend"
      echo_ok "Default is Xserver"
      echo_text "Wayland is EXPERIMENTAL needs kms/drm drivers doesn't support DPMS and may need autologin"
      echo_text ""
      echo "Press enter for default (Xserver)"
      read -r -e -p "Backend Xserver or Wayland (cage)? [X/w]" BACKEND
      if [[ "$BACKEND" =~ ^[wW]$ ]]; then
        echo_text "Installing Wayland Cage Kiosk"
        if sudo apt install -y $CAGE; then
            echo_ok "Installed Cage"
            BACKEND="W"
            break
        else
            echo_error "Installation of Cage dependencies failed ($CAGE)"
            exit 1
        fi
      else
        echo_text "Installing Xserver"
        if sudo apt install -y $XSERVER; then
            echo_ok "Installed X"
            update_x11
            BACKEND="X"
            break
        else
            echo_error "Installation of X-server dependencies failed ($XSERVER)"
            exit 1
        fi
      fi
    fi
  done
}

install_packages()
{
    echo_text "Update package data"
    sudo apt update

    echo_text "Checking for broken packages..."
    if dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' | grep -E "^.[^nci]"; then
        echo_text "Detected broken packages. Attempting to fix"
        sudo apt -f install
        if dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' | grep -E "^.[^nci]"; then
            echo_error "Unable to fix broken packages. These must be fixed before KlipperScreen can be installed"
            exit 1
        fi
    else
        echo_ok "No broken packages"
    fi

    echo_text "Installing KlipperScreen dependencies"
    sudo apt install -y $OPTIONAL
    echo "$_"

    if sudo apt install -y $PYGOBJECT; then
        echo_ok "Installed PyGobject dependencies"
    else
        echo_error "Installation of PyGobject dependencies failed ($PYGOBJECT)"
        exit 1
    fi
    if sudo apt install -y $MISC; then
        echo_ok "Installed Misc packages"
    else
        echo_error "Installation of Misc packages failed ($MISC)"
        exit 1
    fi
}

check_requirements()
{
    VERSION="3,8"
    echo_text "Checking Python version > "$VERSION
    python3 --version
    if ! python3 -c 'import sys; exit(1) if sys.version_info <= ('$VERSION') else exit(0)'; then
        echo_error 'Not supported'
        exit 1
    fi
}

create_virtualenv()
{
    if [ "${KSENV}" = "/" ]; then
        echo_error "Failed to resolve venv location. Aborting."
        exit 1
    fi

    if [ -d "$KSENV" ]; then
        echo_text "Removing old virtual environment"
        rm -rf "${KSENV}"
    fi
    
    echo_text "Creating virtual environment"
    python3 -m venv "${KSENV}"

    if ! . "${KSENV}/bin/activate"; then
        echo_error "Could not activate the enviroment, try deleting ${KSENV} and retry"
        exit 1
    fi

    if [[ "$(uname -m)" =~ armv[67]l ]]; then
        echo_text "Using armv[67]l! Adding piwheels.org as extra index..."
        pip --disable-pip-version-check install --extra-index-url https://www.piwheels.org/simple -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
    else
        pip --disable-pip-version-check install -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
    fi
    if [ $? -gt 0 ]; then
        echo_error "Error: pip install exited with status code $?"
        echo_text "Trying again with new tools..."
        sudo apt install -y build-essential cmake libsystemd-dev
        if [[ "$(uname -m)" =~ armv[67]l ]]; then
            echo_text "Adding piwheels.org as extra index..."
            pip install --extra-index-url https://www.piwheels.org/simple --upgrade pip setuptools
            pip install --extra-index-url https://www.piwheels.org/simple -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
        else
            pip install --upgrade pip setuptools
            pip install -r ${KSPATH}/scripts/KlipperScreen-requirements.txt
        fi
        if [ $? -gt 0 ]; then
            echo_error "Unable to install dependencies, aborting install."
            deactivate
            exit 1
        fi
    fi
    deactivate
    echo_ok "Virtual environment created"
}

install_systemd_service()
{
    echo_text "Installing KlipperScreen unit file"

    SERVICE=$(cat "$SCRIPTPATH"/KlipperScreen.service)
    SERVICE=${SERVICE//KS_USER/$USER}
    SERVICE=${SERVICE//KS_ENV/$KSENV}
    SERVICE=${SERVICE//KS_DIR/$KSPATH}
    SERVICE=${SERVICE//KS_BACKEND/$BACKEND}

    echo "$SERVICE" | sudo tee /etc/systemd/system/KlipperScreen.service > /dev/null
    sudo systemctl unmask KlipperScreen.service
    sudo systemctl daemon-reload
    sudo systemctl enable KlipperScreen
    sudo systemctl set-default multi-user.target
    sudo adduser "$USER" tty
}

create_policy()
{
    POLKIT_DIR="/etc/polkit-1/rules.d"
    POLKIT_USR_DIR="/usr/share/polkit-1/rules.d"

    echo_text "Installing KlipperScreen PolicyKit Rules"
    sudo groupadd -f klipperscreen
    sudo groupadd -f network
    sudo adduser "$USER" netdev
    sudo adduser "$USER" network
    if [ ! -x "$(command -v pkaction)" ]; then
        echo "PolicyKit not installed"
        return
    fi

    POLKIT_VERSION="$( pkaction --version | grep -Po "(\d+\.?\d*)" )"
    echo_text "PolicyKit Version ${POLKIT_VERSION} Detected"
    if [ "$POLKIT_VERSION" = "0.105" ]; then
        # install legacy pkla
        create_policy_legacy
        return
    fi

    RULE_FILE=""
    if [ -d $POLKIT_USR_DIR ]; then
        RULE_FILE="${POLKIT_USR_DIR}/KlipperScreen.rules"
    elif [ -d $POLKIT_DIR ]; then
        RULE_FILE="${POLKIT_DIR}/KlipperScreen.rules"
    else
        echo "PolicyKit rules folder not detected"
        exit 1
    fi
    echo_text "Installing PolicyKit Rules to ${RULE_FILE}..."
    sudo rm ${RULE_FILE}

    KS_GID=$( getent group klipperscreen | awk -F: '{printf "%d", $3}' )
    sudo tee ${RULE_FILE} > /dev/null << EOF
polkit.addRule(function(action, subject) {
    if (action.id.indexOf("org.freedesktop.NetworkManager.") == 0 && subject.isInGroup("network")) {
        return polkit.Result.YES;
    }
});
polkit.addRule(function(action, subject) {
    if ((action.id == "org.freedesktop.login1.power-off" ||
         action.id == "org.freedesktop.login1.power-off-multiple-sessions" ||
         action.id == "org.freedesktop.login1.reboot" ||
         action.id == "org.freedesktop.login1.reboot-multiple-sessions" ||
         action.id == "org.freedesktop.login1.halt" ||
         action.id == "org.freedesktop.login1.halt-multiple-sessions" ||
         action.id.startsWith("org.freedesktop.NetworkManager.")) &&
        subject.user == "$USER") {
        return polkit.Result.YES;
        }
    }
});
EOF
}

create_policy_legacy()
{
    RULE_FILE="/etc/polkit-1/localauthority/50-local.d/20-klipperscreen.pkla"
    sudo tee ${RULE_FILE} > /dev/null << EOF
[KlipperScreen]
Identity=unix-user:$USER
Action=org.freedesktop.login1.power-off;
       org.freedesktop.login1.power-off-multiple-sessions;
       org.freedesktop.login1.reboot;
       org.freedesktop.login1.reboot-multiple-sessions;
       org.freedesktop.login1.halt;
       org.freedesktop.login1.halt-multiple-sessions;
       org.freedesktop.NetworkManager.*
ResultAny=yes
EOF
}

update_x11()
{
    sudo tee /etc/X11/Xwrapper.config > /dev/null << EOF
allowed_users=anybody
needs_root_rights=yes
EOF
}

fix_fbturbo()
{
    if [ "$(dpkg-query -W -f='${Status}' xserver-xorg-video-fbturbo 2>/dev/null | grep -c "ok installed")" -eq 0 ]; then
        FBCONFIG="/usr/share/X11/xorg.conf.d/99-fbturbo.conf"
        if [ -e $FBCONFIG ]; then
            echo_text "FBturbo not installed, but the configuration file exists"
            echo_text "This will fail if the config is not removed or the package installed"
            echo_text "moving the config to the home folder"
            sudo mv $FBCONFIG ~/99-fbturbo-backup.conf
        fi
    fi
}

add_desktop_file()
{
    mkdir -p "$HOME"/.local/share/applications/
    cp "$SCRIPTPATH"/KlipperScreen.desktop "$HOME"/.local/share/applications/KlipperScreen.desktop
    sudo cp "$SCRIPTPATH"/../styles/icon.svg /usr/share/icons/hicolor/scalable/apps/KlipperScreen.svg
}

start_KlipperScreen()
{
    echo_text "Starting service..."
    sudo systemctl restart KlipperScreen
}

install_network_manager()
{
    if [ -z "$NETWORK" ]; then
        echo "Press enter for default (Yes)"
        read -r -e -p "Install NetworkManager for the network panel [Y/n]" NETWORK
        if [[ $NETWORK =~ ^[nN]$ ]]; then
            echo_error "Not installing NetworkManager for the network panel"
        else
            echo_ok "Installing NetworkManager for the network panel"
            echo_text ""
            echo_text "If you were not using NetworkManager"
            echo_text "You will need to reconnect to the network using KlipperScreen or nmtui or nmcli"
            sudo apt install network-manager
            sudo mkdir -p /etc/NetworkManager/conf.d
            sudo tee /etc/NetworkManager/conf.d/any-user.conf > /dev/null << EOF
[main]
auth-polkit=false
EOF
            sudo systemctl -q disable dhcpcd 2> /dev/null
            sudo systemctl -q stop dhcpcd 2> /dev/null
            sudo systemctl enable NetworkManager
            sudo systemctl -q --no-block start NetworkManager
            sync
            systemctl reboot
        fi
    fi
}

# Script start
if [ "$EUID" == 0 ]
    then echo_error "Please do not run this script as root"
    exit 1
fi
check_requirements

if [ -z "$SERVICE" ]; then
    echo_text "Install standalone?"
    echo_text "It will create a service, enable boot to console and install the graphical dependencies."
    echo_text ""
    echo_text "Say no to install as a regular desktop app that will not start automatically"
    echo_text ""
    echo "Press enter for default (Yes)"
    read -r -e -p "[Y/n]" SERVICE
    if [[ $SERVICE =~ ^[nN]$ ]]; then
        echo_text "Not installing the service"
        echo_text "The graphical backend will NOT be installed"
    else
        install_graphical_backend
        install_systemd_service
        if [ -z "$START" ]; then
            START=1
        fi
    fi
fi

install_packages
create_virtualenv
create_policy
fix_fbturbo
add_desktop_file
install_network_manager
if [ -z "$START" ] || [ "$START" -eq 0 ]; then
    echo_ok "KlipperScreen was installed"
else
    start_KlipperScreen
fi
