## wpa_supplicant

The user is not allowed to control the interface

* Edit `/etc/wpa_supplicant/wpa_supplicant.conf` and add this line if it's not there:

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
```

* Run `cat /etc/group | grep netdev`

If your username is not listed under that line, you need to add it with the following command:

```sh
usermod -a -G netdev pi
```
(if your username is not 'pi' change 'pi' to your username)

Then reboot the machine:

```sh
systemctl reboot
```

!!! tip
    It's possible to just restart KlipperScreen and networking