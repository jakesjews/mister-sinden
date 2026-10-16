# uvcvideo with a bandwidth cap

`src/` is the `uvcvideo` driver from Linux 5.15.147 (`drivers/media/usb/uvc`, GPL-2.0) plus
`bandwidth-cap.patch`, which adds one module parameter:

    options uvcvideo bandwidth_cap=1000

A Sinden Lightgun's camera asks for the largest high-speed isochronous payload (3×1020 bytes per
microframe) at every resolution, far more than its MJPEG stream needs. One camera is fine. Two of
them on the Cubie's single USB 2.0 bus reserve most of it, the guns' own serial traffic starves, and
both guns disconnect. With the cap the driver picks a smaller alternate setting (2×640 bytes) and
both cameras still deliver 60 fps. Batocera carries the same idea as a kernel patch.

`bridge/install.sh` installs this through DKMS, so it is rebuilt automatically on kernel updates.
