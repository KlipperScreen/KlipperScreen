#!/bin/bash

XDG_RUNTIME_DIR="/run/user/$(id -u)"
export XDG_RUNTIME_DIR

SCRIPTPATH="$(dirname "$(realpath "$0")")"

if [ -f "$SCRIPTPATH/launch_KlipperScreen.sh" ]; then
    echo "Running $SCRIPTPATH/launch_KlipperScreen.sh"
    "$SCRIPTPATH/launch_KlipperScreen.sh"
    exit $?
fi

start_x11() {
    echo "Running KlipperScreen on X11"
    exec /usr/bin/xinit $KS_XCLIENT
}

start_cage() {
    echo "Running KlipperScreen on Cage"
    exec /usr/bin/cage -ds $KS_XCLIENT
}

start_weston() {
    echo "Running KlipperScreen on Weston"

    mkdir -p "$XDG_RUNTIME_DIR"
    chmod 700 "$XDG_RUNTIME_DIR"

    export WAYLAND_DISPLAY=wayland-0

    rm -f "$XDG_RUNTIME_DIR/wayland-0"
    rm -f "$XDG_RUNTIME_DIR/wayland-0.lock"

    /usr/bin/weston \
        --backend=drm-backend.so \
        --socket="$WAYLAND_DISPLAY" \
        --shell=kiosk-shell.so \
        --idle-time=0 &

    WESTON_PID=$!

    cleanup() {
        kill "$WESTON_PID" 2>/dev/null
        wait "$WESTON_PID" 2>/dev/null
    }

    trap cleanup EXIT

    for i in {1..50}; do
        if [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
            echo "Weston ready"
            break
        fi

        if ! kill -0 "$WESTON_PID" 2>/dev/null; then
            echo "Weston exited unexpectedly"
            exit 1
        fi

        sleep 0.1
    done

    exec $KS_XCLIENT
}

if [[ "$BACKEND" =~ ^[wW]$ ]]; then
    if command -v cage >/dev/null 2>&1; then
        start_cage
    elif command -v weston >/dev/null 2>&1; then
        start_weston
    else
        echo "No Wayland compositor found, exiting..."
        exit 1
    fi
else
    if command -v xinit >/dev/null 2>&1; then
        start_x11
    else
        echo "xinit not found, exiting..."
        exit 1
    fi
fi
