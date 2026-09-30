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

## Using it on the MiSTer

**Hardware.** Plug the Sinden **and the pedal** into a small USB hub on the Cubie's USB-C 3.1 port —
any USB 2.0+ hub with two free ports works, e.g. the [UGREEN USB-C to 4× USB-A hub](https://www.amazon.com/dp/B07PY87TBD). The
Cubie's other USB-C port (power/OTG) goes to the MiSTer's USB hub. The gun and pedal reach the
MiSTer as one device (a Sinden light gun), so MiSTer's own menus do all the setup — no files.

1. **Once, in the MiSTer main menu:** System Settings → *Define joystick buttons*, using the gun.
   D-pad for the directions, side buttons for A / B / Select / Start, space bar on a keyboard to skip
   everything else. Hold the gun still (point it at the screen) while mapping, or its aim can be
   captured as a stick. This lets the gun take a player slot in every core.
2. **Once per core:** load it, set its gun options in the OSD, then *Define <core> buttons* and press
   the trigger for the gun button and the pedal wherever you want it. Save settings.
3. Press a gun button once after loading a core so the gun is Player 1, and play.

| Core | OSD settings | Trigger → | Pedal (suggested) |
|---|---|---|---|
| NES | Peripheral: **Zapper(Joy1)**, Zapper Trigger: **Joystick** | Zapper/Vaus Btn | B |
| SNES | Super Scope: **Joy1**, Super Scope Btn: **Joy**, Gun Type: Super Scope / Justifier | A (SS Fire) | B (SS Cursor) |
| MegaDrive / MegaCD | Gun Control: **Joy1**, Gun Fire: **Joy** | A | B (reload) |
| SMS | Gun Control: **Joy1**, Gun Fire: **Joy** | Fire 1 | Fire 2 |
| PSX | Pad1: **GunCon** (or Justifier) | O (Gun Fire) | Start (Gun A) — takes cover in Time Crisis; Gun B pauses it |
| Atari 7800 | Port1 Input: **Lightgun**, Gun Control: **Joy1**, Gun Fire: **Joy** | Fire1 | Fire2 |

The pump action is an off-screen shot (reload) everywhere, no mapping needed. Optional:
`player_1_controller=16c0_0f01` in `MiSTer.ini` makes the gun Player 1 whenever it is pressed, which
games like Time Crisis require.

## Layout

```
bridge/gadget/sinden-gadget.sh   configfs USB gadget: VID 16c0 PID 0f01, one joystick HID
bridge/hid-bridge/hid_bridge.py  gun evdev → /dev/hidg0 report translator (+ SSE position feed, pump = off-screen shot)
bridge/systemd/*.service         gadget / driver / bridge units;  bridge/install.sh deploys to /opt/mister-sinden
bridge/udev/99-sinden-bridge.rules  restart the driver when a gun is plugged/unplugged
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
- [x] MiSTer enumerates the gadget as a Sinden joystick; set up with MiSTer's own Define-buttons menus (no files)
- [x] NES core: Zapper aims and fires with an unmodified core
- [x] All 10 gun inputs (trigger, pump, 4 side buttons, D-pad) arrive as distinct joystick buttons
- [x] MegaDrive core works; per-core quirks: each core needs its own OSD gun options (NES: Zapper Trigger = Joystick)
- [x] Pump action = off-screen shot (bridge `--pump-offscreen-shot`, on by default in the unit)
- [x] Sinden pedal on a hub on the Cubie: merged by the bridge into the gun as button 11 (bridge also switches the pedal to keyboard mode on attach); verified end to end on the Cubie through a 4-port USB 2.0 hub
- [ ] Pedal mapped in a core's Define-buttons wizard (should work: it is a button of the gun device)
- [x] Gun hot-plug: udev rule restarts the vendor driver on add/remove (it otherwise hangs after an unplug)
- [ ] SNES/PSX/SMS/7800 cores checked
- [ ] RetroTINK 4K masking-colour border profiles via DonutShop
- [ ] Native driver (sindenrs) replacing Mono
