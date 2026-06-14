# Backends

KlipperScreen can be run under various backends like Xserver or Wayland compositors like Cage or Weston.

## X11 (Default)

Install by leaving the backend prompt blank or entering `X` during installation.

X11 is the default and most stable graphical backend for KlipperScreen.

**Pros:**
- Fully supported and well-tested
- Supports all features including DPMS (display power management)
- Compatible with both new and old/legacy displays

**Cons:**
- Heavy client-server architecture with more overhead than Wayland.
- Prone to rendering glitches (Screen tearing)
- It is nearing end-of-life, unknown availability in the future.

**Dependencies:**
```
xinit xinput x11-xserver-utils xserver-xorg-input-evdev xserver-xorg-input-libinput xserver-xorg-legacy xserver-xorg-video-fbdev
```

## Wayland

Install by entering `W` or `w` during the installation backend prompt.

**Pros:**
- Lower CPU/GPU overhead
- Frame perfect without tearing
- Modern architecture future-proof

**Cons:**
- Doesn't support legacy software framebuffers (needed for some old displays)
- Display power management is still being worked on KS


### Options to use the modern Wayland display protocol.

#### Cage

Cage is the most light weight compositor, but display rotation can be challenging.

**Dependencies:**
```
cage seatd
```

#### Weston

Weston is an alternative to cage if you have issues

it easy to do display rotation, and handles touch rotation too, but it has a bit more overhead.

**Dependencies:**
```
weston seatd
```

**Switch to Weston if you installed cage:**
```
sudo service KlipperScreen stop
sudo apt remove cage
sudo apt install weston seatd
```