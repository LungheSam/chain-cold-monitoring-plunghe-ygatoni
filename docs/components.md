# Components list

Everything needed to build the demo unit, grouped by purpose. Quantities come from the design
(`docs/wiring.md`, `hardware/freecad/enclosure.py`, `hardware/kicad/output/carrier-bom.csv`).
**VERIFY** = check on the real part or its datasheet before relying on the value.
Tick the **Have** column as parts arrive.

## 1. Computer and power for the Pi

| Qty | Part | Spec / notes | Have |
|---|---|---|---|
| 1 | Raspberry Pi 4 Model B | 2 GB RAM or more. Check the board says "Raspberry Pi 4" (a Pi 3 B+ also works, but the enclosure's power opening must change) | |
| 1 | Pi power supply | official 5.1 V 3 A USB-C | |
| 1 | microSD card | 16–32 GB, A1 / Class 10, Raspberry Pi OS (64-bit) | |
| 0–1 | UPS board for the Pi | optional; model to choose (VERIFY it does not use our GPIO pins or I2C addresses, `docs/wiring.md`) | |

## 2. Sensors

| Qty | Part | Spec / notes | Have |
|---|---|---|---|
| 1 | DS18B20 waterproof probe | stainless tip, about 1 m cable; ±0.5 °C (datasheet) | |
| 1 | DHT22 (AM2302) | ambient temperature + humidity; bare sensor or small module (VERIFY whether the module has its own pull-up) | |
| 1 | Door reed switch with magnet | surface-mount door contact, MC-38 style (VERIFY: contact closed when the magnet is near) | |

## 3. Local alarm and user interface

| Qty | Part | Spec / notes | Have |
|---|---|---|---|
| 1 | 16×2 LCD with I2C backpack | HD44780 + PCF8574 backpack, 5 V (VERIFY address 0x27 or 0x3F) | |
| 1 | Logic level shifter | 4-channel BSS138 module (3.3 V ↔ 5 V for the LCD's I2C) | |
| 1 | Passive buzzer | about 12 mm, 5 V (VERIFY size for the lid holder) | |
| 1 | Red LED, 5 mm | alarm | |
| 1 | Green LED, 5 mm | OK | |
| 1 | 4×4 membrane keypad | ribbon R1–R4, C1–C4 (seller's diagram) | |

## 4. Door lock (extension)

| Qty | Part | Spec / notes | Have |
|---|---|---|---|
| 1 | Solenoid cabinet lock, 5 V | about 1 A (VERIFY by measuring); check its duty cycle | |
| 1 | 5 V 2 A adapter | lock power only, never from the Pi's 5 V pins | |
| 1 | IRLB8721 N-MOSFET (TO-220) | logic-level, for the breadboard (not IRLZ44N) | |
| 1 | 1N4007 diode | across the solenoid (flyback) | |

## 5. Cooling and 12 V supply (the "fridge")

| Qty | Part | Spec / notes | Have |
|---|---|---|---|
| 1 | The "fridge": an insulated cool box **or** a small (mini) fridge | whichever is easier to get. A mini fridge cools by itself (no Peltier needed); its own mains cable stays untouched (nobody works on 230 V) | |
| 2–4 | Frozen gel packs | keep a cool box below 8 °C without a Peltier (plan B in D14) | |
| 1 | 12 V adapter | **always needed**: the "mains present" sense input watches it (unplugging it is the power-cut demo). Without a Peltier any 12 V adapter of 1 A or more is enough | |
| 2 | DC barrel jacks | for the 12 V and the 5 V lock adapters | |

**Only if the school provides the Peltier in time** (not known yet, D14):

| Qty | Part | Spec / notes | Have |
|---|---|---|---|
| 1 | Peltier module TEC1-12706 kit | with hot-side heat sink and fan; about 6 A at 12 V. Never run it without the heat sink and fan | |
| — | 12 V adapter (instead of the small one) | rated for the Peltier plus fan: at least 6 A (VERIFY the label) | |
| 1 | Inline fuse holder + fuse | blade fuse just above the adapter rating, e.g. 7.5 A for a 6 A adapter | |

## 6. Small parts for the breadboard build

| Qty | Part | Used for | Have |
|---|---|---|---|
| 1 | 4.7 kΩ resistor | R1, DS18B20 pull-up | |
| 3 | 10 kΩ resistors | R2 DHT22 pull-up (if needed), R3 divider top, R10 MOSFET gate pull-down | |
| 1 | 2.7 kΩ resistor | R4 divider bottom (2.55 V at 12 V) | |
| 2 | 1 kΩ resistors | R5 sense series, R6 buzzer transistor base | |
| 2 | 330 Ω resistors | R7, R8 LEDs | |
| 1 | 100 Ω resistor | R9 MOSFET gate | |
| 1 | 100 nF capacitor | C1 sense filter | |
| 1 | 1N5819 Schottky diode | D1 clamp on the sense input | |
| 1 | 1N4148 diode | D2 across the buzzer | |
| 1 | BC547 or 2N2222 NPN transistor | Q1 buzzer driver (VERIFY pin order: they differ) | |
| 1 | Full-size breadboard | | |
| 1 set | Jumper wires | male–male, male–female, female–female (the keypad and LCD need female ends) | |
| — | Hook-up wire 22 AWG, heat-shrink, header pins | longer runs and the probe/reed cables | |

Buying a resistor assortment (E12, 1/4 W) covers all the resistors.

## 7. Enclosure (3D printed, `hardware/freecad/`)

| Qty | Part | Spec / notes | Have |
|---|---|---|---|
**No screws** (team decision): the lid clicks on with printed snap hooks, the Pi and LCD sit on printed
push-fit pins, and the brackets stick on with tape. Print the small fit test first (`hardware/freecad/README.md`).

| Qty | Part | Spec / notes | Have |
|---|---|---|---|
| ~0.3 kg | PETG filament | the 7 parts are about 180 cm³ of plastic; one 1 kg spool is plenty | |
| 4 | PG7 cable glands (optional) | tidy, sealed cable entries (they tighten by hand, no tools). Simple printed holes work too | |
| 1 | Rubber grommet (optional) | for the lock adapter and solenoid wires | |
| 1 roll | Strong double-sided mounting tape (foam, outdoor grade) | sticks the DHT22 pod, reed and magnet holders, lock plate and strike to the box/door | |
| — | Small zip ties | hold the reed, magnet and cables in their cradles | |
| — | Hot glue (optional) | holds the solenoid on its plate if tape is not strong enough (VERIFY with the real lock) | |

## 8. Carrier PCB (optional, not needed for the demo)

Only if the board is ordered (`hardware/kicad/`; it will not arrive before the demo). The full
list with footprints is `hardware/kicad/output/carrier-bom.csv`. Compared with the breadboard it
adds: 2×20 female header socket, M2.5 standoffs 11 mm (×4), JST-XH connectors (2-, 3- and 4-pin),
3 two-way screw terminals, 1×8 and 1×2 pin headers, AO3400A MOSFET and BAT54S diode (SOT-23)
instead of the IRLB8721 and 1N5819, 2 BSS138 + 2 × 10 kΩ instead of the level-shifter module.

## 9. Tools

| Tool | Why |
|---|---|
| Multimeter | the VERIFY measurements: divider voltage (must be below 3.3 V), lock current, adapter voltage, reed switch |
| Soldering iron + solder | probe/reed/keypad cables, header pins |
| Calipers | LCD, keypad, lock and reed dimensions for the enclosure |
| 3D printer (PETG) | the enclosure |
| Wire stripper, small screwdrivers | |
| Reference thermometer | test A2 (probe accuracy) |
