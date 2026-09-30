# Radxa Cubie A7Z — verified hardware/kernel facts

Everything here was read off the running board on 2026-09-29 (not from marketing pages).

## Board / OS

| Item | Value |
|---|---|
| SoC | Allwinner A733 (`sun60iw2`), 2× Cortex-A76 @ 2.0 GHz + 6× Cortex-A55 @ 1.8 GHz |
| RAM | 2 GB (+ 1 GB zram swap) |
| Storage | 59.5 GB eMMC; root (`/dev/mmcblk0p3`) is only 11.7 GB — ~48 GB unpartitioned |
| OS | Debian 12 bookworm (Radxa image), vendor kernel `5.15.147-21.1-a733` |
| Network | `wlan0` only (AIC8800 USB WiFi on internal EHCI bus 3); no wired NIC detected |
| Boot | U-Boot + `/boot/extlinux/extlinux.conf`; overlays via `rsetup`, cmdline via `/etc/kernel/cmdline` + `u-boot-update` |
| Serial console | `ttyAS0` @ 115200 |
| Governor | `ondemand` on all cores (switch to `performance` for the driver) |

## USB topology

Two USB-C ports, mapped by reading `/sys/class/typec` and the device tree:

| Port | DT node | Controller | Type-C class | Role today |
|---|---|---|---|---|
| **OTG + power input** | `usbc0@10` (`allwinner,sunxi-otg-manager`) | UDC `4100000.udc-controller` (`allwinner,sunxi-udc`) for device mode; `ehci0/ohci0` for host mode | `typec/port1` (from `10.usbc0`) | `otg_role=usb_device`; power cable attached; VBUS detected through the AXP8191 PMIC (`usb_det_vbus_gpio=axp_ctrl`) |
| **USB 3.1 host** | `usbc2@12` (`allwinner,sunxi-plat-dwc3`) | dwc3 → `xhci-hcd.41.auto` (buses 1 & 2, USB 3.1) | `typec/port0` (ET7304 TCPC on i2c-14 @0x4e, DP alt-mode capable) | host, nothing attached |
| internal | `usbc1@11` | `ehci1/ohci1` (buses 3 & 4) | — | AIC8800 WiFi/BT |

Role switch for the OTG port: `/sys/devices/platform/soc@3000000/10.usbc0/otg_role`
(writable helpers alongside it: `usb_host`, `usb_device`, `usb_null`, `usb_otg`).

Consequence for the bridge: the port that faces the MiSTer (device mode) is the same
port that powers the board. Power must come from the MiSTer's hub port, a power-injecting
Y cable, or the GPIO header.

## Kernel features that matter (all verified)

- Gadget: `CONFIG_USB_GADGET=y`, `CONFIG_USB_CONFIGFS=m`, `CONFIG_USB_CONFIGFS_F_HID=y`,
  `CONFIG_USB_F_HID=m`, `CONFIG_USB_LIBCOMPOSITE=m`, plus `f_fs`, `ecm`, `ncm`, `acm`,
  `mass_storage`, `uac2`. `configfs` is mounted at `/sys/kernel/config`.
- Radxa ships an `adbd` gadget (`/sys/kernel/config/usb_gadget/g1`, `ffs.adb`, VID
  `0x18d1` PID `0x0100`) bound to the UDC via `adbd.service`
  (`/usr/lib/android-sdk/platform-tools/adbd-usb-gadget setup|activate|reset`).
  Our gadget replaces it.
- Input: `CONFIG_INPUT_EVDEV=y`, `CONFIG_INPUT_UINPUT=m` (`/dev/uinput` present after `modprobe uinput`).
- Camera: `CONFIG_USB_VIDEO_CLASS=m` (`uvcvideo` loads), `libv4l`, `v4l-utils` installed.
- Not present: `dwc2` gadget path is irrelevant (dwc2 is host-only here); no `g_ether`
  module but `usb_f_ecm`/`usb_f_ncm` exist if a USB network link is ever wanted.

## Software installed for this project

`mono-complete` 6.8.0.105 (Debian arm64), `libgdiplus`, `v4l-utils`, `evtest`,
`python3-evdev`, `python3-numpy`, `libinput-tools`, `tmux`, `htop`, `iperf3`.
Pre-existing: gcc/g++/cmake/git, `libevdev-dev`, `libv4l-0`, `libusb-1.0-0`, `libsdl2`.

## Access

- The Debian 12 image's defaults: user `radxa`, password `radxa`, SSH enabled, hostname
  `radxa-cubie-a7z` (reachable as `radxa-cubie-a7z.local` via mDNS).
- `radxa` is in `video`, `plugdev`, `sudo`, but not `input` or `dialout`; the bridge services run as root.
- `tools/cubie-ssh` wraps SSH (`CUBIE_HOST`, optional `CUBIE_KEY`).
