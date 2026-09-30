# Architecture: Sinden → Cubie A7Z → MiSTer

Goal: plug a Sinden Lightgun into a Radxa Cubie A7Z, plug the Cubie into a MiSTer, and have
**unmodified** MiSTer cores see a light gun. The RetroTINK 4K Pro draws the white border the
gun tracks. This document records what was verified (from source and from the running board)
and the design that follows from it.

## The two facts that shape everything

1. **The Sinden Linux driver never creates an input device.** It reads the gun's UVC camera,
   finds the white border, computes where the barrel points, and writes that position *back
   into the gun* over the gun's CDC-ACM serial port (7-byte frame `AA 28 Xhi Xlo Yhi Ylo BB`,
   0..32767 per axis, ~60 Hz). The gun's own firmware then reports position and buttons over
   its USB HID interfaces to whatever host the gun is plugged into. (Vendor `LightgunMono.exe`,
   decompiled; `sindenrs` clean-room driver does the same.)
2. **MiSTer has no light-gun protocol.** Main_MiSTer treats a device as a gun purely by
   USB VID/PID; the gun's `ABS_X/ABS_Y` are forwarded to the core as Player N's left analog
   stick (`UIO_ASTICK`, 8-bit signed), and each gun-capable core has an OSD option
   ("Zapper: Joy1", "Gun Control: Joy1", …) that reads that stick as beam position.
   Sinden IDs are already special-cased upstream
   ([Main_MiSTer `input.cpp` ~5440](https://github.com/MiSTer-devel/Main_MiSTer/blob/master/input.cpp),
   PR #968, Feb 2025): VID `0x16c0`/`0x16d0`, PID `0x0f01|0x0f02|0x0f38|0x0f39` →
   `QUIRK_LIGHTGUN`, hard-coded axis range **0..65535** (the device's own absinfo is ignored).

So the bridge does not need to invent anything: it runs the real driver on a fast ARM board and
re-presents the gun's HID output to the MiSTer as a Sinden-in-joystick-mode device.

## Data flow

```
                 ┌──────────────────────── Radxa Cubie A7Z ────────────────────────┐
                 │                                                                  │
 Sinden ──USB──▶ │ USB 3.1 port (dwc3/xHCI)                                         │
   gun           │   ├─ uvcvideo  /dev/video0   (MJPEG 640x480 @ 60 fps)            │
                 │   ├─ cdc-acm   /dev/ttyACM0  (driver ⇄ gun serial, 115200 8N1)   │
                 │   └─ usbhid    /dev/input/event*  "Unknown SindenLightgun ..."   │
                 │                    (one HID iface, 1 ms: mouse report = 3 btns +  │
                 │                     ABS_X/Y 0..32767; keyboard report = KEY_*)   │
                 │                                                                  │
                 │   [1] sinden driver ── camera → aim → serial write to gun ──▶ gun │
                 │   [2] hid-bridge   ── gun evdev → normalize → /dev/hidg0          │
                 │                                                                  │
                 │ USB 2.0 OTG port (sunxi UDC, VID 16c0 PID 0f01, 1 HID interface) │
                 └────────────────────────────┬─────────────────────────────────────┘
                                              │ USB
                                              ▼
                                   MiSTer (Main_MiSTer QUIRK_LIGHTGUN → core Joy1 analog)
                                              │ HDMI
                                              ▼
                                   RetroTINK 4K Pro (Masking Color = white border)
                                              │
                                              ▼
                                        TV ◀── gun camera sees the white border
```

- **[1] Driver.** v1 = vendor `LightgunMono.exe` (Pi5 folder of Sinden's V2.08b zip is the
  aarch64 build; runs under Debian's Mono 6.8, verified on the board). v2 = `sindenrs`
  (Rust, clean-room, 2–5 ms/frame, no Mono) once v1 works end to end.
- **[2] hid-bridge.** A small daemon that reads the gun's evdev nodes, rescales X/Y to
  0..65535, maps buttons to Button 1..16, and writes 6-byte reports to `/dev/hidg0`.
  Because the driver's output always round-trips through the gun's HID, the bridge is the
  same regardless of which driver is used. If the gun's own joystick-mode descriptor turns
  out to already be MiSTer-perfect, the bridge can become a raw hidraw → hidg passthrough.
- **Gadget.** `bridge/gadget/sinden-gadget.sh` builds the configfs gadget: one Joystick
  application collection, 16 buttons + X/Y 16-bit 0..65535. Linux/MiSTer maps Button 1..16
  of a Joystick collection to `BTN_TRIGGER (0x120)..0x12F`, matching Sinden's shipped MiSTer
  `.map` files (trigger 0x120, A 0x121, B 0x122, Select 0x123, D-pad 0x125–0x128).

### Pump action as an off-screen shot

MiSTer has no off-screen signal; cores infer it from edge coordinates (NES x≤1/≥254, PSX X or
Y == 0/255, SNES/MD similar). With `--pump-offscreen-shot` the bridge turns the pump into that
gesture: on pull it reports the top-left corner, then one report later the trigger; on release
it drops the trigger and restores the real aim. Games with off-screen reload therefore reload
on the pump with no per-core mapping, and the pump's own button bit is suppressed so nothing
double-fires. Remove the flag from `sinden-bridge.service` to get button 10 back.

### Pedal

The Sinden pedal is its own USB device: `16d0:1094 "Sinden Technology Ltd Sinden Pedal"`, a boot
keyboard that types `c` (reassignable with Sinden's serial tool) plus a CDC port. Plugged into
the Cubie next to the gun, the bridge grabs it and merges it into the gadget report — as joystick
button 11 by default (map it per core), or as a trigger alias, or as an off-screen shot
(`--pedal-as`). It is optional and hot-pluggable (rescanned every 3 s). Plugging it into the
MiSTer directly would make it a separate keyboard device, not a button on the gun.

Pedal serial protocol (decompiled from Sinden's pedal tool and Windows app; `tools/sinden-pedal.py`):
115200 8N1 with DTR/RTS asserted, single ASCII command bytes, single raw reply bytes, no framing.
`7` → key code, `9` → unique id, `5 <code>` set key (Arduino `Keyboard.h` codes), `8 <id>` set id,
`0` enter "attached to lightgun" mode (keyboard output stops; state answered by `4` → `'0'`/`'1'`),
`3` back to standalone keyboard mode. Sinden's Windows app sends `0` when it adopts a pedal and `3`
on exit, so a pedal last used there can arrive silent; `tools/sinden-pedal.py keyboard` fixes it.
Measured 2026-09-30: key `c` (99), id 0, keyboard mode.

### Hot-plug

The bridge exits when a gun node vanishes and systemd restarts it into its wait loop. The vendor
driver does not: it logs "Exit Lightgun1" and lingers, so `bridge/udev/99-sinden-bridge.rules`
restarts `sinden-driver.service` on every add/remove of a Sinden gun (matched on udev's
`PRODUCT=16c0/<pid>/…`, which is present on remove events too).

### Why one HID interface, joystick class

Main_MiSTer does not merge devices across USB interfaces, so a keyboard collection would be
enumerated as a separate device and could grab a player slot; a mouse collection
(`BTN_LEFT` + `ABS_X/Y`) makes MiSTer's kernel create `/dev/input/mouseN` and Main feeds it to
the core as PS/2 mouse motion in parallel ("aim is off" reports for Gun4IR/AimTrak in mouse
mode). Buttons 0x110–0x11F are diverted to mouse buttons and never reach the joystick mapper.
Everything therefore goes on one joystick collection with buttons ≥ 0x120.

### MiSTer-side requirements (unmodified cores)

- Main_MiSTer ≥ Feb 2025 (has the Sinden quirk). Nothing to patch.
- A button map so the device gets a player slot: Main only assigns a player number when a
  mapped button (code ≥ 0x120) is pressed. Sinden's `MiSTerSindenDriver` repo ships
  `Config/inputs/*_input_16c0_0f01_v3.map` for each gun core; copying them to
  `/media/fat/config/inputs/` avoids the "Define joystick buttons" dance.
- Core OSD: point the gun at Joy1 ("Zapper: Joy1" etc.). Off-screen is inferred by cores from
  edge coordinates (NES x≤1/≥254, y≤8/≥224; PSX X or Y == 0 or 255), so the bridge must
  emit true 0 / 65535 at the edges.
- Calibration: optional per core via F10 (stored as `<core>_gun_cal_16c0_0f01_v2.cfg`). The
  Sinden itself calibrates to the border, so this should rarely be needed.

### RetroTINK 4K border

There is no light-gun feature on the RT4K (only the 5X has one). The working recipe is
`Scaling/Crop → Masking Color` R/G/B = 31 (white) with `Show: Always`, then crop/scale the
image so the mask forms a border (Sinden guidance: ~2 % of width white, black outside it).
No serial command toggles the mask, but profiles load over serial, so "border on/off" is two
profiles switched through DonutShop (`POST http://donutshop.local/api/command`
`{"command":"prof load <path>"}`, RT4K fw ≥ 1.75).

## What the real gun looks like (measured 2026-09-29, black non-recoil, firmware 1.8)

- USB tree: internal hub `0424:2512` → camera `16d0:1095 SindenCamA` (UVC, MJPEG 640x480 and
  smaller sizes at 60 fps; YUYV 30 fps) + gun MCU `16c0:0f38` (CDC-ACM `ttyACM0` + one HID
  interface, interrupt interval 1 ms). The camera ID is not in sindenrs's table upstream
  (patched locally: `CAMERA_IDS += (0x16d0, 0x1095)`).
- HID report descriptor (mouse mode; firmware < 1.9 has no joystick mode):
  report 2 = boot keyboard (8 modifiers + 6 keys); report 1 = pointer with 3 buttons and
  X/Y `Logical 0..32767`, `Physical 0..32767`. Linux exposes it as two nodes,
  "Unknown SindenLightgun Keyboard" and "... Mouse" (ABS_X/ABS_Y 0..32767, BTN_LEFT/RIGHT/MIDDLE).
- Vendor driver on the A733: ~70–95 % of one core at 640x480/60 (Mono). Edge values
  (0 / 32767) are reported while no border is in view.

## Hardware and power

- **Cubie ports.** `usbc0` (USB-C, USB 2.0 OTG, sunxi UDC) is also the **5 V input**: its VBUS
  is wired straight to `VCC5V0_SYS` (schematic p.13, no diode/load switch), CC pull-downs
  make it a permanent sink. `usbc2` (USB-C, USB 3.1, ET7304 TCPC) is the host port; its
  VBUS is switched from the 5 V rail by an SGM2576 (~1 A budget).
- **Powering the bridge while it is a USB device.** Because VBUS and the 5 V rail are the
  same net, feeding 5 V on GPIO pins 2/4 would back-feed the MiSTer's hub. Options, in
  order of preference: (a) let the MiSTer's (externally powered) hub power it — the A7Z
  draws ~0.3 A idle, ~1.1 A stressed; (b) a data-only lead from the MiSTer plus separate
  5 V — only if the sunxi OTG manager tolerates no VBUS in device mode (untested);
  (c) an ideal-diode injector cable.
- **Gun power.** Non-recoil guns draw ~0.3 A (camera). Recoil solenoids exceed the USB 3
  port's ~1 A budget → powered hub between gun and Cubie.
- **Bench setup (no MiSTer).** Power on `usbc0` as today, gun on `usbc2`. To validate the
  gadget without the MiSTer, plug `usbc0` into a Mac: the Mac powers the board and enumerates
  the gadget.

## Latency budget (estimated, to be measured)

camera exposure ~8 ms + one frame period 16.7 ms + processing (2–10 ms) + serial to gun ~1 ms
+ gun HID poll ≤ 8 ms + bridge <1 ms + gadget poll 1–8 ms + Main_MiSTer/core. The RT4K adds
~2 ms of scaler delay that the camera sees. The Sinden's native MiSTer solution has the same
camera/serial/HID stages, so the bridge should feel identical while offloading the CPU work.

## Components in this repo

| Path | Purpose |
|---|---|
| `bridge/gadget/sinden-gadget.sh` | configfs gadget up/down/status (replaces Radxa's adbd gadget) |
| `bridge/hid-bridge/` | evdev → hidg translator daemon (to be written) |
| `bridge/driver/` | vendor driver config + service, later sindenrs (to be written) |
| `docs/cubie-a7z.md` | verified board facts |
| `tools/cubie-ssh` | SSH helper |

## Prior art consulted

- Sinden official MiSTer driver (MrLightgun/MiSTerSindenDriver): runs the driver *on* the
  DE10-Nano with a custom UVC-enabled kernel and border-patched cores. Our design avoids both.
- Batocera (`package/batocera/controllers/guns/sinden-guns`): udev-launched `mono-service`
  per gun, evsieve merges the gun's mouse+keyboard into one "Sinden lightgun" uinput device.
  Ships `uvcvideo bandwidth_cap=1000` for two guns on one controller.
- schlarpc/sindenrs: protocol notes (`docs/notes.md`), VID/PID table, joystick-mode enable
  (`sindenrs gun joystick-device enable`, firmware ≥ 1.9), firmware backup/flash.
