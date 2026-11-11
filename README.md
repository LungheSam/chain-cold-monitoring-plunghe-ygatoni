# IoT-Based Cold Chain Monitoring for Vaccine Storage Units

CMU Africa · 04-645 A Internet of Things · Fall 2026
Putshu Lunghe Samuel (plunghe) · Yves Dominique Gatoni (ygatoni)

A Raspberry Pi 4 node watches a vaccine fridge (+2 to +8 °C): internal and ambient temperature,
humidity, door and 12 V power. It raises a local alarm and an SMS, keeps a record of every
temperature excursion, and is exposed as a W3C **Web Thing**. A React dashboard shows live data,
history and analytics.

```
edge (Pi) ──MQTT/TLS──> broker ──> backend (Node.js, WoT TD, SSE) ──> Firestore ──> dashboard (React)
                                         └──> Africa's Talking SMS
```

See [docs/architecture.md](docs/architecture.md) for the full picture.

## Repository layout

| Folder | Contents |
|---|---|
| [edge/](edge/) | Python firmware for the Pi (alarm logic, drivers, mock mode, offline queue) |
| [broker/](broker/) | Mosquitto (Docker) for development, with TLS and passwords |
| [backend/](backend/) | Node.js back end: MQTT ingest, Web Thing API, Firestore, SMS |
| [frontend/](frontend/) | React dashboard and QR unlock page |
| [firebase/](firebase/) | Firestore rules and indexes, hosting config |
| [hardware/](hardware/) | Fritzing, FreeCAD enclosure, KiCad carrier PCB |
| [docs/](docs/) | Architecture, wiring, MQTT topics, Thing Description, data model, decisions |

## Prerequisites

| Tool | For | Notes |
|---|---|---|
| Python 3.11+ | edge | on the Pi it comes with Raspberry Pi OS |
| Node.js 24 LTS | backend, frontend | |
| Docker Desktop | dev broker | or install Mosquitto natively |
| Firebase CLI (`npm i -g firebase-tools`) + Java 21 | rules, hosting, emulators | the emulator needs Java |
| FreeCAD 1.1, KiCad 10, Fritzing | hardware | installed; FreeCAD and KiCad are not on PATH (see CLAUDE.md) |

## Running each part

Secrets go in `.env` files that are never committed. Each part has a `.env.example` to copy.

### 1. Broker (development)

See [broker/README.md](broker/README.md): make the certificates, create the users, then
`docker compose up -d`.

### 2. Edge node

On a laptop (mock hardware):

```bash
cd edge
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Linux/macOS: .venv/bin/pip
cp .env.example .env
.venv/Scripts/python -m pytest
```

On the Pi, see `edge/SETUP.md` (added in Phase 2).

### 3. Back end

```bash
cd backend
cp .env.example .env
npm install
npm test
npm run dev
```

### 4. Dashboard

Added in Phase 4.

## Project phases

| Phase | Content | Status |
|---|---|---|
| 0 | Plan and skeleton | done |
| 1 | Alarm logic + simulator | |
| 2 | Real edge drivers, bring-up, Fritzing wiring list | |
| 3 | Back end (MQTT, Firestore, WoT, SMS, auth) | |
| 4 | Dashboard + seed data | |
| 5 | Keypad, lock, QR unlock | |
| 6 | FreeCAD enclosure | |
| 7 | KiCad carrier PCB | |
| 8 | End-to-end tests and demo script | |
