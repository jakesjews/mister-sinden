#!/usr/bin/env python3
"""Talk to a Sinden pedal (USB 16d0:1094) over its serial port. No dependencies.

Protocol (from Sinden's pedal tool / Windows lightgun app, decompiled): 115200 8N1, DTR+RTS on,
single ASCII command bytes, single raw reply bytes, no framing:
    7            -> 1 byte: current key code           9            -> 1 byte: unique id 0..9
    5 <code>     set key code (Arduino Keyboard.h)     8 <id>       set unique id
    0            "attached to lightgun" mode: keyboard output stops, presses answered by polling
    4            -> '0'/'1' pedal state (attached mode)  3            back to standalone keyboard mode

    tools/sinden-pedal.py [--port /dev/ttyACM1] status | keyboard | attached | poll | set-key c | set-id 0
"""
import argparse
import os
import sys
import termios
import time
import glob

KEYS = {**{chr(c): c for c in range(48, 58)}, **{chr(c): c for c in range(97, 123)}, **{chr(c): c for c in range(65, 91)},
        "return": 0xB0, "space": 32, "escape": 0xB1, "tab": 0xB3, "up": 0xDA, "down": 0xD9, "left": 0xD8, "right": 0xD7,
        **{f"f{i}": 0xC2 + i - 1 for i in range(1, 13)}}
NAMES = {v: k for k, v in KEYS.items()}


def find_port():
    for tty in sorted(glob.glob("/sys/class/tty/ttyACM*")):
        try:
            uevent = open(f"{tty}/device/uevent").read()
        except OSError:
            continue
        if "PRODUCT=16d0/1094/" in uevent:
            return "/dev/" + os.path.basename(tty)
    return None


def open_port(path):
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0                                    # iflag: raw
    attrs[1] = 0                                    # oflag
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL   # cflag
    attrs[3] = 0                                    # lflag: raw, no echo
    attrs[4] = attrs[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    import fcntl
    import struct
    TIOCMBIS, TIOCM_DTR, TIOCM_RTS = 0x5416, 0x002, 0x004
    fcntl.ioctl(fd, TIOCMBIS, struct.pack("I", TIOCM_DTR | TIOCM_RTS))
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def xfer(fd, tx, want=0, wait=0.15):
    termios.tcflush(fd, termios.TCIFLUSH)
    os.write(fd, tx)
    time.sleep(wait)
    out = b""
    while len(out) < want:
        try:
            out += os.read(fd, 64)
        except BlockingIOError:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("cmd", choices=["status", "keyboard", "attached", "poll", "set-key", "set-id"])
    ap.add_argument("arg", nargs="?")
    a = ap.parse_args()
    port = a.port or find_port()
    if not port:
        sys.exit("no Sinden pedal serial port found (16d0:1094)")
    fd = open_port(port)
    if a.cmd == "status":
        key = xfer(fd, b"7", 1); pid = xfer(fd, b"9", 1)
        k = key[0] if key else None
        print(f"port={port} key={k!r} ({NAMES.get(k, '?') if k is not None else 'no reply'}) id={pid[0] if pid else 'no reply'}")
    elif a.cmd == "keyboard":
        xfer(fd, b"3"); print("pedal set to standalone keyboard mode")
    elif a.cmd == "attached":
        xfer(fd, b"0"); print("pedal set to attached (polled) mode")
    elif a.cmd == "poll":
        xfer(fd, b"0")
        print("polling (Ctrl-C to stop); press the pedal")
        try:
            last = None
            while True:
                r = xfer(fd, b"4", 1, 0.02)
                s = r[:1]
                if s != last:
                    print(time.strftime("%H:%M:%S"), "pressed" if s == b"1" else "released" if s == b"0" else repr(r)); last = s
        except KeyboardInterrupt:
            pass
        finally:
            xfer(fd, b"3")
    elif a.cmd == "set-key":
        code = KEYS.get(a.arg.lower() if a.arg and len(a.arg) > 1 else a.arg)
        if code is None:
            sys.exit(f"unknown key {a.arg!r}; use a single character or one of {sorted(k for k in KEYS if len(k) > 1)}")
        xfer(fd, bytes([0x35, code])); print(f"key set to {a.arg!r} ({code})")
    elif a.cmd == "set-id":
        xfer(fd, bytes([0x38, int(a.arg)])); print(f"id set to {a.arg}")
    os.close(fd)


if __name__ == "__main__":
    main()
