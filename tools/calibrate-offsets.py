#!/usr/bin/env python3
"""Turn trigger pulls at the game image's corners into Sinden driver offsets.

Run it, then on the TV aim at the four corners of the *game image* (not the white border)
and pull the trigger once at each, in the order printed. The script reads the bridge's
position feed and prints OffsetX / OffsetY / OffsetXRatio / OffsetYRatio for
LightgunMono.exe.config, so the driver reports coordinates relative to the game image
and MiSTer needs no F10 calibration.

    tools/calibrate-offsets.py [--feed http://192.168.50.212:8765/events]
"""
import argparse
import json
import sys
import urllib.request

ORDER = ["top-left", "top-right", "bottom-right", "bottom-left"]


def shots(feed):
    prev = 0
    with urllib.request.urlopen(feed) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            d = json.loads(line[5:])
            if d["buttons"] & 1 and not prev & 1:
                yield d["x"] / 65535 * 100, d["y"] / 65535 * 100
            prev = d["buttons"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed", default="http://192.168.50.212:8765/events")
    args = ap.parse_args()
    print(f"Listening on {args.feed}. Shoot the game image's corners: {', '.join(ORDER)}.")
    pts = []
    for (x, y), name in zip(shots(args.feed), ORDER):
        print(f"  {name:13s} x={x:5.1f}%  y={y:5.1f}%")
        pts.append((x, y))
        if len(pts) == 4:
            break
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    left, right = (x0 + x3) / 2, (x1 + x2) / 2
    top, bottom = (y0 + y1) / 2, (y2 + y3) / 2
    print("\nGame image inside the tracked frame:")
    print(f"  left {left:.1f}%  right {right:.1f}%  top {top:.1f}%  bottom {bottom:.1f}%")
    print("\nLightgunMono.exe.config values (bridge/driver/LightgunMono.exe.config):")
    print(f'  <add key="OffsetX" value="{left:.2f}"/>')
    print(f'  <add key="OffsetY" value="{top:.2f}"/>')
    print(f'  <add key="OffsetXRatio" value="{(right - left) / 100:.4f}"/>')
    print(f'  <add key="OffsetYRatio" value="{(bottom - top) / 100:.4f}"/>')


if __name__ == "__main__":
    sys.exit(main())
