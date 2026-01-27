# VNC

This article describes how to use KlipperScreen through a remote connection.

!!! warning
    The experience may not be equal to run KlipperScreen natively.
    Depending on the device or the network you may encounter performance degradation or other issues.

##  On the Host device:

The host device could be for example a Raspberry Pi

1. [First install KlipperScreen](Installation.md)
2. Install a vnc server package, for example:
    ```bash
    sudo apt install tigervnc-standalone-server
    ```

3. Create `~/KlipperScreen/scripts/launch_KlipperScreen.sh`:

    ```bash
    #!/bin/bash
    # Use display 10 to avoid clashing with local X server, if any
    Xtigervnc -rfbport 5900 -noreset -AlwaysShared -SecurityTypes none :10&
    DISPLAY=:10 $KS_XCLIENT&
    wait
    ```
    !!! tip
        To change resolution add: `-geometry 1280x720` to the arguments of Xtigervnc

4. Make the script executable
    ```bash
    chmod +x ~/KlipperScreen/scripts/launch_KlipperScreen.sh
    ```

5. Restart KlipperScreen or reboot the system:
    ```bash
    sudo systemctl restart KlipperScreen.service
    ```

## On the remote device:

Install a VNC viewer and  configure it to the ip of the host.


??? example "Example using an iPad"
    #### Example using an iPad
    * Install a VNC viewer for example: `RealVNC Viewer: Remote Desktop`
    * Open the VNC viewer app
    * Press "+" button at the top right
    * Enter IP address of your print host.
    * Press "Save"
    * Select "Interaction", select "Touch panel", go back
    * Press "Done"
    * Double-click on an icon with IP address you have just added.
    * VNC client will complain about unencrypted connection. Disable the warning and say "Connect"
    * Use or skip tutorial
    * Press the "Pin" icon to hide the panel.
    ##### Prevent unwanted rotation of UI
    * Go to `Settings` > `General` >  Set `Use side switch to` to `Lock Rotation`
    ##### Avoid accidentally switching between apps
    * Go to `Restrictions` > Set passcode > Enable restrictions.
    * Open
    * Triple-click "Home" button
    * Guided access pops up
    * Press "Start"
    * Now iPad is locked to VNC viewer until "Guided access" mode is disabled by triple-clicking "Home" button and entering the password.

??? example "Example using an Android device"
    #### Example using an Android device
    * Install a VNC viewer for example: `RealVNC Viewer: Remote Desktop`
    * Open the VNC viewer app
    * Press "+" button at the right
    * Enter IP address of your print host.
    * Press "Save"
    * Double-click on an icon with name or IP address you have just added.
    * VNC client may complain about unencrypted connection. Disable the warning and say "Connect"
    ##### Prevent unwanted rotation of UI
    * Lock the rotation using the buttons in the notification bar or in device Settings > Screen > Disable "Rotate automatically"

It's recommended to set Display timeout to never:

Also for X11 installs turn off DPMS:

![disable_dpms_poweroff](img/disable_dpms_poweroff.png)
