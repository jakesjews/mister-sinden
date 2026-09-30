# mister-sinden

Use a Sinden Lightgun with **unmodified MiSTer FPGA cores** by putting a Radxa Cubie A7Z
between the gun and the MiSTer:

```
Sinden ──USB──▶ Cubie A7Z (runs the Sinden driver, re-emits the gun as a USB HID joystick)
                   └──USB──▶ MiSTer ──HDMI──▶ RetroTINK 4K Pro (draws the white border) ──▶ TV
```

MiSTer already recognises Sinden's USB IDs as a light gun (since Feb 2025) and treats the
device's X/Y as Player 1's analog stick, which every gun-capable core reads as beam position.
Sinden's own MiSTer solution instead runs the camera processing on the DE10-Nano with a
patched kernel and border-patched cores; this project moves that work to the Cubie so the
MiSTer stays stock and the RT4K supplies the border.

Read [`docs/architecture.md`](docs/architecture.md) for the design and the evidence behind
it, and [`docs/cubie-a7z.md`](docs/cubie-a7z.md) for the board facts.

## Layout

```
bridge/gadget/sinden-gadget.sh   configfs USB gadget: VID 16c0 PID 0f01, one joystick HID
bridge/hid-bridge/hid_bridge.py  gun evdev → /dev/hidg0 report translator (+ SSE position feed, pump = off-screen shot)
bridge/systemd/*.service         gadget / driver / bridge units;  bridge/install.sh deploys to /opt/mister-sinden
bridge/udev/99-sinden-bridge.rules  restart the driver when a gun is plugged/unplugged
mister/config-inputs/            MiSTer map files (global + per-core) for the gadget's VID/PID
docs/                            architecture + hardware notes
tools/border-target.html         bench target: white border + crosshairs, shows the live aim from the feed
tools/sinden-pedal.py            pedal serial tool: status / keyboard / attached / poll / set-key / set-id
tools/calibrate-offsets.py       four-corner calibration → driver OffsetX/Y values
tools/cubie-ssh, tools/mister-ssh  ssh helpers
```

## Status

- [x] Cubie: gadget mode verified, `/dev/hidg0` gadget bound as a Sinden
- [x] Cubie: vendor driver (Mono, aarch64 Pi5 build) loads and runs
- [x] Gun on the Cubie: camera + serial + evdev nodes enumerated; driver handshakes (fw 1.8), positions echo back through the gun's HID into the bridge
- [x] systemd units: gadget → driver → bridge, survive reboot and gun hot-plug
- [ ] Tracking verified against a white border (tools/border-target.html)
- [x] MiSTer enumerates the gadget as a Sinden joystick; global + per-core maps installed (`mister/config-inputs/`)
- [x] NES core: Zapper aims and fires with an unmodified core
- [x] All 10 gun inputs (trigger, pump, 4 side buttons, D-pad) arrive as distinct joystick buttons
- [x] MegaDrive core works; per-core quirks: each core needs its own OSD gun options (NES: Zapper Trigger = Joystick)
- [x] Pump action = off-screen shot (bridge `--pump-offscreen-shot`, on by default in the unit)
- [x] Sinden pedal (`16d0:1094`, a USB keyboard typing `c`) folded into the gadget by the bridge (`--pedal-as button:11|trigger|offscreen`), hot-pluggable
- [x] Gun hot-plug: udev rule restarts the vendor driver on add/remove (it otherwise hangs after an unplug)
- [ ] SNES/PSX/SMS/7800 cores checked
- [ ] RetroTINK 4K masking-colour border profiles via DonutShop
- [ ] Native driver (sindenrs) replacing Mono
