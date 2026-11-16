# Purchase request: IoT cold chain monitoring prototype

**Course:** 04-645 A Internet of Things, CMU Africa, Fall 2026
**Team:** Putshu Lunghe Samuel (plunghe), Yves Dominique Gatoni (ygatoni)
**Needed by:** as soon as possible; the demo is on Wednesday 2 December 2026
**Purpose:** a working prototype of a vaccine fridge monitor. A small insulated box is cooled by a
Peltier module and kept between +2 and +8 °C; a Raspberry Pi measures the temperature, the door and
the power supply, raises a local alarm and an SMS, and records every period out of range.

How to read the list:
- **Priority**: *Essential* = the prototype cannot work without it; *Extension* = the door lock
  feature; *Optional* = makes the build better or safer but is not required.
- **Specification** is what to buy. Where several products would do, the key values are given.
- The price column is left for the purchasing office.

## A. Cooling (the "fridge")

| # | Item | Specification | Qty | Priority | Purpose | Unit price |
|---|---|---|---|---|---|---|
| A1 | Thermoelectric (Peltier) cooling kit | Complete kit with **TEC1-12706** module, **hot-side heat sink with fan** (about 90 mm) and **cold-side heat sink with fan** (about 40 mm); **12 V DC, about 6 A maximum, about 60 W**. Often sold as "DIY thermoelectric Peltier refrigeration cooling system kit". | 1 | Essential | cools the box | |
| A2 | DC power supply for the cooler | **12 V DC, 10 A (120 W)**, enclosed metal-case type or desktop brick, with mains cable; **CE/UL marked** | 1 | Essential | powers the Peltier kit and fans (a 6 A supply would run at its limit) | |
| A3 | Inline fuse holder with fuses | Blade-fuse holder for the 12 V line, rated for at least 10 A, with **10 A blade fuses** (pack) | 1 + fuses | Essential | protects the 12 V wiring | |
| A4 | Thermostat controller module | **W1209** (or equivalent) 12 V digital thermostat with NTC probe and on-board relay; relay rated **at least 10 A at 12 V DC** (check the listing) | 1 | Essential | switches the Peltier on and off around a set temperature, like a real fridge thermostat | |
| A5 | Insulated cool box | Small, rigid, well insulated: **5–10 litres**, polystyrene or foam-walled picnic cool box with a flat lid (the cooler is mounted through the lid, pointing down) | 1 | Essential | the "vaccine fridge" | |
| A6 | Power wire | **16 AWG** (1.5 mm²) two-core red/black, about 3 m | 1 | Essential | 12 V supply to the cooler | |
| A7 | Gel ice packs | reusable, small (about 200–400 ml) | 4 | Optional | back-up cooling if the Peltier cannot reach +8 °C in a warm room | |
| A8 | Foam sealing tape | self-adhesive foam weatherstrip, about 10 mm wide, 2 m | 1 | Optional | seals the gap around the cooler in the lid and the box lid | |

## B. Computer

| # | Item | Specification | Qty | Priority | Purpose | Unit price |
|---|---|---|---|---|---|---|
| B1 | Raspberry Pi 4 Model B | 2 GB RAM or more | 1 | Essential (if not already available) | runs the monitoring software | |
| B2 | Raspberry Pi power supply | **official Raspberry Pi 15 W USB-C, 5.1 V 3 A** | 1 | Essential (if not already available) | powers the Pi | |
| B3 | microSD card | **32 GB, Class 10 / A1** (SanDisk, Samsung or similar) | 1 | Essential (if not already available) | operating system and data | |

## C. Sensors

| # | Item | Specification | Qty | Priority | Purpose | Unit price |
|---|---|---|---|---|---|---|
| C1 | Waterproof temperature probe | **DS18B20**, stainless steel tip, about 1 m cable, 3 wires | 2 | Essential | internal temperature (second one is a spare) | |
| C2 | Temperature and humidity sensor | **DHT22 / AM2302** (module on a small board preferred) | 1 | Essential | room temperature and humidity | |
| C3 | Door reed switch | surface-mount magnetic door contact, **normally open**, with magnet (MC-38 type) | 2 | Essential | door open / closed (one spare) | |

## D. Alarm and display

