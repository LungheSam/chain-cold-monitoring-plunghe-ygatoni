# Decisions and open questions

Status: **proposed** = my recommendation, waiting for Samuel/Yves to confirm; **decided** = agreed.
All of D1–D17 were reviewed with the team on 11 Nov 2026.

## Tools on the development laptop

- FreeCAD 1.1.4: `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe` (not on PATH)
- KiCad 10.0.3: `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe` (not on PATH)
- Node 24, Python 3.14, OpenSSL 3.5
- Docker Desktop: not detected yet on 11 Nov

## D1. Node.js 24 LTS instead of 20: decided

Node 20 reached end-of-life on 30 April 2026, so it no longer gets security fixes. Node 24 is the
current LTS and is already installed on the laptop (v24.21). The code uses nothing version-specific;
`package.json` asks for `>=22.12`.

## D2. Raspberry Pi OS version: decided

The brief says Bookworm / Python 3.11. Since late 2025 the default Raspberry Pi OS image is based on
Debian 13 "Trixie" (Python 3.13). Both are fine: same `/boot/firmware/config.txt`, same overlays,
gpiozero + lgpio on both. Keep whatever is on the SD card now. The code stays compatible with
Python 3.11.

## D3. MQTT broker for the demo: HiveMQ Cloud Serverless (free): decided

- Free, TLS on 8883 with a public CA certificate (no CA file to copy to the Pi), supports QoS 1,
  retained messages and LWT, so nothing in our design changes. Nothing to host or keep awake.
- The team confirmed that the campus network does not block HiveMQ Cloud.
- Security is username/password over TLS (D11). Give the node and the back end **separate
  credentials**, and if the HiveMQ console offers per-credential topic permissions, restrict them
  like `broker/mosquitto/config/acl` (VERIFY in the console).
- Mosquitto in Docker stays the development broker.

## D4. Where the back end runs at the demo: Railway (paid Hobby plan): decided

- The team will pay for Railway. On the Hobby plan (VERIFY the current price on railway.com) a
  service runs continuously and does not sleep, so the MQTT subscriber stays connected.
  Leave Railway's optional "serverless / app sleeping" setting **off** for this service.
- Railway gives an HTTPS URL (`*.up.railway.app`), which the dashboard on Firebase Hosting needs.
- No secret files on Railway: the Firebase service-account JSON goes in an environment variable
  (`FIREBASE_SERVICE_ACCOUNT`, the whole JSON), and every other secret is a Railway variable.
- Run only **one** instance (replicas = 1). Two instances would both send each SMS and both answer
  commands.
- Fallback if Railway has a problem on the day: run the back end on a laptop (`npm start`).
- The dashboard's live view reads Firestore directly, so it keeps working even if the back end is down.

## D5. Public TD and read-only properties: decided

TD, read-only properties and the SSE event stream are public (`nosec`). Writes and actions need a
Firebase ID token and the `supervisor` role. Details in `thing-description.md`.

## D6. Clock: network time (NTP) only, no RTC module: decided

The Pi 4 has no real-time clock. It syncs over the network with `systemd-timesyncd`, within
seconds of Wi-Fi coming up. The only weak case is **a reboot while there is no network**: the
clock then starts at the last saved time (fake-hwclock), so it is behind by however long the Pi was
off, until the network returns. The software handles this without an RTC:

- The alarm logic and the out-of-range timer use `time.monotonic()`, so they are never affected.
- Every message is stored with its monotonic time and a `timeSynced` flag (from
  `timedatectl show -p NTPSynchronized`).
- When the clock syncs, the node works out `offset = time.time() - time.monotonic()` and fixes the
  timestamps of every unsynced message still in the offline queue before sending them. Monotonic
  time is continuous within one boot, so this is exact.
- The time the Pi was off during an excursion is also recovered after sync: the last saved state
  has a synced wall-clock time, so `off time = (sync time - seconds since boot) - last save time`.
- Only a message already **sent** while unsynced keeps a wrong time. To avoid that, the node keeps
  unsynced messages in the queue until the clock syncs. Without network it cannot send anyway.

A DS3231 module stays optional, only for a real deployment with long outages.

## D7. How out-of-range time is counted: decided

- The **cumulative timer uses the raw limits**: it counts every second the reading is above 8.0 °C
  or below 2.0 °C, from the first out-of-range reading (not after the confirmation delay).
- The **alarm uses the confirmation delay and the 0.3 °C hysteresis**: it fires after
  `TEMP_CONFIRM_S` and clears when the temperature is back within 2.3–7.7 °C.
- **Excursion record**: starts at the first out-of-range reading and ends when the alarm clears.
  It stores `durationS` (start to end) and `outOfRangeSeconds` (raw seconds actually out of range).
- A short blip that returns before the confirmation delay still adds to the total and gets an
  excursion record with `confirmed: false`. Then the total always equals the sum of the excursions,
  and the dashboard can hide unconfirmed ones by default.
- After a reboot in the middle of an excursion: the excursion is reopened from the saved file. The
  time the Pi was off is added once the clock is synced (D6), if the first reading after boot is
  still out of range. It is recorded separately as `offlineGapS` in the excursion, so it is clear
  that this part was assumed, not measured.

## D8. Lock safety if the program crashes: decided

If the Python process is killed while the lock is energised, the GPIO can **stay HIGH**. The gate
pull-down only helps when the pin is an input. So:

- `systemd` `ExecStopPost=` runs `pinctrl set 25 ip pd` (pin back to input with pull-down), which
  covers crashes and restarts.
- The software never holds the lock on for more than 5 s.
- Cheap solenoids are often rated for short duty cycles only: VERIFY on the lock's datasheet/listing.

## D9. What WARNING means: decided

