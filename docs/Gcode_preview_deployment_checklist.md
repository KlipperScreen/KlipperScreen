# G-code Preview Deployment Checklist

Verify the printer is running the expected branch and commit:

```bash
git -C /home/ender/KlipperScreen branch --show-current
git -C /home/ender/KlipperScreen rev-parse HEAD
```

Verify the installed preview constructor and preview-context wiring:

```bash
grep -n "def __init__" \
    /home/ender/KlipperScreen/panels/gcode_viewer.py

grep -RIn "preview_context" \
    /home/ender/KlipperScreen/panels/gcode_viewer.py \
    /home/ender/KlipperScreen/panels/gcodes.py \
    /home/ender/KlipperScreen/config/print_menu.conf
```

Verify the deployed file timestamps:

```bash
stat \
    /home/ender/KlipperScreen/panels/gcode_viewer.py \
    /home/ender/KlipperScreen/panels/gcodes.py \
    /home/ender/KlipperScreen/ks_includes/screen_panel.py
```

Verify compiled runtime translations:

```bash
stat \
    /home/ender/KlipperScreen/ks_includes/locales/rs/LC_MESSAGES/KlipperScreen.mo \
    /home/ender/KlipperScreen/ks_includes/locales/hr/LC_MESSAGES/KlipperScreen.mo
```
