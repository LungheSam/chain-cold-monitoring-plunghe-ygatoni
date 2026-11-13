# End-to-end test plan

Three levels of testing. The first two run on a laptop with no hardware. The third needs the Pi, the
fridge and the cloud services, and its results go in the final report.

| Level | What | How to run | Last result |
|---|---|---|---|
| Unit tests | alarm logic, outbox, PINs, lock timer, ingest, SMS rules, TD schema, HTTP API, analytics | `edge`: `pytest` · `backend`: `npm test` · `frontend`: `npm test` | 88 + 47 + 14 pass |
| Automated end-to-end | broker + back end + mock node, driven through the Web Thing API | `backend`: `npm run e2e` (1.5 min) | 34 / 34 checks pass |
| System tests on the real hardware | sections A–G below | by hand, following this page | to do |

## What the automated end-to-end test covers

`backend/e2e/run.mjs` starts an MQTT broker inside the test, the real back end (memory store, dev
tokens) and the real edge code with simulated sensors. It then acts like the dashboard:

1. Node comes online; the Thing Description and properties are readable.
2. Probe at 9.5 °C: WARNING at once, ALARM and OUT_OF_RANGE_HIGH after the 20 s confirm delay; the
   out-of-range time counts from the first bad reading; an SMS alert is sent.
3. Viewer cannot acknowledge (403); supervisor acknowledges; thresholds are written to the node; an
   impossible threshold is refused by the node (422).
4. Back in range: BACK_IN_RANGE with duration and max; total kept.
5. QR unlock (supervisor only), keypad unlock, 3 wrong PINs lock the keypad; the public event stream
   carries no user names.
6. Broker stopped for 22 s while the door is left open: the node raises the door alarm offline,
   queues it, and delivers both events in order after the broker returns.
7. Power cut: POWER_LOST and POWER_RESTORED.
8. Node killed: the Last Will marks the unit OFFLINE; after a restart the out-of-range total is intact.

## System tests on the real hardware

Before starting: hardware brought up part by part (`edge/SETUP.md`, steps 0–12), `PROFILE=demo` unless
a test says `real`, and a reference thermometer next to the probe. Record every measured value: it is
evidence for the report. "Pass" means the expected column is met.

### A. Sensors (accuracy)

| ID | Test | Steps | Expected | Measured | Pass |
|---|---|---|---|---|---|
| A1 | DS18B20 at 0 °C | probe in a cup of crushed ice + water, stirred, 3 min | 0.0 ± 0.5 °C (datasheet accuracy) | | |
| A2 | DS18B20 vs reference | probe and reference thermometer inside the fridge, 30 min | within ± 0.5 °C of the reference | | |
| A3 | DHT22 ambient | compare with a room thermometer/hygrometer | ± 0.5 °C, ± 5 %RH (typical datasheet values) | | |
| A4 | Probe fault | unplug the DS18B20 connector | SENSOR_FAULT after 3 bad samples, status ALARM, no out-of-range time counted | | |
| A5 | Door reed | open / close the door 10 times | each opening logged once (DOOR_CLOSED with `openSeconds`), no false events | | |
| A6 | Mains sense | measure GPIO 22 voltage with 12 V on; unplug the 12 V adapter | about 2.55 V; POWER_LOST after 3 s (demo) | | |

### B. Alarms on the device (no network needed)

| ID | Test | Steps | Expected | Measured | Pass |
|---|---|---|---|---|---|
| B1 | High temperature | warm the probe in a hand or warm water | WARNING (LCD), then after 20 s: red LED blinks, buzzer, LCD `ALARM` | delay: | |
| B2 | Low temperature | probe in ice water | same, OUT_OF_RANGE_LOW | delay: | |
| B3 | Short blip | warm the probe for 10 s only | no alarm; BACK_IN_RANGE marked "short blip"; time still counted | | |
| B4 | Hysteresis | hold the probe near 8.1 °C | no repeated alarm/clear flapping | | |
| B5 | Acknowledge on keypad | during an alarm type `#` PIN `#` | buzzer stops, red LED keeps blinking, ALARM_ACKNOWLEDGED logged with the name | | |
| B6 | Door left open | open the door and wait | alarm after 15 s (demo) / 120 s (real) | | |
| B7 | Local alarm without Internet | switch the Wi-Fi router off, then do B1 | local alarm still works; events arrive on the dashboard after Wi-Fi returns | | |