- `WARNING`: a condition is present but not yet confirmed (temperature out of range inside the
  confirmation delay, door open but under the limit, sense line low but not yet `POWER_CONFIRM_S`),
  or only the ambient DHT22 has failed.
- `ALARM`: any confirmed alarm, or the internal probe has failed.
- `OK`: none of the above.
- `OFFLINE`: set by the back end only.

## D10. Firestore summaries and emulator: decided

Hourly and daily summary documents keep the 7-day chart and the analytics cheap. Use the Firebase
emulator for development and seeding. Arithmetic in `data-model.md`.

## D11. Command security: broker passwords over TLS, no HMAC: decided

Commands are protected by TLS plus a username/password per client. Only the back end has
credentials allowed to publish on `cmd` (Mosquitto ACL in development; HiveMQ permissions if
available, D3). Accepted risk: anyone who gets a broker password could publish `unlockDoor`, so
broker passwords are never shared or put in the dashboard, and they are kept only in `.env` files
and Railway variables.

## D12. Delayed (buffered) messages: decided

When the node comes back online it replays its queue. The back end stores everything but only
updates live state from messages newer than what it already has. An SMS for an event older than
5 minutes is marked "(delayed)", and is skipped if the problem already cleared in the same batch.

## D13. LCD level shifter: decided

Use a BSS138 level-shifter module between the Pi and the 5 V PCF8574 backpack. Reasons in `wiring.md`.

## D14. Demo cooling: Peltier check: decided

A single TEC1-12706 in a cool box may struggle to bring it below 8 °C and hold it there in a warm
room. Test this week. Plan B for the demo: frozen gel packs in the box, with the Peltier optional.
Either way:

- the 12 V adapter must be rated for the Peltier plus fan: about 6 A for the TEC1-12706 at 12 V
  (VERIFY on the adapter label);
- fuse just above the adapter rating (e.g. a 7.5 A blade fuse for a 6 A adapter) on the 12 V line;
- never power the Peltier without its hot-side heat sink and fan.

## D15. Africa's Talking SMS: decided

The team confirmed that Africa's Talking SMS works in Rwanda. Development uses the sandbox (free,
messages shown in their simulator). The demo uses the live account with the **default shared sender
ID** (leave `AT_SENDER_ID` empty), so no sender-ID registration is needed. The live account needs
credit topped up before 2 Dec.

We call the Africa's Talking REST API (`POST /version1/messaging`) with `fetch` instead of the
`africastalking` npm SDK: the SDK (0.8.x) pulls in old `axios`, `joi` and `body-parser` versions
with known high-severity vulnerabilities (npm audit, 11 Nov 2026). VERIFY the first real send in the
sandbox simulator.

## D16. Timeline: decided

Today is 11 Nov. The design review is on 20 Nov (9 days), and firmware plus hardware must be clearly
in progress by then. Proposed order:

| Dates | Work |
|---|---|
| 11–13 Nov | Phase 1 (alarm logic + simulator) |
| 13–17 Nov | Phase 2 (real drivers, bring-up), **Fritzing wiring list moved here** for the review |
| 17–20 Nov | Phase 3 start (back end), design review report |
| 20–25 Nov | Phase 3 finish + Phase 4 (dashboard) |
| 25–28 Nov | Phase 5 (keypad/lock/QR) + Phases 6–7 (enclosure, PCB). PCB fabrication will not arrive in time from abroad, so build on protoboard and show the KiCad design |
| 29 Nov–2 Dec | Phase 8 end-to-end tests, rehearsal |
| 3–7 Dec | Final report |

## D17. Sensor fault values: decided

The Linux `w1_therm` driver reports a failed read as an I/O error (or a CRC failure), not
−127 °C. −127 comes from the Arduino library. We treat as `SENSOR_FAULT`: probe missing, read error,
exactly 85.0 °C (power-on reset value) and −127 °C (in case), after **3 bad reads in a row**, so
one glitch does not raise an alarm. A bad value is never counted as out-of-range time. The DHT22
is a fault after 5 failed reads in a row (the kernel driver often returns `EIO`, so single
failures are normal). Phase 2 must feed the engine one reading per *new* sensor sample, so that
"3 in a row" means 3 samples, not 3 passes of the 0.1 s main loop.

## Things to measure (VERIFY list)

- [ ] LCD I2C address (`i2cdetect -y 1`), and whether the backpack has 5 V pull-ups (see `wiring.md`)
- [ ] LCD module outline, window and hole spacing (calipers): assumed 80 × 36 mm, holes 75 × 31 mm, M3
- [ ] Pi 4 hole pattern 58 × 49 mm, M2.5 (from the Raspberry Pi mechanical drawing, check with calipers)
- [ ] Reed switch: contact closed when the magnet is near? Body and magnet dimensions
- [ ] Solenoid lock current at 5 V, body and mounting-hole dimensions, rated duty cycle
- [ ] 12 V adapter voltage with no load and with the Peltier running, current rating
- [ ] UPS board model, size, which pins/I2C addresses it uses
- [ ] Keypad ribbon pin order (rows/columns), flat-cable width
- [ ] Time of one PIN check on the Pi (`python -m coldchain.pins time`, 17 ms on the laptop; should stay under ~100 ms)
- [ ] DHT22 module: has its own pull-up?
- [ ] Enclosure: every `VERIFY` parameter in `hardware/freecad/exports/report.txt` (LCD bezel and depth, keypad and ribbon, solenoid holes and bolt, reed/magnet bodies, screw pilot holes, Pi + carrier stack height 30 mm assumed)
- [ ] Cable diameters (DS18B20 probe, reed) for the PG7 glands (PG7 fits about 3–6.5 mm cable: VERIFY with the gland's datasheet)
