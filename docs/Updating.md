# Updating

## Using Moonraker update manager

!!! info
    This method will not work if KlipperScreen and Moonraker are on different Hosts

For this to work, KlipperScreen should be added to moonraker.conf as explained in the installation instructions.
[moonraker-configuration](Installation.md/#moonraker-configuration)

Then you can update using the System panel:

![system-panel-screenshot](img/panels/system.png)

or from any UI that supports updating from moonraker.


## Using KIAUH

Same as in the installation instructions, but select update instead of install

![KIAUH-screenshot](img/install/KIAUH.png)


## Manual update

```sh
cd ~/KlipperScreen
git pull
source ~/.KlipperScreen-env/bin/activate
pip --disable-pip-version-check install -r ~/KlipperScreen/scripts/KlipperScreen-requirements.txt
sudo service KlipperScreen restart
```


