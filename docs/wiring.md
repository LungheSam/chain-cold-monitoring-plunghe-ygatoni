# Wiring

BCM GPIO numbering. Physical pin numbers checked against the Raspberry Pi 40-pin header pin-out.
Anything marked **VERIFY** must be measured or checked on the real part before connecting.

## GPIO map (reviewed, no conflicts)

| Signal | GPIO | Pin | Direction | Notes |
|---|---|---|---|---|
| DS18B20 data | 4 | 7 | in (1-Wire) | `dtoverlay=w1-gpio,gpiopin=4`, 4.7 kΩ to 3.3 V |
| DHT22 data | 17 | 11 | in | `dtoverlay=dht11,gpiopin=17`, 10 kΩ to 3.3 V (many modules already have it: VERIFY) |
| Reed switch | 27 | 13 | in, internal pull-up | other leg to GND; door closed = contact closed = LOW (VERIFY with a multimeter) |
| Mains sense | 22 | 15 | in, **no** internal pull | divider output; HIGH = 12 V present |
| Buzzer | 18 | 12 | out (PWM ~2 kHz) | through NPN driver |
| Red LED | 23 | 16 | out | 330 Ω |
| Green LED | 24 | 18 | out | 330 Ω |
| I2C SDA / SCL | 2 / 3 | 3 / 5 | I2C | LCD at 0x27 (VERIFY with `i2cdetect -y 1`). Pi has 1.8 kΩ pull-ups to 3.3 V on the board |
| Lock relay module IN | 25 | 22 | out | GPIO 25 is pulled down at boot, so a module that switches on with a HIGH input stays off (use one, or set its H/L jumper to H) |
| Keypad rows R1–R4 | 5, 6, 13, 19 | 29, 31, 33, 35 | out (scan) | |
| Keypad cols C1–C4 | 12, 16, 20, 21 | 32, 36, 38, 40 | in, internal pull-up | |
| Spare | 26 | 37 | | kept free (e.g. a hardware ack button later) |

Review notes:

- GPIO 12, 13 and 19 can be PWM outputs, but only if a PWM overlay assigns them. We only ever use
  PWM on GPIO 18, so using them for the keypad is fine.
- The buzzer will use **software PWM from lgpio** (through gpiozero), which is good enough for a
  beep. Real hardware PWM on GPIO 18 would need `dtoverlay=pwm,pin=18,func=2` and a different
  library; we keep GPIO 18 so that option stays open.
- **UPS board: VERIFY which model.** Many UPS HATs sit on the 40-pin header and use I2C
  (e.g. an INA219 at 0x40–0x43) or a GPIO for "power lost". Send me the model so I can check it
  does not clash with the map above and with the carrier PCB stacking.
- No RTC module: the Pi uses network time, and the software corrects offline timestamps
  (`decisions.md` D6). If a DS3231 (I2C 0x68) is added later, it clashes with nothing.

## Mains sense input

- Divider: 10 kΩ (top) / 2.7 kΩ (bottom). At 12.0 V: 12 × 2.7 / 12.7 = **2.55 V**. At 15 V (a cheap
  unloaded adapter): **3.19 V**, still below 3.3 V, but spikes are possible, hence the clamp.
- 100 nF across the 2.7 kΩ filters noise.
- On the PCB: a series resistor (1 kΩ) from the divider to the GPIO, and a BAT54S from the GPIO to
  3.3 V and GND as a clamp.
- The 12 V adapter's negative must be connected to the Pi's GND (common ground), otherwise the
  divider reading means nothing.
- The Peltier kit's 8–10 A runs only on the 12 V wiring (supply → 15 A fuse → car relay → Peltier and fans). Only the
  divider's ~1 mA comes onto our board.

## LCD backpack (PCF8574) and 5 V pull-ups

The backpack is powered from 5 V (the LCD needs it for contrast and backlight). Two problems:

1. Many backpacks have 4.7 kΩ or 10 kΩ pull-ups from SDA/SCL to **5 V**. Together with the Pi's
   1.8 kΩ pull-ups to 3.3 V, the idle line sits at about 3.3 + 1.7 × 1.8 / (1.8 + 4.7) ≈ **3.8 V**,
   above the Pi's 3.3 V I/O rating.
2. A PCF8574 at 5 V wants a logic HIGH of at least 0.7 × 5 V = **3.5 V** (PCF8574 datasheet,
   V_IH). The Pi only drives 3.3 V. It usually works, but it is out of spec.

How to check (backpack not connected to the Pi, powered from 5 V and GND only): measure DC voltage
from SDA to GND and from SCL to GND. About 5 V means pull-ups to 5 V. With power off, the resistance
from SDA to VCC shows the resistor value.

