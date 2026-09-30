#!/bin/bash
# mister-sinden: set up a Radxa Cubie A7Z as a Sinden Lightgun bridge for MiSTer.
#
# On the Cubie (with internet), run:
#   curl -fsSL https://raw.githubusercontent.com/jakesjews/mister-sinden/main/install.sh | sudo bash
# or, from a checkout:   sudo ./install.sh
#
# Safe to run again (that is also how you update).
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/jakesjews/mister-sinden.git}"
SRC_DIR=/usr/local/src/mister-sinden
SINDEN_ZIP_URL="${SINDEN_ZIP_URL:-https://www.sindenlightgun.com/software/SindenLightgunSoftwareReleaseV2.08b.zip}"
SINDEN_APP_PATH="SindenLightgunSoftwareReleaseV2.08b/SindenLightgunLinuxSoftwareV2.05/ARMversion/Pi5/Lightgun/Application"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "Please run with sudo."; exit 1; }
[ "$(uname -m)" = "aarch64" ] || { echo "This installer is for the Radxa Cubie A7Z (arm64)."; exit 1; }

say "Installing packages (this takes a few minutes the first time)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends \
    mono-complete libgdiplus libsdl2-2.0-0 libjpeg62-turbo \
    python3 python3-evdev v4l-utils rsync unzip curl git ca-certificates

say "Getting mister-sinden"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$HERE" ] && [ -f "$HERE/bridge/install.sh" ]; then
    SRC_DIR="$HERE"
    echo "using this checkout: $SRC_DIR"
elif [ -d "$SRC_DIR/.git" ]; then
    git -C "$SRC_DIR" pull --ff-only
else
    git clone --depth 1 "$REPO_URL" "$SRC_DIR"
fi

say "Downloading the Sinden Lightgun driver from sindenlightgun.com"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fL --progress-bar -o "$TMP/sinden.zip" "$SINDEN_ZIP_URL"
mkdir -p /opt/sinden
unzip -o -q -j "$TMP/sinden.zip" "$SINDEN_APP_PATH/*" -d /opt/sinden
[ -f /opt/sinden/LightgunMono.exe ] || { echo "Sinden driver not found in the download"; exit 1; }

say "Installing the bridge services"
"$SRC_DIR/bridge/install.sh"

say "Done"
cat <<'MSG'
The Cubie is ready. Shut it down (sudo poweroff), then:
  - plug the Sinden (and pedal, via a hub) into the Cubie's USB-C 3.1 port
  - plug the Cubie's USB-C power port into the MiSTer's USB hub
It starts working about 30 seconds after the MiSTer powers it.
MSG
