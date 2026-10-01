#!/bin/sh
# Which Sinden guns are attached right now, and has that changed since the driver started?
#
#   sinden-guns.sh list     print the attached guns (USB port:device number), one per line
#   sinden-guns.sh record   remember the current set (run when the driver starts)
#   sinden-guns.sh settle   wait for the USB bus to settle; restart the driver if the set changed
#
# Sinden's driver only looks for guns when it starts, and it lingers after its gun is unplugged,
# so it has to be restarted when a gun comes or goes — but only then: restarting it while it is
# talking to a gun can upset the gun, and a re-plug produces several udev events.
STATE=/run/sinden-guns

list() {
    for d in /sys/bus/usb/devices/*; do
        [ -f "$d/idVendor" ] || continue
        [ "$(cat "$d/idVendor")" = "16c0" ] || continue
        case "$(cat "$d/idProduct")" in
            0f01|0f02|0f38|0f39) echo "$(basename "$d"):$(cat "$d/devnum")" ;;   # devnum changes on every re-plug
        esac
    done | sort
}

case "${1:-list}" in
    list)   list ;;
    record) list > "$STATE" ;;
    settle)
        sleep 3
        if [ "$(list)" != "$(cat "$STATE" 2>/dev/null)" ]; then
            echo "gun set changed: [$(cat "$STATE" 2>/dev/null | tr '\n' ' ')] -> [$(list | tr '\n' ' ')]; restarting the driver"
            systemctl restart sinden-driver.service
        else
            echo "gun set unchanged; nothing to do"
        fi
        ;;
    *) echo "usage: $0 list|record|settle" >&2; exit 2 ;;
esac
