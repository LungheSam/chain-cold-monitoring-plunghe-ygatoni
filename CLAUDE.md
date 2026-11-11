# CLAUDE.md: IoT Cold Chain Monitoring for Vaccine Storage Units

CMU Africa 04-645 A Internet of Things, Fall 2026. Team: Putshu Lunghe Samuel (plunghe) and
Yves Dominique Gatoni (ygatoni). Deadlines: design review **Fri 20 Nov 2026**, demo (Open Day)
**Wed 2 Dec 2026**, final report **Mon 7 Dec 2026**.

## What the system does

It monitors a vaccine fridge that must stay at **+2 to +8 °C**. It reports the internal temperature
(DS18B20), the ambient temperature and humidity (DHT22, outside the box), the door (reed switch) and
12 V mains presence (divider). It raises a local alarm (buzzer, red LED, LCD) and an SMS (Africa's
Talking), and keeps a **cumulative out-of-range time plus excursion records** (start, end, min,
max), so that affected stock can be identified. Extension: 4×4 keypad PIN + solenoid lock + QR
unlock page.

## Layout

| Folder | What | Stack |
|---|---|---|
| `edge/` | Raspberry Pi 4 node: sensors, **all alarm logic**, LCD, offline SQLite queue, mock mode | Python 3.11+, gpiozero/lgpio (OS), paho-mqtt 2.x, RPLCD, pytest |
| `broker/` | Dev Mosquitto in Docker, TLS 8883 + passwords + ACL | Mosquitto 2 |
| `backend/` | MQTT ingest, Firestore, WoT TD 1.1 + HTTP + SSE, commands, SMS, auth | Node 24, Express, ES modules, mqtt, firebase-admin, africastalking, ajv, node:test |
| `frontend/` | Dashboard + `/unlock/:unitId` page | React + Vite, React Router, Firebase JS SDK, react-chartjs-2, qrcode.react |
| `firebase/` | `firestore.rules`, `firestore.indexes.json`, hosting config (build goes to `firebase/public`) | |
| `hardware/` | `fritzing/`, `freecad/enclosure.py` (parametric, headless), `kicad/` carrier PCB | |
| `docs/` | architecture, wiring, mqtt-topics, thing-description, data-model, **decisions** | |

## Key contracts (details in docs/)

- Unit ID `cold-unit-01`. Topics `coldchain/{unitId}/telemetry|event|status|cmd|cmd/result`
  (`docs/mqtt-topics.md`). Status is retained, with an LWT of `offline`.
- Commands: `{id, action, params, expiresAt}`, 30 s expiry, de-duplicated by id. Security = TLS +
  broker passwords only (no HMAC, D11).
- Deployment: HiveMQ Cloud broker, back end on **Railway** (paid, always on, 1 instance, service
  account JSON in the `FIREBASE_SERVICE_ACCOUNT` variable), dashboard on Firebase Hosting, Africa's
  Talking with the default sender ID.
- Clock: NTP only, no RTC. Messages carry `timeSynced`, and unsynced queued messages are re-timed
  from monotonic time once NTP syncs (D6).
- TD at `GET /things/cold-unit-01`. Forms: `/things/{id}/properties/{name}` (GET, PUT for
  `thresholds`), `POST /things/{id}/actions/{name}`, `GET /things/{id}/events` (SSE).
- Profiles: `real` = 300/120/5 s, `demo` = 20/15/3 s (TEMP_CONFIRM_S / DOOR_OPEN_LIMIT_S / POWER_CONFIRM_S).
- Alarm: confirm delay, 0.3 °C hysteresis, door debounce 50 ms, power confirm. The out-of-range
  timer counts raw seconds outside 2–8 °C from the first bad reading (D7). The total is saved
  atomically every 10 s and on every state change.
- Firestore: only the back end writes; the dashboard reads with listeners. Readings at most
  1 per 60 s; hourly/daily summaries for long ranges (`docs/data-model.md`).
- Open decisions and the VERIFY list: `docs/decisions.md`.

## GPIO (BCM)

DS18B20 4 · DHT22 17 · reed 27 · mains sense 22 · buzzer 18 · red LED 23 · green LED 24 ·
I2C 2/3 · lock gate 25 · keypad rows 5, 6, 13, 19 · cols 12, 16, 20, 21 · spare 26.

## How to work on this repo (from the student)

- Simple, readable code with short comments, like a good student would write. No clever abstractions.
- Work in **phases** (0–8, see the README). At the end of each phase: run the tests, show what works
  and what must be done by hand, **commit**, then **stop and wait** for the go-ahead.
- Never commit secrets: `.env` files are git-ignored, and `.env.example` files are committed.
- **Do not invent hardware facts.** Take uncertain dimensions, pin-outs and currents from the
  datasheet, mark them `VERIFY` and ask the student to measure.
- Say so if something requested is technically wrong or unsafe.
- Reports must not contain code. The code is on GitHub, shared with the TA.
- Course rules: WoT Thing Description, a database, a dashboard with high-level analytics, and a
  Fritzing model for the design review.
- Safety: the Peltier's 12 V / ~5 A never goes through the Pi or the carrier PCB, the 12 V line is
  fused, and nobody touches 230 V. The lock output is OFF at start-up and on crash.

## Commands

```bash
# edge (laptop, mock mode)
cd edge && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt && .venv/Scripts/python -m pytest
# backend
cd backend && npm test
# broker
cd broker && ./make-certs.sh <laptop-ip> && docker compose up -d
```

CAD tools are installed but not on PATH:
`"/c/Program Files/FreeCAD 1.1/bin/freecadcmd.exe"` (FreeCAD 1.1.4) and
`"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe"` (KiCad 10.0.3).

## Phase status

- [x] Phase 0: plan and skeleton
- [ ] Phase 1: alarm logic + simulator
- [ ] Phase 2: real edge drivers + bring-up + Fritzing wiring list
- [ ] Phase 3: back end
- [ ] Phase 4: dashboard + seed data
- [ ] Phase 5: keypad, lock, QR unlock
- [ ] Phase 6: FreeCAD enclosure
- [ ] Phase 7: KiCad carrier PCB
- [ ] Phase 8: end-to-end test + demo script
