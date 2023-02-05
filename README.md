# Nord KlipperScreen

This is a theme for [KlipperScreen](https://github.com/jordanruthe/KlipperScreen) which uses the [Nord](https://www.nordtheme.com/) colour palette.

## Installation

To install Nord KlipperScreen is pretty simple:

1) Download the contents of this repo
2) Copy the `nord` folder in the `styles` directory into the `styles` directory within your KlipperScreen install (`~/KlipperScreen/styles/`)
3) Overwrite the `base_panel.py`, `bed_level.py`, `console.py`, `extrude.py`, `fan.py`, `gcode_macros.py`, and `move.py` files in `~/KlipperScreen/panels/` with the ones in the `/panels` folder in this repo
4) Restart KlipperScreen

## Updates

### ⚠ A Quick Warning ⚠
- Using the following as an update source means that while you won't get Moonraker complaining that the installation is dirty, you are relying on this repository being up to date and that I have the free time ~~and remember~~ to upate this repo's files when a new KlipperScreen version is released.
- There's a much higher chance of something being broken or not working since I only have a slight clue as to what I'm doing. This was more of a personal project where I was playing around with the files' styling and layout so I'm really sorry but I can't gaurantee compatability across all platforms and devices (Though I haven't made any big changes so I don't see why it shouldn't work)

Since I ended up modifying a couple of the panel files within KlipperScreen the Moonraker interface will label your installation as "dirty" (Meaning that there were file changes compared to the status of the files on GitHub) if you have it using the official source repo as it's update source. To prevent that modify your `moonraker.conf` file as follows:

**Original**
```
[update_manager KlipperScreen]
type: git_repo
path: ~/KlipperScreen
origin: https://github.com/jordanruthe/KlipperScreen.git
env: ~/.KlipperScreen-env/bin/python
requirements: scripts/KlipperScreen-requirements.txt
install_script: scripts/KlipperScreen-install.sh
managed_services: KlipperScreen
```

**Updated**
```
[update_manager Nord-KlipperScreen]
type: git_repo
path: ~/KlipperScreen
origin: https://github.com/Orbitally/Nord-KlipperScreen.git
env: ~/.KlipperScreen-env/bin/python
requirements: scripts/KlipperScreen-requirements.txt
install_script: scripts/KlipperScreen-install.sh
managed_services: Nord-KlipperScreen
```

## Screenshots
### Klipper Disconnected
![Klipper Disconnected](https://user-images.githubusercontent.com/70914399/216843314-250d316d-da2c-4cbf-a91b-76f639ac6457.jpg)

### Main Menu
![Main Menu](https://user-images.githubusercontent.com/70914399/216844534-1e1bbad8-300f-47ff-9a02-e5ab35aeb88c.jpg)

### Actions
![Actions](https://user-images.githubusercontent.com/70914399/216843459-273497ea-c444-4958-a0fa-6a398d079027.jpg)

### Print Menu
![Print Menu](https://user-images.githubusercontent.com/70914399/216843347-3368c012-4057-4f60-a1ac-6dcc0ef8bd8e.jpg)

### Macros
![Macros](https://user-images.githubusercontent.com/70914399/216843358-5a08e1fc-2032-48c6-9d95-a7d73110bd50.jpg)

### Z-Calibrate
![Zed-Calibrate](https://user-images.githubusercontent.com/70914399/216843376-bec186e2-f10f-4d28-a9f1-93c5365434a1.jpg)

### Console
![Console](https://user-images.githubusercontent.com/70914399/216843430-bba41c07-fc02-425f-aade-296aef6af4e7.jpg)

## Enjoy!
I hope you like the theme and if you have any questions feel free to reach out and I'll do the best I can to answer them!
