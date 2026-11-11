# Decisions and open questions

Status: **proposed** = my recommendation, waiting for Samuel/Yves to confirm; **decided** = agreed.

## D1. Node.js 24 LTS instead of 20: proposed

Node 20 reached end-of-life on 30 April 2026, so it no longer gets security fixes. Node 24 is the
current LTS and is already installed on the laptop (v24.21). The code uses nothing version-specific;
`package.json` asks for `>=22.12`.

## D2. Raspberry Pi OS version: proposed

The brief says Bookworm / Python 3.11. Since late 2025 the default Raspberry Pi OS image is based on
Debian 13 "Trixie" (Python 3.13). Both are fine: same `/boot/firmware/config.txt`, same overlays,
gpiozero + lgpio on both. Keep whatever is on the SD card now. The code stays compatible with
Python 3.11.

## D3. MQTT broker for the demo: HiveMQ Cloud Serverless (free): proposed

- Free, TLS on 8883 with a public CA certificate (no CA file to copy to the Pi), supports QoS 1,
  retained messages and LWT, so nothing in our design changes. Nothing to host or keep awake.
- **Risk: the campus Wi-Fi may block outbound port 8883.** Test it this week from the Pi on the
  campus network. Fallbacks: MQTT over WebSockets on HiveMQ's 8884, or a phone hotspot at the demo.
- Per-credential topic permissions on the free tier: VERIFY in the HiveMQ console. If they are not
  available, the HMAC-signed commands (D11) still stop a forged `unlockDoor`.
- Mosquitto in Docker stays the development broker.

## D4. Where the back end runs at the demo: proposed, decide in Phase 3

- Render's free web services sleep after ~15 min with no HTTP traffic, which stops the MQTT
  subscriber (missed events, no SMS). Railway has no permanent free tier (trial credit only).
- **Recommended: run the back end on a laptop at the demo** and expose it over HTTPS with a free
  Cloudflare quick tunnel (`cloudflared tunnel --url http://localhost:3000`). HTTPS is required
  because the dashboard on Firebase Hosting is HTTPS and browsers block calls to plain HTTP.
- Alternative if you want it always on: a Google Cloud `e2-micro` "always free" VM (needs a billing
  account / card).
- The dashboard's live view reads Firestore directly, so it keeps working even if the back end is down.

## D5. Public TD and read-only properties: proposed

TD, read-only properties and the SSE event stream are public (`nosec`). Writes and actions need a
Firebase ID token and the `supervisor` role. Details in `thing-description.md`.

## D6. The Pi 4 has no real-time clock: proposed

After a reboot without Internet, the Pi's clock starts at the last saved time (fake-hwclock), so
event times can be wrong until NTP syncs. This matters for the "reboot during an excursion" test.

- The alarm logic and the out-of-range timer use `time.monotonic()`, so they are not affected.
- Every message carries `timeSynced` (from `timedatectl show -p NTPSynchronized`).
- **Recommendation: add a DS3231 RTC module** (cheap, I2C 0x68, `dtoverlay=i2c-rtc,ds3231`).
  Then timestamps are right even offline.

## D7. How out-of-range time is counted: proposed

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
  time the Pi was off is added only if the clock is trusted (D6) and the first reading after boot
  is still out of range. Otherwise the gap is recorded as `unknownGapS` in the excursion.

## D8. Lock safety if the program crashes: proposed

If the Python process is killed while the lock is energised, the GPIO can **stay HIGH**. The gate
pull-down only helps when the pin is an input. So:

- `systemd` `ExecStopPost=` runs `pinctrl set 25 ip pd` (pin back to input with pull-down), which
  covers crashes and restarts.
- The software never holds the lock on for more than 5 s.
- Cheap solenoids are often rated for short duty cycles only: VERIFY on the lock's datasheet/listing.

## D9. What WARNING means: proposed

- `WARNING`: a condition is present but not yet confirmed (temperature out of range inside the
  confirmation delay, door open but under the limit, sense line low but not yet `POWER_CONFIRM_S`),
  or only the ambient DHT22 has failed.
- `ALARM`: any confirmed alarm, or the internal probe has failed.
- `OK`: none of the above.
- `OFFLINE`: set by the back end only.

## D10. Firestore summaries and emulator: proposed

Hourly and daily summary documents keep the 7-day chart and the analytics cheap. Use the Firebase
emulator for development and seeding. Arithmetic in `data-model.md`.

## D11. Signed commands: proposed

Commands carry an HMAC-SHA256 signature made with a secret shared by the back end and the node.
Without it, anyone holding any broker password could publish `unlockDoor`. About 10 lines of code on
each side.

## D12. Delayed (buffered) messages: proposed

When the node comes back online it replays its queue. The back end stores everything but only
updates live state from messages newer than what it already has. An SMS for an event older than
5 minutes is marked "(delayed)", and is skipped if the problem already cleared in the same batch.

## D13. LCD level shifter: proposed

Use a BSS138 level-shifter module between the Pi and the 5 V PCF8574 backpack. Reasons in `wiring.md`.

## D14. Demo cooling: Peltier check: proposed

A single TEC1-12706 in a cool box may struggle to bring it below 8 °C and hold it there in a warm
room. Test this week. Plan B for the demo: frozen gel packs in the box, with the Peltier optional.
Either way:

- the 12 V adapter must be rated for the Peltier plus fan: about 6 A for the TEC1-12706 at 12 V
  (VERIFY on the adapter label);
- fuse just above the adapter rating (e.g. a 7.5 A blade fuse for a 6 A adapter) on the 12 V line;
- never power the Peltier without its hot-side heat sink and fan.

## D15. Africa's Talking live SMS in Rwanda: open

The sandbox is free and shows messages in their simulator. Live SMS costs credit, and Rwanda may
require a registered sender ID. VERIFY with Africa's Talking early (account, top-up, sender ID), as
approval can take days. If live is not ready by 2 Dec, demo with the sandbox simulator on screen.

## D16. Timeline: proposed

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
exactly 85.0 °C (power-on reset value) and −127 °C (in case). The DHT22 is a fault after 5 failed
reads in a row (the kernel driver often returns `EIO`, so single failures are normal).

## Things to measure (VERIFY list)

- [ ] LCD I2C address (`i2cdetect -y 1`), and whether the backpack has 5 V pull-ups (see `wiring.md`)
- [ ] LCD module outline, window and hole spacing (calipers): assumed 80 × 36 mm, holes 75 × 31 mm, M3
- [ ] Pi 4 hole pattern 58 × 49 mm, M2.5 (from the Raspberry Pi mechanical drawing, check with calipers)
- [ ] Reed switch: contact closed when the magnet is near? Body and magnet dimensions
- [ ] Solenoid lock current at 5 V, body and mounting-hole dimensions, rated duty cycle
- [ ] 12 V adapter voltage with no load and with the Peltier running, current rating
- [ ] UPS board model, size, which pins/I2C addresses it uses
- [ ] Keypad ribbon pin order (rows/columns), flat-cable width
- [ ] DHT22 module: has its own pull-up?
- [ ] Cable diameters (DS18B20 probe, reed) for the PG7 glands (PG7 fits about 3–6.5 mm cable: VERIFY with the gland's datasheet)
