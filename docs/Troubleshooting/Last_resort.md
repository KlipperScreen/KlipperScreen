# Last resort to make the screen work

If the screen never shows the console or bootup text during startup, Then it's typically an improperly installed screen
See [Physical install issues](Physical_Install.md)

![boot](../img/troubleshooting/boot.png)

If the screen shows the bootup text, but ends in a blinking cursor or login prompt,
and no matter what you tried in [Troubleshooting](../Troubleshooting.md) you can't make it work, then do this:

1. Install a distro with a desktop enviromenment
2. Ensure that the screen is working properly (display and touch)
3. Install KlipperScreen
4. Run `sudo systemctl set-default multi-user.target`
5. Reboot

If it still doesn't work, or you did something else to make it work and want to share:

[Contact us](../Contact.md)

Remember to share the logs, as those aid a lot in the troubleshooting.
