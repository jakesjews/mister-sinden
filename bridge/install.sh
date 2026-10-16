#!/bin/bash
# Install/refresh the bridge on the Cubie. Run on the board from a checkout: sudo bridge/install.sh
set -euo pipefail
SRC=$(cd "$(dirname "$0")/.." && pwd)
DEST=/opt/mister-sinden
UVC_NAME=uvcvideo-bandwidth-cap
UVC_VER=5.15.147
UVC_CAP=1000          # bytes per microframe a camera may reserve (Batocera's value for Sinden guns)

mkdir -p "$DEST"
rsync -a --delete --exclude .git "$SRC"/ "$DEST"/
cp "$DEST"/bridge/systemd/*.service /etc/systemd/system/
install -m 644 "$DEST"/bridge/driver/LightgunMono.exe.config /opt/sinden/LightgunMono.exe.config
install -m 644 "$DEST"/bridge/udev/99-sinden-bridge.rules /etc/udev/rules.d/99-sinden-bridge.rules
install -D -m 644 "$DEST"/bridge/journald/volatile.conf /etc/systemd/journald.conf.d/mister-sinden.conf
udevadm control --reload-rules
systemctl daemon-reload
systemctl restart systemd-journald
systemctl disable --now adbd.service 2>/dev/null || true
systemctl stop sinden-driver.service sinden-bridge.service 2>/dev/null || true

# Camera driver with a bandwidth cap, needed for two guns: each Sinden camera otherwise reserves
# the whole high-speed isochronous maximum and two of them starve the rest of the USB bus.
uvc_cap() {
    case "$(uname -r)" in 5.15.*) ;; *) echo "kernel $(uname -r) is not 5.15.x"; return 1 ;; esac
    [ -d "/lib/modules/$(uname -r)/build" ] || { echo "kernel headers for $(uname -r) are not installed"; return 1; }
    command -v dkms >/dev/null || { echo "dkms is not installed"; return 1; }
    if ! dkms status "$UVC_NAME/$UVC_VER" -k "$(uname -r)" 2>/dev/null | grep -q installed \
       || ! diff -rq "$DEST/bridge/uvcvideo-dkms" "/usr/src/$UVC_NAME-$UVC_VER" >/dev/null 2>&1; then
        dkms remove "$UVC_NAME/$UVC_VER" --all >/dev/null 2>&1 || true
        rm -rf "/usr/src/$UVC_NAME-$UVC_VER"
        cp -r "$DEST/bridge/uvcvideo-dkms" "/usr/src/$UVC_NAME-$UVC_VER"
        dkms install "$UVC_NAME/$UVC_VER" -k "$(uname -r)" --force >/tmp/sinden-dkms.log 2>&1 || { tail -5 /tmp/sinden-dkms.log; return 1; }
    fi
    echo "options uvcvideo bandwidth_cap=$UVC_CAP" > /etc/modprobe.d/sinden-uvcvideo.conf
    if [ "$(cat /sys/module/uvcvideo/parameters/bandwidth_cap 2>/dev/null)" != "$UVC_CAP" ]; then
        modprobe -r uvcvideo 2>/dev/null || true
        modprobe uvcvideo
    fi
    [ "$(cat /sys/module/uvcvideo/parameters/bandwidth_cap 2>/dev/null)" = "$UVC_CAP" ]
}
if uvc_cap; then
    echo "camera bandwidth cap: on ($UVC_CAP bytes per microframe)"
else
    echo "WARNING: could not install the camera bandwidth cap. One gun works without it; two guns need it."
fi

# The Cubie can lose power at any moment; make sure what was just installed is really on the card.
sync
systemctl enable sinden-gadget.service sinden-driver.service sinden-bridge.service
systemctl restart sinden-gadget.service sinden-driver.service sinden-bridge.service
sleep 2
systemctl --no-pager --no-legend status sinden-gadget sinden-driver sinden-bridge | grep -E "●|Active:" || true   # the driver waits until a gun is plugged in
