# Enclosure (FreeCAD)

`enclosure.py` is a parametric Part-workbench script. It runs headless (no FreeCAD window):

```bash
cd hardware/freecad
"/c/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" enclosure.py     # about 2 minutes
```

Every dimension is a constant at the top of the script. Change it, run again, and everything in
`exports/` is rebuilt. The script stops with an error if a part is invalid, is not one solid, does
not fit the printer bed, has a feature under 1.2 mm, or if the electronics would hit the box or lid.

## Output (`exports/`)

| File | What |
|---|---|
| `<part>.stl` | for the slicer, already in print orientation |
| `<part>.step` | for other CAD tools (same orientation) |
| `enclosure.FCStd` | all parts, lid on the box and small parts beside it: open in FreeCAD to look around |
| `png/*.png` | views for the report: `overview`, `box_front`, `box_back`, `lid_top`, `lid_inside`, `small_parts` |
| `report.txt` | sizes, volumes, checks, which gland is which, and **the list of parameters to measure** |

## Parts

| Part | Print size (mm) | Print orientation | Notes |
|---|---|---|---|
| `box` | 190 × 107 × 42 | opening up | Pi 4 on 4 standoffs (ports to the front), USB-C opening in the front wall, 4 × PG7 glands in the back wall (probe, reed, 12 V sense, DHT22 pod), grommet in the right wall (lock adapter + solenoid wires), vent slots in both ends, 2 fixing tabs at the back, M3 lid bosses in the corners |
| `lid` | 190 × 95 × 9 | outer face on the bed | LCD window + 4 standoffs, red and green LED holes, buzzer grille + holder ring, keypad outline groove and ribbon slot, lip that locates it in the box |
| `dht22_pod` | 25 × 59 × 12 | open back on the bed | louvred slots on the front and sides, fixing flanges, cable notch; mount it out of sunlight and away from the fridge's warm exhaust |
| `reed_holder`, `magnet_holder` | 52 × 27 × 9 | flat | cradle for the body, zip-tie slots, 2 screw holes; `REED_SPACER` / `MAGNET_SPACER` raise one so both line up |
| `solenoid_plate` | 70 × 50 × 4 | flat | slotted holes so the lock slides ±3 mm to meet the strike |
| `strike` | 34 × 18 × 22 | base on the bed | window the lock bolt drops into |

Print: PETG (better than PLA near condensation and the Pi's heat), 0.2 mm layers, 4 perimeters,
20 % infill. No supports. The box (190 mm long) needs a 220 × 220 mm bed.

## Layout inside the box

```
 back wall:  [tab]            glands: probe  reed  12V  pod         [tab]
            +---------------------------------------------------------------+
            |  Pi 4 + carrier (under the keypad)  |  LCD module (under the  |
 left vents |                                     |  window), level shifter |  right vents
            |                                     |  LEDs, buzzer           |  + grommet
            +---------------------------------------------------------------+
 front wall:     [USB-C]
```

Orientation: the front of the box is the USB-C wall. Stick the keypad on with its ribbon towards the
front (into the slot) and mount the LCD with its pin header towards the back, so both read upright
for a person standing in front.

Fit check with the current values: 4 mm free above the Pi + carrier stack (assumed 30 mm), and
19 mm free below the LCD module, for the level shifter and wiring. A UPS board stacked on the Pi
would not fit: if you use one, measure it and raise `IN_Z` (the fit check will tell you).

## Before printing: measure

All values marked `VERIFY` in the script are listed in `exports/report.txt`. The most important
ones are below. A wrong value here means a part that does not fit.

1. LCD: PCB size, hole spacing, the metal frame (bezel) size and height, and the depth with the backpack.
2. Keypad: outline, and the ribbon's connector width (the slot is 22 × 4 mm).
3. Solenoid lock: mounting holes, bolt size, and bolt height.
4. Reed switch and magnet bodies.
5. PG7 gland thread and the grommet hole size (from their datasheets).
6. Your screws: M3 and M2.5 self-tapping pilot holes (print a test piece first).

Print the lid first (it is a much smaller print than the box): it checks the LCD, LEDs, buzzer and
keypad fits before you spend the material and time on the box.