### C. Data and cloud

| ID | Test | Steps | Expected | Measured | Pass |
|---|---|---|---|---|---|
| C1 | End-to-end latency | warm the probe; note when the alarm shows on the LCD, the dashboard and the phone | dashboard < 5 s after the LCD; SMS < 60 s | dashboard: SMS: | |
| C2 | Offline replay | Wi-Fi off for 10 min, open the door twice, Wi-Fi on | all events arrive in order with their real times | | |
| C3 | Boot without network time | Wi-Fi off, reboot the Pi, open the door, Wi-Fi on | events stored with the correct time after NTP sync (`timeSynced` re-timing) | | |
| C4 | Crash | `sudo systemctl kill -s KILL coldchain-node` | dashboard OFFLINE within seconds; service back after 5 s; total intact | | |
| C5 | Unit unplugged | unplug the Pi | OFFLINE on the dashboard; SMS "offline" after 2 min | | |
| C6 | 24 h soak test | leave it running (real profile) | no restarts in `journalctl`, memory stable, Firestore writes within the free tier | writes/day: | |
| C7 | Thing Description | open `/things/cold-unit-01` in a browser | valid TD (the back-end test checks it against the official TD 1.1 schema) | | |

### D. SMS (Africa's Talking)

| ID | Test | Steps | Expected | Measured | Pass |
|---|---|---|---|---|---|
| D1 | Alert | cause B1 with a live AT account | one SMS per contact, text names the unit and temperature | | |
| D2 | No spam | warm the probe twice within 10 min (two excursions) | the second alert is not sent again within 15 min of the first | | |
| D3 | All clear | return to range | one "back in range" SMS with the duration | | |

Note: the Africa's Talking **sandbox** does not deliver to real phones (messages only appear in its
simulator). D1–D3 need a live account with a little credit.

### E. Dashboard

| ID | Test | Expected | Pass |
|---|---|---|---|
| E1 | Sign in as viewer and as supervisor | viewer has no Settings / Door QR / acknowledge | |
| E2 | Live update | temperature and "last updated" change without reloading | |
| E3 | History, analytics, excursions | the B1/B2 excursions appear with start, end, min, max; CSV export opens in Excel | |
| E4 | Phone | every page usable on a phone, no sideways scrolling | |

### F. Access control (extension)

| ID | Test | Expected | Pass |
|---|---|---|---|
| F1 | Keypad PIN | lock opens 5 s, ACCESS_GRANTED with the name | |
| F2 | 3 wrong PINs | keypad locked 60 s, LCD shows the countdown | |
| F3 | QR code | scan the printed label with a phone, sign in as supervisor, unlock: lock opens, logged with the email | |
| F4 | Lock safe on crash | kill the service while the lock is open: `pinctrl get 25` shows input, pull-down; lock closed | |
| F5 | Lock current | multimeter in series with the solenoid: about 1 A (VERIFY value for the PCB tracks) | |

### G. Mechanical

| ID | Test | Expected | Pass |
|---|---|---|---|
| G1 | Lid print | LCD, LEDs, buzzer and keypad fit (`hardware/freecad/README.md`) | |
| G2 | Box print | Pi, cables and glands fit; lid closes; USB-C cable reaches | |
| G3 | Probe cable | DS18B20 cable through the fridge door seal without stopping the door from closing | |

## Faults found and fixed during development

Kept here for the report's testing section. Each one was found by a test.

| Found by | Problem | Fix |
|---|---|---|
| unit test (Phase 1) | debounce timer started on the second sample, so delays were one sample long | timers start when the change is first seen |
| end-to-end run (Phase 3) | first telemetry after coming online was not written | "came online" forces a write |
| browser check (Phase 4) | 7-day chart of hourly averages hid excursion peaks (10.9 °C shown as 7.5 °C) | min–max band added |
| scenario run (Phase 5) | `#` in a scenario file was read as a comment, so `key 1234#` lost its `#` | comments need ` # ` |
| DRC (Phase 7) | pad shape distance was 0 inside rectangles, so pin-1 pads could not be routed | signed distance |
| seller's diagram (Phase 7) | keypad ribbon leaves the bottom edge: the lid slot was on the wrong side | slot moved to the front |
