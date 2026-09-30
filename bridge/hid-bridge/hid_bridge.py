#!/usr/bin/env python3
"""evdev → USB HID gadget bridge for a Sinden Lightgun.

Reads the gun's own input nodes (created by usbhid when the gun is plugged into the Cubie),
normalises them into a single joystick report and writes it to the HID gadget function
(/dev/hidg0) that the MiSTer sees. See docs/architecture.md.

Report layout (must match bridge/gadget/sinden-gadget.sh): 6 bytes little-endian
    u16 buttons   bit n-1 = Button n  (Linux maps to BTN_TRIGGER + n-1 on the MiSTer)
    u16 x         0..65535, 0 = left edge of the white border
    u16 y         0..65535, 0 = top edge

Button numbering follows Sinden's shipped MiSTer .map files (evdev codes 0x120..0x129):
    1 trigger  2 front-left  3 rear-left  4 rear-right  5 front-right
    6 up  7 down  8 left  9 right  10 pump-action

A Sinden pedal (a USB keyboard that types 'c') plugged into the Cubie is folded in too:
--pedal-as button:11 (default) | trigger | offscreen. It is optional and hot-pluggable.

With --pump-offscreen-shot the pump action becomes an off-screen shot instead of a button:
while it is pulled the report shows the top-left corner (off-screen for every core's detector)
with the trigger held, so games with off-screen reload reload; releasing restores the aim.
"""
import argparse
import http.server
import json
import logging
import os
import select
import socketserver
import struct
import sys
import threading
import time

import evdev
from evdev import ecodes as E

log = logging.getLogger("hid-bridge")

# The gun's HID interfaces enumerate as several input nodes whose names all start with this.
GUN_NAME_PREFIX = "Unknown SindenLightgun"
# When the gun's joystick mode is enabled it adds a node with joystick-range buttons; prefer
# it when present because it is the same HID the vendor's MiSTer driver relies on.

# Mouse-mode gun (firmware < 1.9): the driver's button table (bridge/driver/LightgunMono.exe.config)
# makes every physical button emit a distinct key, mapped here to the numbering Sinden's own
# MiSTer per-core maps expect (see mister/config-inputs/README.md).
MOUSE_MODE_BUTTONS = {
    E.BTN_LEFT: 1,      # trigger
    E.KEY_1: 2,         # front-left   (A in Sinden's maps)
    E.KEY_2: 3,         # rear-left    (B)
    E.KEY_3: 4,         # rear-right   (Select)
    E.KEY_4: 5,         # front-right  (Start)
    E.KEY_UP: 6,
    E.KEY_DOWN: 7,
    E.KEY_LEFT: 8,
    E.KEY_RIGHT: 9,
    E.KEY_9: 10,        # pump action
}
# Joystick-mode node: BTN_TRIGGER (0x120) is Button 1, etc. — pass straight through.


def find_gun_devices(prefix=GUN_NAME_PREFIX):
    devs = []
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
        except OSError:
            continue
        if d.name.startswith(prefix):
            devs.append(d)
        else:
            d.close()
    return devs


PEDAL_NAME_HINTS = ("pedal",)          # matched case-insensitively against the evdev device name
PEDAL_IDS = {(0x16d0, 0x1094)}         # "Sinden Technology Ltd Sinden Pedal" (measured 2026-09-30)
PEDAL_VIDS = (0x16c0, 0x16d0, 0x2341)  # Sinden / Arduino-Leonardo style boards


def find_pedal_device(exclude_paths):
    """The Sinden pedal enumerates as a USB keyboard; find it by name, else by VID + keyboard shape."""
    for path in evdev.list_devices():
        if path in exclude_paths:
            continue
        try:
            d = evdev.InputDevice(path)
        except OSError:
            continue
        name = d.name.lower()
        keys = set(d.capabilities().get(E.EV_KEY, []))
        looks_like_kbd = E.KEY_C in keys and E.BTN_LEFT not in keys and E.ABS_X not in dict(d.capabilities().get(E.EV_ABS, []))
        if ((d.info.vendor, d.info.product) in PEDAL_IDS or any(h in name for h in PEDAL_NAME_HINTS)
                or (d.info.vendor in PEDAL_VIDS and looks_like_kbd and "sinden" not in name)):
            return d
        d.close()
    return None


class Report:
    __slots__ = ("buttons", "x", "y", "dirty", "last_buttons")

    def __init__(self):
        self.buttons = 0
        self.x = 32767
        self.y = 32767
        self.dirty = True
        self.last_buttons = 0

    def pack(self):
        return struct.pack("<HHH", self.buttons, self.x, self.y)