| # | Item | Specification | Qty | Priority | Purpose | Unit price |
|---|---|---|---|---|---|---|
| D1 | LCD display | **16×2 character LCD with I2C backpack (PCF8574)**, 5 V, blue or green backlight | 1 | Essential | local status display | |
| D2 | Logic level converter | **4-channel bidirectional, BSS138**, 3.3 V ↔ 5 V | 2 | Essential | connects the 5 V display to the 3.3 V Pi (one spare) | |
| D3 | Buzzer | **passive** buzzer module or bare buzzer, 5 V, about 12 mm | 2 | Essential | audible alarm | |
| D4 | LEDs | 5 mm, red and green, assorted pack | 1 pack | Essential | alarm / OK lights | |

## E. Door lock (extension)

| # | Item | Specification | Qty | Priority | Purpose | Unit price |
|---|---|---|---|---|---|---|
| E1 | Electric solenoid cabinet lock | **5 V DC**, small (fits a cupboard door), current about 1 A or less | 1 | Extension | locks the box door | |
| E2 | Power supply for the lock | **5 V DC, 2 A**, barrel plug | 1 | Extension | powers the lock (not from the Pi) | |
| E3 | Keypad | **4×4 matrix membrane keypad**, 8-pin ribbon | 1 | Extension | PIN entry | |
| E4 | MOSFET | **IRLB8721** (logic-level N-channel, TO-220) | 2 | Extension | switches the lock (one spare) | |

## F. Electronic parts and wiring

| # | Item | Specification | Qty | Priority | Purpose | Unit price |
|---|---|---|---|---|---|---|
| F1 | Breadboard | full size, 830 points | 1 | Essential | circuit assembly | |
| F2 | Jumper wire set | male–male, male–female and female–female, 20 cm, about 40 of each | 1 set | Essential | connections | |
| F3 | Resistor assortment | 1/4 W, E12 values from 10 Ω to 1 MΩ (must include 100 Ω, 330 Ω, 1 kΩ, 2.7 kΩ, 4.7 kΩ, 10 kΩ) | 1 | Essential | pull-ups, voltage divider, LED and transistor resistors | |
| F4 | Diodes | 1N4007 (×5), 1N4148 (×5), 1N5819 Schottky (×5) | 1 set | Essential | protection diodes | |
| F5 | Transistors | BC547 or 2N2222 NPN | 5 | Essential | buzzer driver | |
| F6 | Ceramic capacitors | 100 nF | 5 | Essential | noise filter | |
| F7 | DC barrel jack connectors | 5.5 × 2.1 mm, female, with screw terminals | 2 | Essential | connect the 12 V and 5 V supplies | |
| F8 | Hook-up wire | 22 AWG solid core, assorted colours | 1 set | Essential | longer connections | |
| F9 | Heat-shrink tubing | assorted sizes | 1 set | Essential | insulate soldered joints | |
| F10 | Double-sided mounting tape | strong foam tape, outdoor grade, 1 roll | 1 | Essential | fixes the sensors and brackets (no screws) | |
| F11 | Small cable ties | 100 mm | 1 pack | Essential | cable management | |

## G. Enclosure (3D printed by the team)

| # | Item | Specification | Qty | Priority | Purpose | Unit price |
|---|---|---|---|---|---|---|
| G1 | 3D printer filament | **PETG, 1.75 mm, 1 kg** (any colour) | 1 | Essential | electronics box, sensor holders, cooler mounting frame | |
| G2 | Cable glands | PG7, IP68, for 3–6.5 mm cable | 4 | Optional | sealed cable entries into the box | |

## H. Tools (only if the lab does not already have them)

| # | Item | Specification | Qty | Priority | Purpose |
|---|---|---|---|---|---|
| H1 | Digital multimeter | DC voltage and current up to 10 A | 1 | Essential | safety checks (voltages, lock current) |
| H2 | Soldering station | temperature controlled, with solder | 1 | Essential | sensor cables |
| H3 | Digital calipers | 150 mm | 1 | Essential | measuring parts for the 3D-printed enclosure |
| H4 | Access to a 3D printer | prints PETG, bed at least 220 × 220 mm | — | Essential | printing the enclosure |

## Safety notes for the purchasing office

- All mains-powered items (A2, B2, E2) must be **certified** (CE / UL or equivalent) power supplies.
  The team never opens or wires anything at 230 V; only the low-voltage (12 V / 5 V) side is used.
- The Peltier cooler's 12 V current does not pass through the Raspberry Pi or the circuit board: it
  goes from the supply through the fuse (A3) and the thermostat (A4) to the cooler only.
