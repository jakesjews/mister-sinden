#!/bin/bash
# Install/refresh the bridge on the Cubie. Run on the board from a checkout: sudo bridge/install.sh
set -euo pipefail
SRC=$(cd "$(dirname "$0")/.." && pwd)
DEST=/opt/mister-sinden
mkdir -p "$DEST"
rsync -a --delete --exclude .git "$SRC"/ "$DEST"/
cp "$DEST"/bridge/systemd/*.service /etc/systemd/system/
install -m 644 "$DEST"/bridge/driver/LightgunMono.exe.config /opt/sinden/LightgunMono.exe.config
install -m 644 "$DEST"/bridge/udev/99-sinden-bridge.rules /etc/udev/rules.d/99-sinden-bridge.rules
udevadm control --reload-rules
systemctl daemon-reload
systemctl disable --now adbd.service 2>/dev/null || true
systemctl enable sinden-gadget.service sinden-driver.service sinden-bridge.service
systemctl restart sinden-gadget.service sinden-driver.service sinden-bridge.service
sleep 2
systemctl --no-pager --no-legend status sinden-gadget sinden-driver sinden-bridge | grep -E "●|Active:"