class PositionFeed:
    """Optional Server-Sent-Events feed of the latest report for tools/border-target.html."""

    def __init__(self, port):
        self.latest = b'{"buttons":0,"x":32767,"y":32767}'
        self.port = port
        feed = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path in ("/", "/index.html", "/border-target.html"):
                    page = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "tools", "border-target.html")
                    try:
                        body = open(page, "rb").read()
                    except OSError:
                        self.send_response(404); self.end_headers(); return
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path != "/events":
                    self.send_response(404); self.end_headers(); return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                last = None
                try:
                    while True:
                        cur = feed.latest
                        if cur is not last:
                            self.wfile.write(b"data: " + cur + b"\n\n"); self.wfile.flush(); last = cur
                        time.sleep(1 / 60)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.server = Server(("0.0.0.0", port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        log.info("position feed: http://<cubie>:%d/events", port)

    def publish(self, buttons, x, y):
        self.latest = json.dumps({"buttons": buttons, "x": x, "y": y}).encode()


class AxisScaler:
    """Rescale a device's ABS range to 0..65535 (MiSTer ignores our absinfo and assumes this)."""

    def __init__(self, absinfo):
        self.lo = absinfo.min
        self.span = max(1, absinfo.max - absinfo.min)

    def __call__(self, v):
        v = min(max(v, self.lo), self.lo + self.span)
        return (v - self.lo) * 65535 // self.span


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hidg", default="/dev/hidg0")
    ap.add_argument("--dry-run", action="store_true", help="log reports instead of writing hidg")
    ap.add_argument("--rate", type=float, default=0.0,
                    help="max report rate in Hz (0 = send on every change)")
    ap.add_argument("--sse-port", type=int, default=0,
                    help="serve the latest position as Server-Sent Events on this port (0 = off)")
    ap.add_argument("--pedal-as", default="button:11",
                    help="what a Sinden pedal press does: button:N (joystick button N), trigger, or offscreen (default button:11)")
    ap.add_argument("--pedal-key", default="KEY_C", help="evdev key the pedal types (Sinden default KEY_C)")
    ap.add_argument("--pump-offscreen-shot", action="store_true",
                    help="pump action = off-screen shot (trigger at the top-left corner) instead of button 10")
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    while True:
        devs = find_gun_devices()
        if devs:
            break
        log.info("waiting for %s* input devices", GUN_NAME_PREFIX)
        time.sleep(2)

    scalers = {}
    joystick_node = None
    for d in devs:
        caps = d.capabilities(absinfo=True)
        abs_caps = dict(caps.get(E.EV_ABS, []))
        keys = set(caps.get(E.EV_KEY, []))
        if E.ABS_X in abs_caps and E.ABS_Y in abs_caps:
            scalers[d.fd] = (AxisScaler(abs_caps[E.ABS_X]), AxisScaler(abs_caps[E.ABS_Y]))
        if E.BTN_TRIGGER in keys or E.BTN_JOYSTICK in keys:
            joystick_node = d
        log.info("gun node %s '%s' abs=%s keys=%d%s", d.path, d.name,
                 {E.ABS[c]: (a.min, a.max) for c, a in abs_caps.items() if c in (E.ABS_X, E.ABS_Y)},
                 len(keys), "  [joystick mode]" if d is joystick_node else "")
        try:
            d.grab()          # keep the gun from also acting as a mouse/keyboard on the Cubie
        except OSError as e:
            log.warning("grab %s failed: %s", d.path, e)

    hidg = None if args.dry_run else os.open(args.hidg, os.O_WRONLY | os.O_NONBLOCK)
    feed = PositionFeed(args.sse_port) if args.sse_port else None
    rep = Report()                       # physical state: real aim + real buttons
    fds = {d.fd: d for d in devs}
    min_interval = 1.0 / args.rate if args.rate > 0 else 0.0
    st = {"last_sent": 0.0, "sent": 0, "host_ok": None}   # None unknown, True writes succeed, False no host
    pump_held = False
    TRIGGER_BIT, PUMP_BIT = 1 << 0, 1 << 9
    OFFSCREEN = (0, 0)

    # optional pedal: its key becomes a joystick button, the trigger, or an off-screen shot
    pedal_key = getattr(E, args.pedal_key)
    pedal_mode, pedal_bit = args.pedal_as, 0
    if pedal_mode.startswith("button:"):
        pedal_bit = 1 << (int(pedal_mode.split(":")[1]) - 1)
        pedal_mode = "button"
    elif pedal_mode not in ("trigger", "offscreen"):
        ap.error("--pedal-as must be button:N, trigger or offscreen")
    pedal = None
    pedal_next_scan = 0.0
    gun_paths = {d.path for d in devs}

    def emit(buttons, x, y):
        data = struct.pack("<HHH", buttons, x, y)
        if hidg is None:
            log.info("report btn=%04x x=%5d y=%5d", buttons, x, y)
        else:
            try:
                os.write(hidg, data)
                if st["host_ok"] is not True:
                    log.info("host is polling the gadget; reports flowing")
                    st["host_ok"] = True
            except BlockingIOError:
                log.debug("hidg not ready (host not polling yet)")
            except OSError as e:
                # ESHUTDOWN (108) = gadget not connected to a host; log the transition only
                if st["host_ok"] is not False:
                    log.warning("no USB host on the gadget (%s); reports dropped until one appears", e)
                    st["host_ok"] = False
        if feed:
            feed.publish(buttons, x, y)
        st["last_sent"] = time.monotonic()
        st["sent"] += 1
        if args.verbose and st["sent"] % 600 == 0:
            log.debug("%d reports sent", st["sent"])

    def flush():
        """Send the current logical state (real aim, or the off-screen shot while the pump is held)."""
        if pump_held:
            emit((rep.buttons | TRIGGER_BIT) & ~PUMP_BIT, *OFFSCREEN)
        else:
            emit(rep.buttons, rep.x, rep.y)
        rep.dirty = False
        rep.last_buttons = rep.buttons

    def attach_pedal():
        nonlocal pedal, pedal_next_scan
        pedal_next_scan = time.monotonic() + 3.0
        d = find_pedal_device(gun_paths)
        if d is None:
            return
        try:
            d.grab()
        except OSError as e:
            log.warning("grab pedal %s failed: %s", d.path, e)
        pedal = d
        fds[d.fd] = d
        log.info("pedal %s '%s' (%04x:%04x) → %s", d.path, d.name, d.info.vendor, d.info.product, args.pedal_as)

    def detach_pedal():
        nonlocal pedal
        if pedal is None:
            return
        fds.pop(pedal.fd, None)
        try:
            pedal.close()
        except OSError:
            pass
        log.info("pedal went away")
        pedal = None

    attach_pedal()
    log.info("bridging %d node(s) → %s%s", len(devs), args.hidg if hidg is not None else "(dry run)",
             "  [pump = off-screen shot]" if args.pump_offscreen_shot else "")
    while True:
        if pedal is None and time.monotonic() >= pedal_next_scan:
            attach_pedal()
        ready, _, _ = select.select(list(fds), [], [], 1.0)
        for fd in ready:
            d = fds.get(fd)
            if d is None:
                continue
            try:
                events = list(d.read())
            except OSError as e:
                if d is pedal:
                    detach_pedal()
                    continue
                log.error("gun node %s went away (%s); exiting for restart", d.path, e)
                return 1
            if d is pedal:
                for ev in events:
                    if ev.type != E.EV_KEY or ev.code != pedal_key or ev.value not in (0, 1):
                        continue
                    if pedal_mode == "button":
                        new = (rep.buttons | pedal_bit) if ev.value else (rep.buttons & ~pedal_bit)
                    elif pedal_mode == "trigger":
                        new = (rep.buttons | TRIGGER_BIT) if ev.value else (rep.buttons & ~TRIGGER_BIT)
                    else:   # offscreen: same choreography as the pump
                        if ev.value:
                            pump_held = True
                            emit(rep.buttons & ~TRIGGER_BIT & ~PUMP_BIT, *OFFSCREEN)
                            time.sleep(0.012)
                        else:
                            emit(rep.buttons & ~TRIGGER_BIT & ~PUMP_BIT, *OFFSCREEN)
                            pump_held = False
                            time.sleep(0.012)
                        flush()
                        continue
                    if new != rep.buttons:
                        rep.buttons = new
                        flush()
                continue
            for ev in events:
                if ev.type == E.EV_ABS and fd in scalers:
                    if ev.code == E.ABS_X:
                        v = scalers[fd][0](ev.value)
                        if v != rep.x:
                            rep.x, rep.dirty = v, True
                    elif ev.code == E.ABS_Y:
                        v = scalers[fd][1](ev.value)
                        if v != rep.y:
                            rep.y, rep.dirty = v, True
                elif ev.type == E.EV_KEY and ev.value in (0, 1):
                    if d is joystick_node and E.BTN_JOYSTICK <= ev.code < E.BTN_JOYSTICK + 16:
                        n = ev.code - E.BTN_JOYSTICK + 1
                    else:
                        n = MOUSE_MODE_BUTTONS.get(ev.code)
                    if n is None:
                        log.debug("unmapped key %s=%d", E.KEY.get(ev.code, ev.code), ev.value)
                        continue
                    bit = 1 << (n - 1)
                    new = (rep.buttons | bit) if ev.value else (rep.buttons & ~bit)
                    if new == rep.buttons:
                        continue
                    rep.buttons, rep.dirty = new, True
                    if args.pump_offscreen_shot and bit == PUMP_BIT:
                        if ev.value:
                            # off-screen first, then the trigger edge one report later, so the core
                            # latches the off-screen position before it sees the press
                            pump_held = True
                            emit(rep.buttons & ~TRIGGER_BIT & ~PUMP_BIT, *OFFSCREEN)
                            time.sleep(0.012)
                            flush()
                        else:
                            emit(rep.buttons & ~TRIGGER_BIT & ~PUMP_BIT, *OFFSCREEN)   # release the shot off-screen
                            pump_held = False
                            time.sleep(0.012)
                            flush()                                                 # back to the real aim
                elif ev.type == E.EV_SYN and rep.dirty:
                    # rate-limit pure motion; button changes always go out immediately
                    if min_interval and time.monotonic() - st["last_sent"] < min_interval and rep.buttons == rep.last_buttons:
                        continue
                    flush()


if __name__ == "__main__":
    sys.exit(main() or 0)
