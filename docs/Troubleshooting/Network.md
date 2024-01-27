# Wi-Fi networks not listed

!!! tip "First start"
    The initial scan may take a while, first be patient before assuming it's an issue

The network panel requires network-manager to function, (if you are using a fork this may not be the case)

if version of KlipperScreen installed was previous than v0.3.9, then re-run the installer and reboot


??? "Alternative workaround for network-manager not having permissions"

    in order to fix this polkit needs to be configured or disabled:

    here is how to disable polkit for network-manager:

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