**Recommendation: use a 4-channel BSS138 bidirectional level-shifter module** (3.3 V side to the Pi,
5 V side to the backpack). This fixes both problems. Only removing the 5 V pull-ups fixes problem 1
but not problem 2. The carrier PCB (Phase 7) will include two BSS138 + 4 resistors for this.

## Lock driver (extension)

No logic-level MOSFET is sold locally, so a **5 V relay module** switches the lock (20 Nov 2026).

- Module: VCC → 5 V rail, GND → GND rail, IN → GPIO 25. The relay contacts switch the lock's
  own supply, so the lock circuit does not share ground with the Pi.
- Lock supply (+) → relay COM; relay NO → lock (+); lock (−) → lock supply (−). 1N4007 across the
  lock, cathode (stripe) to the lock's (+).
- **Trigger level VERIFY:** with the Pi off, power the module's VCC and touch IN to GND, then to 5 V:
  the relay must click only on HIGH. If it clicks on LOW, set its H/L jumper to H; only if it has
  none, set `LOCK_ACTIVE_LOW=1` in `edge/.env` (it may still click while the Pi boots).
- **Our lock** (SARY cabinet lock) is labelled 24 V, 1.4 A, "power-on time 500 ms": it needs only a
  short pulse to release the latch. The software powers it for `LOCK_PULSE_S` (0.5 s) and then
  rests 5 s. A **12 V** version was requested so it can run from the 12 V supply through its own
  fuse; until then, use a 24 V adapter for it, never the Pi.
- The lock has four wires: two for the coil, and probably two for a built-in door switch. VERIFY the
  colours with the seller's sheet or a multimeter before connecting.

## Peltier switching

The W1209's own relay (about 10 A) only switches the coil of a **SONGLE SLA-12VDC-SL-A** relay
(12 V coil, 30 A contacts), which switches the Peltier kit's 8–10 A:
12 V supply (+) → 15 A fuse → SLA contact COM; SLA NO → Peltier kit (+); kit (−) → supply COM.
W1209 relay → SLA coil (+); coil (−) → supply COM; 1N4007 across the coil, stripe to (+).
The SLA is a circuit-board relay: solder its pins or use a screw-terminal adapter, never a breadboard.
The supply we received is an **S-120-12, 12 V 10 A**: at the limit for the whole kit, so either run
one of the kit's two Peltier modules, or get a 20–30 A supply. Its mains side (L, N, ⏚) is wired by
the lab technician, with the earth connected and the terminal cover on; check its 110/220 V switch
is on **220 V** before the first power-on.

## Fritzing wiring list (design review)

This is the **reduced design we actually build on the breadboard**. Draw it in Fritzing's
breadboard view from this table. Rails: put **3.3 V + GND** on the top rails and **5 V + GND** on
the bottom rails. Join the two GND rails. Physical pin numbers are the Pi header pins.

Wire colour code: red = 5 V, orange = 3.3 V, black = GND, then one colour per signal.

Fritzing parts to use (names in the core library; **VERIFY** in your Fritzing version):
Raspberry Pi 4 (or Raspberry Pi 3, which has the same 40-pin header), DS18B20 (temperature sensor),
DHT22, reed switch, resistor, ceramic capacitor, NPN transistor, N-channel MOSFET (TO-220),
diodes, piezo buzzer, red and green LED, LCD 16x2 (with a note "PCF8574 I2C backpack" if no I2C
LCD part exists), "Logic Level Converter" (BSS138 bidirectional), 4x4 keypad (or an 8-pin header
labelled R1–R4 C1–C4), solenoid, DC barrel jacks for the 12 V and 5 V adapters, fuse.

### Power rails

| From | To | Pi pin | Colour |
|---|---|---|---|
| Pi 3V3 | top + rail | 1 | orange |
| Pi GND | top − rail | 6 | black |
| Pi 5V | bottom + rail | 2 | red |
| Pi GND | bottom − rail | 9 | black |
| top − rail | bottom − rail | – | black |

### Sensors

| Part | Part pin | Connects to | Pi pin (GPIO) | Colour |
|---|---|---|---|---|
| DS18B20 | VDD (red lead) | 3.3 V rail | – | orange |
| DS18B20 | GND (black lead) | GND rail | – | black |
| DS18B20 | DQ (yellow lead, VERIFY) | Pi | 7 (GPIO 4) | yellow |
| R1 4.7 kΩ | – | between DQ and 3.3 V rail | – | (component) |
| DHT22 | VCC (pin 1) | 3.3 V rail | – | orange |
| DHT22 | DATA (pin 2) | Pi | 11 (GPIO 17) | white |
| DHT22 | NC (pin 3) | not connected | – | – |
| DHT22 | GND (pin 4) | GND rail | – | black |
| R2 10 kΩ | – | between DATA and 3.3 V rail (leave out if the module has one) | – | (component) |
| Reed switch | lead 1 | Pi | 13 (GPIO 27) | blue |
| Reed switch | lead 2 | GND rail | – | black |

