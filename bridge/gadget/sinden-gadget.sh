#!/bin/bash
# Bring up / tear down the USB HID gadget that presents the bridge to the MiSTer as a
# Sinden Lightgun in joystick mode. Runs on the Cubie A7Z (root).
#
#   sinden-gadget.sh up      create+bind the gadget (stops the Radxa adbd gadget first)
#   sinden-gadget.sh down    unbind+remove it
#   sinden-gadget.sh status
#
# Descriptor: one Joystick application collection = 16 buttons + X/Y 16-bit 0..65535.
# Linux hid-input maps Button 1..16 in a Joystick collection to BTN_TRIGGER(0x120)..0x12F,
# which is what Main_MiSTer's Sinden quirk and Sinden's shipped .map files expect.
# Report (6 bytes, little-endian): [buttons lo][buttons hi][X lo][X hi][Y lo][Y hi]
set -euo pipefail

CONFIGFS=/sys/kernel/config/usb_gadget
NAME=${GADGET_NAME:-sinden}
G=$CONFIGFS/$NAME
UDC_NAME=${UDC_NAME:-$(ls /sys/class/udc | head -1)}
VID=${SINDEN_VID:-0x16c0}
PID=${SINDEN_PID:-0x0f01}          # 0f01 Blue P1, 0f02 Red, 0f38 Black/P1, 0f39 P2
SERIAL=${SINDEN_SERIAL:-MISTERSINDEN01}

REPORT_DESC='05 01 09 04 A1 01
             05 09 19 01 29 10 15 00 25 01 75 01 95 10 81 02
             05 01 09 30 09 31 15 00 27 FF FF 00 00 75 10 95 02 81 02
             C0'
REPORT_LENGTH=6

log() { echo "[sinden-gadget] $*"; }

up() {
    modprobe libcomposite
    modprobe usb_f_hid
    # Radxa's image binds an adb gadget (g1) to the only UDC; a UDC takes one gadget.
    if systemctl is-active --quiet adbd; then
        log "stopping adbd gadget"
        systemctl stop adbd
    fi
    for other in "$CONFIGFS"/*/; do
        [ -f "$other/UDC" ] || continue
        [ "$other" = "$G/" ] && continue
        if [ -n "$(cat "$other/UDC")" ]; then
            log "unbinding $(basename "$other") from UDC"
            echo "" > "$other/UDC" || true
        fi
    done
    if [ -d "$G" ]; then
        log "gadget exists; rebinding"
    else
        mkdir -p "$G"
        echo "$VID"   > "$G/idVendor"
        echo "$PID"   > "$G/idProduct"
        echo 0x0100   > "$G/bcdDevice"
        echo 0x0200   > "$G/bcdUSB"
        mkdir -p "$G/strings/0x409"
        echo "$SERIAL"                   > "$G/strings/0x409/serialnumber"
        echo "mister-sinden bridge"      > "$G/strings/0x409/manufacturer"
        echo "Sinden Lightgun"           > "$G/strings/0x409/product"
        mkdir -p "$G/configs/c.1/strings/0x409"
        echo "Lightgun"                  > "$G/configs/c.1/strings/0x409/configuration"
        echo 500                         > "$G/configs/c.1/MaxPower"
        mkdir -p "$G/functions/hid.usb0"
        echo 0              > "$G/functions/hid.usb0/protocol"
        echo 0              > "$G/functions/hid.usb0/subclass"
        echo $REPORT_LENGTH > "$G/functions/hid.usb0/report_length"
        printf "$(echo $REPORT_DESC | tr -d ' ' | sed 's/../\\x&/g')" > "$G/functions/hid.usb0/report_desc"
        ln -sf "$G/functions/hid.usb0" "$G/configs/c.1/"
    fi
    if [ "$(cat "$G/UDC")" = "$UDC_NAME" ]; then
        log "already bound to $UDC_NAME"
    else
        echo "$UDC_NAME" > "$G/UDC"
        log "bound to $UDC_NAME as $VID:$PID"
    fi
    sleep 0.5
    status
}

down() {
    [ -d "$G" ] || { log "no gadget"; return 0; }
    echo "" > "$G/UDC" 2>/dev/null || true
    rm -f "$G/configs/c.1/hid.usb0"
    rmdir "$G/configs/c.1/strings/0x409" "$G/configs/c.1" "$G/functions/hid.usb0" \
          "$G/strings/0x409" "$G" 2>/dev/null || true
    log "removed"
}

status() {
    if [ -d "$G" ]; then
        echo "gadget: $NAME  UDC=$(cat "$G/UDC")  id=$(cat "$G/idVendor"):$(cat "$G/idProduct")"
    else
        echo "gadget: not created"
    fi
    echo "udc:    $UDC_NAME state=$(cat /sys/class/udc/"$UDC_NAME"/state) speed=$(cat /sys/class/udc/"$UDC_NAME"/current_speed)"
    ls -la /dev/hidg* 2>/dev/null || echo "hidg:   none"
}

case "${1:-status}" in
    up) up ;; down) down ;; status) status ;;
    *) echo "usage: $0 up|down|status" >&2; exit 2 ;;
esac
