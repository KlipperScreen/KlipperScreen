# Troubleshooting Framebuffer Issues

Here are some solutions if this line is in the logs:
```sh
(EE) Cannot run in framebuffer mode. Please specify busIDs for all framebuffer devices
```

!!! abstract "Raspberry Pi"

    This has been known to happen on RaspberryOS Bookworm Lite on Pi5.

    Later versions of the OS fixed the issue.

    ```sh
    sudo nano /etc/X11/xorg.conf.d/99-v3d.conf
    ```
    Paste this into the file:
    ```sh
    Section "OutputClass"
      Identifier "vc4"
      MatchDriver "vc4"
      Driver "modesetting"
      Option "PrimaryGPU" "true"
    EndSection
    ```
    Reboot.

!!! abstract "Generic"

    This will heavily vary with different hardware. Find the correct busID and create a config like:

    ```sh
    sudo nano /etc/X11/xorg.conf.d/99-busid.conf
    ```
    Paste this into the file:
    ```sh
    Section "Device"
        Identifier "Card0"
        Driver "fbdev"
        BusID "pci:1:0:0"
    EndSection
    ```
    Where the busID in this example is the first pci card. You will have to find the identifier and id of the video output device using tools like:
    ```sh
    lspci
    ```
    Or sometimes with:
    ```sh
    lshw
    ```

If you find a solution not listed here, please consider contributing with the information.