DHT22 pin numbers are for the bare 4-pin sensor (pin 1 on the left, grid facing you). A 3-pin module
has its own order printed on it: VERIFY.

### 12 V mains sense

| Part | Part pin | Connects to | Pi pin (GPIO) | Colour |
|---|---|---|---|---|
| 12 V barrel jack | + | F1 fuse, then the "12 V node" row | – | red (label "12 V") |
| 12 V barrel jack | − | GND rail (common ground) | – | black |
| R3 10 kΩ | – | 12 V node → sense node | – | (component) |
| R4 2.7 kΩ | – | sense node → GND rail | – | (component) |
| C1 100 nF | – | sense node → GND rail | – | (component) |
| R5 1 kΩ | – | sense node → GPIO row | – | (component) |
| GPIO row | – | Pi | 15 (GPIO 22) | pink |
| D1 1N5819 | anode / cathode | anode on the GPIO row, cathode to the 3.3 V rail (clamp) | – | (component) |

Draw the Peltier and fan as a separate load on the 12 V node **after the fuse**, with a note
"~5 A, not on the breadboard". Their current never flows through the breadboard or the Pi.

### Outputs

| Part | Part pin | Connects to | Pi pin (GPIO) | Colour |
|---|---|---|---|---|
| R6 1 kΩ | – | Pi → Q1 base | 12 (GPIO 18) | purple |
| Q1 NPN (2N2222 / BC547, VERIFY pin order) | emitter | GND rail | – | black |
| Q1 | collector | buzzer (−) | – | (short wire) |
| Buzzer | (+) | 5 V rail | – | red |
| D2 1N4148 | – | across the buzzer, cathode to 5 V | – | (component) |
| R7 330 Ω | – | Pi → red LED anode | 16 (GPIO 23) | brown |
| Red LED | cathode | GND rail | – | black |
| R8 330 Ω | – | Pi → green LED anode | 18 (GPIO 24) | green |
| Green LED | cathode | GND rail | – | black |

### LCD through the level shifter

| Part | Part pin | Connects to | Pi pin (GPIO) | Colour |
|---|---|---|---|---|
| Level shifter | LV | 3.3 V rail | – | orange |
| Level shifter | HV | 5 V rail | – | red |
| Level shifter | GND (both sides) | GND rail | – | black |
| Level shifter | LV1 | Pi SDA | 3 (GPIO 2) | cyan |
| Level shifter | LV2 | Pi SCL | 5 (GPIO 3) | grey |
| Level shifter | HV1 | LCD backpack SDA | – | cyan |
| Level shifter | HV2 | LCD backpack SCL | – | grey |
| LCD backpack | VCC | 5 V rail | – | red |
| LCD backpack | GND | GND rail | – | black |

### Keypad (extension)

| Keypad pin | Pi pin (GPIO) | Colour |
|---|---|---|
| R1, R2, R3, R4 | 29 (GPIO 5), 31 (GPIO 6), 33 (GPIO 13), 35 (GPIO 19) | yellow |
| C1, C2, C3, C4 | 32 (GPIO 12), 36 (GPIO 16), 38 (GPIO 20), 40 (GPIO 21) | cyan |

Ribbon order of our 4x4 keypad (seller's diagram): R1 R2 R3 R4 C1 C2 C3 C4, left to right with the keys
facing you, ribbon at the bottom (below `* 0 # D`). Confirm once with `test_keypad`.

### Solenoid lock (extension)

| Part | Part pin | Connects to | Pi pin (GPIO) | Colour |
|---|---|---|---|---|
| Relay module | VCC | 5 V rail | – | red |
| Relay module | GND | GND rail | – | black |
| Relay module | IN | Pi | 22 (GPIO 25) | ochre |
| Lock supply | + | relay COM | – | red (label "lock supply") |
| Relay module | NO | lock (+) | – | red |
| Lock | (−) | lock supply (−) | – | black |
| D3 1N4007 | – | across the lock, cathode (stripe) to the lock's (+) | – | (component) |

Never connect the lock to the Pi's 5 V pins: the lock current comes from its own supply only.

### Parts list for the breadboard build

R1 4.7 kΩ · R2 10 kΩ (if needed) · R3 10 kΩ · R4 2.7 kΩ · R5 1 kΩ · R6 1 kΩ · R7, R8 330 Ω ·
C1 100 nF · D1 1N5819 · D2 1N4148 · D3, D4 1N4007 · Q1 2N2222 or BC547 · 5 V relay module (lock) ·
SONGLE SLA-12VDC-SL-A relay (Peltier) · F1 15 A fuse · I2C level-shifter module · two barrel jacks.
(The carrier PCB still uses an AO3400A MOSFET for the lock; the breadboard uses the relay module.)
