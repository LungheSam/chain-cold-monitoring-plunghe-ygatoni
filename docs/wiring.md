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
| Lock MOSFET gate | 25 | 22 | out | 100 Ω series, 10 kΩ pull-down. GPIO 25 is pulled down at boot, so the lock stays off |
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
- A DS3231 RTC module (I2C 0x68) is recommended (see `decisions.md` D6). It shares SDA/SCL and
  clashes with nothing.

## Mains sense input

- Divider: 10 kΩ (top) / 2.7 kΩ (bottom). At 12.0 V: 12 × 2.7 / 12.7 = **2.55 V**. At 15 V (a cheap
  unloaded adapter): **3.19 V**, still below 3.3 V, but spikes are possible, hence the clamp.
- 100 nF across the 2.7 kΩ filters noise.
- On the PCB: a series resistor (1 kΩ) from the divider to the GPIO, and a BAT54S from the GPIO to
  3.3 V and GND as a clamp.
- The 12 V adapter's negative must be connected to the Pi's GND (common ground), otherwise the
  divider reading means nothing.
- The Peltier's ~5 A runs only on the 12 V wiring (adapter → fuse → Peltier/fan). Only the
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

5 V 2 A adapter (+) → solenoid → MOSFET drain; source → GND; 1N4007 (or 1N5819) across the
solenoid, cathode to +5 V; GPIO 25 → 100 Ω → gate; 10 kΩ gate → GND. Lock-adapter GND joined to Pi GND.
Use IRLB8721 (TO-220, easy to solder) or AO3400 (SOT-23, PCB only). Not IRLZ44N, which is not fully
on at 3.3 V gate drive. Solenoid current about 1 A: **VERIFY** by measuring with the lock energised.

## Fritzing wiring list

The full list (part, pin, wire colour, GPIO) for the breadboard view is added in Phase 2, so it is
ready for the 20 Nov design review.
