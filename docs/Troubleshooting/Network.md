# Network

The network panel relies on Network-Manager for its operation.

!!! info "Note for Forks"
    The network panel's behavior and dependencies may differ. Please refer to your specific fork documentation or support resources for instructions tailored to your setup.

## Loss of Connection After Installing Network-Manager

If you lose network connection after installing Network-Manager, follow these steps to reconnect:

### Reconnect using KlipperScreen
- **Go to the network panel in KlipperScreen:**
  - Access the network panel in KlipperScreen and select your Wi-Fi network to reconnect.

!!! info "Alternative: using the console"

    - **Option 1: Switch to a local console with keyboard:**
        1. Use `Ctrl + Alt + F1` (or other function keys up to F6) to access a virtual terminal.
        2. Log in and run `nmtui` to manage Wi-Fi connections directly from the console.

    - **Option 2: Connect a LAN cable for SSH access:**
        1. Use SSH to remotely connect to your system.
        2. Run `nmtui` to manage your network connections.


## Wi-Fi networks not listed

The initial scan may take a while, first be patient before assuming it's an issue. and check with other tools like `nmtui`

## Permission error
Usually permissions are set with the installer, try to update and then re-run the installer and reboot


???+ "Alternative workaround for network-manager not having permissions"

    ```sh
    mkdir -p /etc/NetworkManager/conf.d
    sudo nano /etc/NetworkManager/conf.d/any-user.conf
    ```

    in the editor paste this:

    ```ini
    [main]
    auth-polkit=false
    ```

    Then restart the service (or reboot):

    ```sh
    systemctl restart NetworkManager.service
    systemctl restart KlipperScreen.service
    ```
