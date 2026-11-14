# Back end (Node.js)

MQTT ingest, Firestore storage, the W3C **Web Thing** (Thing Description 1.1 + HTTP + SSE),
commands to the node, SMS alerts and the small dashboard API.

| File | What it does |
|---|---|
| `src/index.js` | Entry point: wires MQTT, the store, SMS and the HTTP server |
| `src/ingest.js` | Handles every MQTT message: live state, unit document (≤ 1 write / 15 s), readings (≤ 1 / 60 s), events, excursions with cause guess, access log, offline detection |
| `src/td.js` | Builds the Thing Description |
| `src/wot.js` | WoT routes: properties, actions, events (SSE) |
| `src/commands.js` | Commands to the node with id, 30 s expiry, wait for `cmd/result` |
| `src/sms.js` | SMS rules, 15-min de-duplication, follow-ups, Africa's Talking REST call |
| `src/summaries.js` | Hourly/daily summaries (with MKT) for the dashboard |
| `src/auth.js` | Firebase ID token check and roles (`supervisor`, `viewer`) |
| `src/api.js` | `/api/me` and SMS contacts for the Settings page |
| `src/schemas.js` | Validation of MQTT messages and request bodies (ajv) |
| `src/store/` | Firestore store, and an in-memory store with the same functions |
| `scripts/set-role.js` | Gives a user the supervisor or viewer role |

## Run it

```bash
cd backend
npm install
npm test                 # 47 tests, no network or Firebase needed
npm run broker           # local MQTT broker on mqtt://localhost:1883 (no Docker needed; laptop only)
npm run e2e              # whole chain: in-process MQTT broker + this back end + the mock edge node (1.5 min)
cp .env.example .env
npm run dev
```

**Without Firebase (quick try):** in `.env` set `STORE=memory` and `DEV_AUTH=1`. Then actions work
with the token `dev-supervisor`:

```bash
curl http://localhost:3000/things/cold-unit-01
curl http://localhost:3000/things/cold-unit-01/properties
curl -N http://localhost:3000/things/cold-unit-01/events
curl -X POST -H "Authorization: Bearer dev-supervisor" http://localhost:3000/things/cold-unit-01/actions/acknowledgeAlarm
```

## Firebase setup (once)

1. <https://console.firebase.google.com> → **Add project** (Google Analytics not needed). Stay on the
   free Spark plan.
2. **Firestore Database** → Create database → production mode → choose a location (it cannot be
   changed later; pick the one closest to Rwanda that the console offers).
3. **Authentication** → Get started → enable **Email/Password**. Under **Users**, add an account for
   each team member.
4. **Project settings → Service accounts → Generate new private key**. Save the file as
   `backend/secrets/service-account.json` (git-ignored). Never commit it or send it in chat.
5. Set `FIREBASE_PROJECT_ID` in `.env`, then give the roles:
   ```bash
   npm run set-role -- samuel@example.org supervisor
   npm run set-role -- yves@example.org supervisor
   ```
6. Publish the rules: either paste `firebase/firestore.rules` in the console (Firestore → Rules,
   see `docs/firebase-setup.md`), or deploy them with the Firebase CLI (`npm install -g firebase-tools`):
   ```bash
   cd ../firebase && cp .firebaserc.example .firebaserc   # put your project id in it
   firebase login
   firebase deploy --only firestore:rules,firestore:indexes
   ```
7. Add the SMS contacts from the dashboard's Settings page (Phase 4), or with
   `POST /api/contacts {"name": "...", "phone": "+2507XXXXXXXX"}` and a supervisor token.

## Africa's Talking

- **Sandbox:** create an account at africastalking.com, open the sandbox app, generate an API key,
  set `AT_USERNAME=sandbox` and `AT_API_KEY`. Messages appear in the sandbox **simulator**
  (add the contact's phone number there). They are not delivered to real phones.
- **Live (demo):** use your live app's username and key, top up credit, leave `AT_SENDER_ID` empty.
- We call their REST endpoint `POST /version1/messaging` directly with `fetch`. The `africastalking`
  npm SDK depends on old `axios`/`joi` versions with known high-severity vulnerabilities.

## HTTP interface

| Method and path | Auth | What |
|---|---|---|
| `GET /things`, `GET /things/{id}` | public | Thing Description(s) |
| `GET /things/{id}/properties[/{name}]` | public | live values |
| `PUT /things/{id}/properties/thresholds` | supervisor | `{minC, maxC, confirmDelayS, doorLimitS}` (any subset) → 204 |
| `POST /things/{id}/actions/{acknowledgeAlarm,setThresholds,unlockDoor}` | supervisor | → `{id, ok, error}`; 409 offline, 422 refused by the node, 504 no answer |
| `GET /things/{id}/events[/{type}]` | public | Server-Sent Events |
| `GET /api/me` | signed in | `{uid, email, role}` |
| `GET/POST/PUT/DELETE /api/contacts` | supervisor | SMS contacts |
| `GET /health` | public | online state of each unit |

Auth = header `Authorization: Bearer <Firebase ID token>`.

Deployment on Railway: [docs/deploy-railway.md](../docs/deploy-railway.md).
