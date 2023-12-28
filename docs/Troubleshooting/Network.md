# Wi-Fi networks not listed

!!! tip "First start"
    The initial scan may take a couple of minutes, first be patient before assuming it's an issue

Check if network-manager is installed:

```bash
dpkg -s network-manager
```

if the response is the following:

```sh
dpkg-query: the package 'network-manager' is not installed
```

go to [wpa_supplicant](wpa_supplicant.md)

if the response is the following:

```sh
Package: network-manager
Status: install ok installed
```

this line may appear in KlipperScreen.log:
!!! abstract "Log"
    ```sh
    [wifi_nm.py:rescan()] [...] NetworkManager.wifi.scan request failed: not authorized
    ```

if version of KlipperScreen installed was previous than v0.3.8, then re-run the installer and reboot


??? Alternative workaround for network-manager

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
