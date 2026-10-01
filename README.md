# mister-sinden

Play light gun games on MiSTer with your Sinden. The gun plugs into a small Radxa Cubie A7Z, the Cubie
plugs into your MiSTer, and your RetroTINK 4K draws the white border. It works with the regular MiSTer
cores, and the Sinden pedal works too.

```
Sinden (+ pedal) ── Cubie ── MiSTer ── RetroTINK 4K ── TV
```

## What you need

- [Radxa Cubie A7Z, 2 GB](https://www.amazon.com/dp/B0HGR1XPDS)
- [microSD card](https://www.amazon.com/dp/B08GY9NYRM)
- [USB-A to USB-C cable](https://www.amazon.com/dp/B0BPCBP15P), Cubie to MiSTer
- [USB-C to USB-A adapter](https://www.amazon.com/dp/B072V9CNTK) for the gun, or a
  [USB-C hub](https://www.amazon.com/dp/B07PY87TBD) if you also use the pedal
- A RetroTINK 4K, for the white border. Cores with their own Sinden border option (some arcade cores
  have one) don't need it.

Two guns? Use one Cubie per gun, each with its own card, cable and adapter.

The Cubie and gun run off the MiSTer's USB, so make sure your MiSTer's power supply has room for them
alongside everything else you have plugged in.

## Setup

1. **Flash the Cubie** with the [Debian 12 image for the Cubie A7Z](https://github.com/cuihuir/radxa-a7z-debian12/releases).
   Radxa's official image doesn't work. We used v0.3.3.

2. **Install.** Power the Cubie from either USB-C port. The one that lights it up is its power port;
   the other one is for the gun. Get it online, open a terminal on it (login `radxa`, password `radxa`)
   and run:
   ```
   curl -fsSL https://raw.githubusercontent.com/jakesjews/mister-sinden/main/install.sh | sudo bash
   ```
   When it's done, `sudo poweroff`. Running it again is safe, and it's also how you update.

3. **Plug it in.** Gun (and pedal) into the Cubie's gun port, and the Cubie's power port into the
   MiSTer's USB hub. From now on the Cubie starts with the MiSTer.

4. **White border.** Skip this for cores with their own Sinden border option. On the RetroTINK 4K, go
   to *Scaling/Crop → Masking Color*, set each of R, G and B to 31 to make the frame white, and set Show
   to *Always*. Then shrink the picture until the frame shows on all four sides.

5. **Map the gun** in MiSTer's *Define joystick buttons* using the gun's D-pad and its four side buttons.
   Keep it pointed at the screen while you map.

6. **Per core:** turn on the core's light gun option, then map the trigger (and the pedal, if you have
   one) in *Define buttons*, and save.

With two guns, do steps 5 and 6 with each gun.

## Playing

- **Press one of the gun's side buttons after loading a game.** That's what wakes the gun up in that game.
- The pump reloads by firing off-screen.
- Crosshair a little off? Press F10 and shoot the edges of the picture. Each core remembers its own.
- To fix which gun is which player, add `player_1_controller=` (or `player_2_controller=`) and the
  gun's ID to `MiSTer.ini`: `16c0_0f01` for a blue gun, `16c0_0f02` red, `16c0_0f38` black, `16c0_0f39`
  for a gun set to player 2.

## Troubleshooting

- **Gun does nothing:** press a side button, and check the core's light gun option is on and saved.
- **Nothing works at all:** check the Cubie's two cables aren't swapped, then unplug it and plug it back in.

Recoil Sindens haven't been tried yet, and neither has two guns.

The Sinden driver comes from sindenlightgun.com (the installer downloads it), and the Cubie image is by
[cuihuir](https://github.com/cuihuir/radxa-a7z-debian12). The nerdy details are in [docs/](docs/development.md).
