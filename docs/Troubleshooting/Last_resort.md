# Last Resort to Make the Screen Work

If your screen never shows the console or bootup text during startup, it is typically due to an improperly installed screen. See [Physical Install Issues](Physical_Install.md) for more information.

![Boot Screen](../img/troubleshooting/boot.png)

If the screen shows the bootup text but ends with a blinking cursor or login prompt, and no matter what you tried in [Troubleshooting](../Troubleshooting.md) you can't make it work, then follow these steps:

1. **Install a Distro with a Desktop Environment**  
   [Click to learn how to check](./Desktop.md)

2. **Ensure Proper Functionality**  
   Make sure the screen is working properly, including both display and touch functionality.

3. **Deactivate the Desktop Environment for KlipperScreen**  
   To allow KlipperScreen to run exclusively, enter the following command in a terminal and press enter:
   ```sh
   sudo systemctl set-default multi-user.target && sudo reboot
   ```

4. **Reboot and Install KlipperScreen**  
   Wait for the system to reboot and then proceed to install KlipperScreen.

If it still doesn't work, or if you did something else to make it work and want to share your solution:

[Contact Us](../Contact.md)

Remember to share the logs, as they are crucial for troubleshooting.