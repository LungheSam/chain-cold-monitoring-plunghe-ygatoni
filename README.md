# IoT-Based Cold Chain Monitoring for Vaccine Storage Units

CMU Africa · 04-645 A Internet of Things · Fall 2026
Putshu Lunghe Samuel (plunghe) · Yves Dominique Gatoni (ygatoni)

A Raspberry Pi 4 node watches a vaccine fridge (+2 to +8 °C): internal and ambient temperature,
humidity, door and 12 V power. It raises a local alarm and an SMS, keeps a record of every
temperature excursion, and is exposed as a W3C **Web Thing**. A React dashboard shows live data,
history and analytics. Extension: keypad PIN, solenoid lock and a QR unlock page.

```
edge (Pi) ──MQTT/TLS──> EMQX Cloud ──> back end (Railway: Node.js, WoT TD, SSE) ──> Firestore
                                               │                                     │
                                               └──> Africa's Talking SMS              └──> dashboard (Railway: React)
```

See [docs/architecture.md](docs/architecture.md) for the full picture.

## Where it runs

| Part | Service | Guide |
|---|---|---|
| MQTT broker | EMQX Cloud Serverless (free, TLS 8883) | [docs/deploy-railway.md](docs/deploy-railway.md) step 1 |
| Back end | Railway (service 1, root `backend/`) | [docs/deploy-railway.md](docs/deploy-railway.md) |
| Dashboard + unlock page | Railway (service 2, root `frontend/`) | [docs/deploy-railway.md](docs/deploy-railway.md) |
| Database + sign-in | Firebase (Firestore + Authentication) | [docs/firebase-setup.md](docs/firebase-setup.md) |
| SMS | Africa's Talking | [backend/README.md](backend/README.md) |

Why these choices (and why not HiveMQ or Firebase Hosting): [docs/decisions.md](docs/decisions.md) D3, D4, D18.

## Repository layout

| Folder | Contents |
|---|---|
| [edge/](edge/) | Python firmware for the Pi (alarm logic, drivers, keypad and lock, mock mode, offline queue) |
| [backend/](backend/) | Node.js back end: MQTT ingest, Web Thing API, Firestore, SMS, local test broker |
| [frontend/](frontend/) | React dashboard (light/dark), QR unlock page, small server for Railway |
| [firebase/](firebase/) | Firestore security rules and indexes |
| [broker/](broker/) | Mosquitto configuration (Docker), kept as a fallback broker |
| [hardware/](hardware/) | Fritzing wiring list, FreeCAD enclosure, KiCad carrier PCB |
| [docs/](docs/) | Architecture, wiring, MQTT topics, Thing Description, data model, decisions, [components list](docs/components.md), [purchase request](docs/purchase-request.md) ([Excel](docs/purchase-request.xlsx)), [test plan](docs/test-plan.md), [demo script](docs/demo-script.md), [report pictures](docs/report-media.md) |

## Prerequisites

| Tool | For | Notes |
|---|---|---|
| Python 3.11+ | edge | on the Pi it comes with Raspberry Pi OS |
| Node.js 24 LTS | backend, frontend | |
| FreeCAD 1.1, KiCad 10, Fritzing | hardware | FreeCAD and KiCad are not on PATH (paths in docs/decisions.md) |

Docker is not needed: `npm run broker` gives a local MQTT broker for testing.

## Running it on a laptop

Secrets go in `.env` files that are never committed. Each part has a `.env.example` to copy:
`backend/.env`, `edge/.env`, `frontend/.env.local`.

**First time:**

```bash
cd backend && npm install && npm test
cd ../frontend && npm install && npm test
cd ../edge && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt && .venv/Scripts/python -m pytest
```

**Without any account** (memory store, local broker, demo dashboard):

```bash
cd backend && npm run broker       # terminal 1: local MQTT broker
cd backend && npm run dev          # terminal 2: back end (STORE=memory, DEV_AUTH=1 in backend/.env)
cd edge && .venv/Scripts/python -m coldchain.node    # terminal 3: simulated fridge (type `help`)
cd frontend && npm run demo        # terminal 4: dashboard with a generated week of data
```

**With the real services** (Firebase, EMQX: `backend/.env`, `edge/.env` and `frontend/.env.local` filled in):

```bash
cd backend && npm run check        # tests both MQTT logins and Firestore, prints no secrets
cd backend && npm run dev          # http://localhost:8080
cd edge && .venv/Scripts/python -m coldchain.node
cd frontend && npm run dev         # http://localhost:5173
```

In the node's terminal, `temp 9.5` makes the fridge too warm: WARNING at once, ALARM after 20 s.
More: [edge/README.md](edge/README.md), [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md).
On the Pi: [edge/SETUP.md](edge/SETUP.md).

**Whole chain in one command** (in-process broker + back end + simulated node, 34 checks):

```bash
cd backend && npm run e2e
```

## Project phases

| Phase | Content | Status |
|---|---|---|
| 0 | Plan and skeleton | done |
| 1 | Alarm logic + simulator | done |
| 2 | Real edge drivers, bring-up, Fritzing wiring list | done (not yet run on the Pi) |
| 3 | Back end (MQTT, Firestore, WoT, SMS, auth) | done, running against the real Firestore and EMQX |
| 4 | Dashboard + seed data | done, running against Firebase; light and dark themes |
| 5 | Keypad, lock, QR unlock | done (mock keypad and lock; not yet on the Pi) |
| 6 | FreeCAD enclosure | done (script runs headless, all parts valid; dimensions to VERIFY before printing) |
| 7 | KiCad carrier PCB | done (ERC/DRC clean, Gerbers ready; header position and parts to VERIFY before ordering) |
| 8 | End-to-end tests and demo script | done (`npm run e2e`: 34/34; system tests on the Pi to do, see docs/test-plan.md) |

Next: deploy on Railway ([docs/deploy-railway.md](docs/deploy-railway.md)), then the Pi bring-up.
