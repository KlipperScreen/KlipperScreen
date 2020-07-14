# OctoScreen [![GitHub release](https://img.shields.io/github/release/Z-Bolt/OctoScreen.svg)](https://github.com/Z-Bolt/OctoScreen/releases) [![license](https://img.shields.io/github/license/Z-Bolt/OctoScreen.svg)]()

_OctoScreen_, LCD touch interface for our Octoprint based on GTK+3, that allows you to control your 3D Printer, like you can do with any [LCD panel](http://reprap.org/wiki/RepRapTouch), but using _OctoPrint_ and a Raspberry Pi. It's a _X application_ to be executed directly in the X Server without any windows
manager or browser, as _frontend of a [OctoPrint](http://octoprint.org) server_ in a Raspberry Pi
equipped with any [Touch Screen](https://www.waveshare.com/wiki/4.3inch_HDMI_LCD_(B)).

<img width="480" src="https://user-images.githubusercontent.com/390214/60487814-ef9d1a00-9ca8-11e9-9c48-31bf54a5488d.png" />
<img width="240" src="https://user-images.githubusercontent.com/390214/60277300-f4a74580-9905-11e9-8b88-f6cc35533c2a.png" /><img width="240" src="https://user-images.githubusercontent.com/390214/60277572-84e58a80-9906-11e9-8334-202544f0191d.png" />

### These are some of the functionalities supported:

- Print jobs monitoring.
- Temperature and Filament management.
- Jogging operations.
- Wifi connection management
- Toolchanger management tools

### How this is different from TouchUI?

[TouchUI](http://plugins.octoprint.org/plugins/touchui/), is an amazing plugin
for Octoprint, was created as a responsive design for access to OctoPrint,
from low resolution devices, such as smartphones, tablets, etc.

Executing TouchUI under a RPi w/TFT modules, presents two big problems,
first isn't optimized to be used with resistive touch screens with low resolutions
like 480x320 and second requires a browser to be access, consuming a lot of
resources.

This is the main reason because I develop this X application to be executed
in my 3d printer.

## [Roadmap](https://github.com/Z-Bolt/OctoScreen/projects/2)

Installation
------------

### Dependencies

*OctoScreen* is based on [Golang](golang.org), usually this means that is
dependency-less, but in this case [GTK+3](https://developer.gnome.org/gtk3/3.0/gtk.html)
is used, this means that GTK+3 libraries are required to be installed on
the system. Be sure that graphical environment is additionally installed.

If you are using `Raspbian` or any other `Debian` based distribution, required packages can
be installed using:

```sh
sudo apt-get install libgtk-3-0 xserver-xorg xinit x11-xserver-utils
```
Also you may need to install video drive, usually **no screens found** error indicates this. Please find manual here:
[https://github.com/ssvb/xf86-video-fbturbo/wiki/Installation](https://github.com/ssvb/xf86-video-fbturbo/wiki/Installation)


### Install from .deb package

The recommended way to install *OctoScreen* is use the `.deb` packages
from the [Releases](https://github.com/Z-Bolt/OctoScreen/releases) page. The packages
are available for Debian Stretch based distributions such as Raspbian and OctoPi.

For example for a Raspbian Stretch:
```sh
wget https://github.com/Z-Bolt/OctoScreen/releases/download/v2.5.1/octoscreen_2.5-1_armhf.deb
sudo dpkg -i octoscreen_2.5-1_armhf.deb
```

### Install from source

The compilation and packaging tasks are managed by the [`Makefile`](Makefile)
and backed on [Docker](Dockerfile). Docker is used to avoid installing any other
dependencies since all the operations are done inside of the container.

If you need to install docker inside `Raspbian` or any other linux distrubution
just run:

```sh
curl -fsSL get.docker.com -o get-docker.sh
sh get-docker.sh
```

> You can read more about this at [`docker-install`](https://github.com/docker/docker-install)

To compile the project, assuming that you already cloned this repository, just
execute the `build` target, this will generate in `build` folder all the binaries
and debian packages:

```sh
> make build
> ls -1 build/
```

If you are using `Raspbian` you can install any of the `.deb` generated packages.
If not, just use the compiled binary.

Configuration
-------------

### Basic Configuration

The basic configuration is handled via environment variables, if you are using
the `.deb` package you can configure it at `/etc/octoscreen/config`.

- `OCTOPRINT_CONFIG_FILE` - Location of the OctoPrint's config.yaml file. If empty the file will be searched at the `pi` home folder or the current user. Only used for locally installed OctoPrint servers.

- `OCTOPRINT_HOST` - OctoPrint HTTP address, example `http://localhost:5000`, if OctoPrint is locally installed will be read from the config file.

- `OCTOPRINT_APIKEY` - OctoScreen expects an [API key]( http://docs.octoprint.org/en/master/api/general.html) to be supplied. This API key can be either the globally configured one or a user specific one if “Access Control”. if OctoPrint is locally installed will be read from the config file.

- `OCTOSCREEN_STYLE_PATH` - Several themes are supported, and style configurations can be done through CSS. This variable defines the location of the application theme.

- `OCTOSCREEN_RESOLUTION` -  Resolution of the application, should be configured to the resolution of your screen. Optimal resolution for OctoScreen is no less than 800x480, so if the physical resolution of your screen is 480x320, it's recommended to set the software resolution 800x533. If you are using Raspbian you can do it by changing [`hdmi_cvt`](https://www.raspberrypi.org/documentation/configuration/config-txt/video.md) param in `/boot/config.txt` file.

### [Menu Configuration](https://github.com/Z-Bolt/OctoScreen/blob/master/docs/README.md)

### Custom controls and commands

Custom [controls](http://docs.octoprint.org/en/master/configuration/config_yaml.html#controls) to execute GCODE instructions and [commands](http://docs.octoprint.org/en/master/configuration/config_yaml.html#system) to execute shell commands can be defined in the `config.yaml` file.

The controls are limit to static controls without `inputs`.

License
-------

GNU Affero General Public License v3.0, see [LICENSE](LICENSE)

This project is a hard fork from [Octiprint-TFT](https://github.com/mcuadros/OctoPrint-TFT) created by [@mcuadros](https://github.com/mcuadros/OctoPrint-TFT)
