# FBturbo failing with undefined symbol

in the system [log](../Troubleshooting.md) this appears:

!!! abstract "Log"
    ```sh
    xinit[948]: /usr/lib/xorg/Xorg: symbol lookup error: /usr/lib/xorg/modules/drivers/fbturbo_drv.so: undefined symbol: shadowUpdatePackedWeak
    ```

Your system doesn't seem compatible with the FBturbo driver that you have installed

Remove the fbturbo driver

```sh
sudo apt purge xserver-xorg-video-fbturbo
```
