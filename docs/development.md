# Development notes

See [architecture.md](architecture.md) for how it works and why, and [cubie-a7z.md](cubie-a7z.md)
for verified board facts.

## Layout

```
install.sh                       one-command Cubie installer (packages, Sinden driver download, services)
bridge/install.sh                deploys this checkout to /opt/mister-sinden and (re)starts the services
bridge/gadget/sinden-gadget.sh   configfs USB gadget: VID 16c0 PID 0f01, one joystick HID
bridge/hid-bridge/hid_bridge.py  gun evdev → /dev/hidg0 translator (+ SSE position feed, pump = off-screen
                                 shot, pedal merged as button 11)
bridge/driver/                   managed LightgunMono.exe.config (unique key per gun button)
bridge/systemd/*.service         gadget / driver / bridge units
bridge/udev/99-sinden-bridge.rules  restart the driver when a gun is plugged/unplugged
tools/border-target.html         bench target: white border + crosshairs, live aim from the feed
tools/sinden-pedal.py            pedal serial tool: status / keyboard / attached / poll / set-key / set-id
tools/calibrate-offsets.py       four-corner calibration → driver OffsetX/Y values
tools/cubie-ssh, tools/mister-ssh  ssh helpers
```

## Status

- [x] Cubie: USB gadget presents the bridge to the MiSTer as a Sinden (`16c0:0f01`) joystick
- [x] Sinden's own aarch64 driver (V2.08b "Pi5" build) runs under Mono on the Cubie
- [x] Tracking verified against a white-bordered screen; aim within ~2–3 % at centre and corners
- [x] Boot- and hot-plug-persistent (systemd units + udev driver restart)
- [x] NES, Mega Drive, PSX (Time Crisis) and arcade gun games on stock cores
- [x] All 10 gun inputs as distinct joystick buttons; pump = off-screen shot (reload verified on Mega Drive)
- [x] Sinden pedal through a hub on the Cubie, merged into the gun as button 11; mappable in core wizards
- [x] One-command installer, verified by re-running on an installed Cubie (Debian 12 image v0.3.3)
- [ ] Installer run on a freshly flashed card (clone-from-GitHub path)
- [ ] SNES, SMS, Atari 7800 cores checked
- [ ] Recoil guns, second gun
- [ ] Native driver (sindenrs) replacing Mono
