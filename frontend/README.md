# Dashboard (React + Vite)

Live data comes straight from Firestore (real-time listeners). The back end is called only for
actions (acknowledge, thresholds) and the SMS contacts. Light theme, works on a phone.

| Page | What it shows |
|---|---|
| Login | Firebase email/password |
| Overview | Status banner (OK / WARNING / ALARM / OFFLINE), live cards, "last updated X s ago", **Acknowledge alarm** (supervisors), latest events |
| History | Internal + ambient temperature, safe band shaded, door-open (blue) and power-cut (red) periods; 1 h / 24 h (raw readings) / 7 days (hourly averages with min–max band) |
| Analytics | % time in range per day, excursions (count, total, longest), door openings per day and the longest, power cuts, min / max / mean, **mean kinetic temperature** |
| Excursions | Table with start, end, duration, min, max, likely cause; CSV export |
| Events | All events with a type filter, and the access log |
| Settings | Supervisors: thresholds and delays, SMS contacts |
| Door QR | Supervisors: printable QR label for the fridge, pointing to `/unlock/<unit>` |
| `/unlock/:unitId` | Phone page opened by the QR code: sign in, unit status, big **Unlock door** button (supervisors), last 5 accesses |

The QR code is only a link and holds no secret. Unlocking needs a signed-in supervisor (the back end
checks the Firebase token and role), and the node logs every unlock with the user's email. Viewers
(for example nurses) open the fridge with their keypad PIN. Print the label from the deployed
dashboard, not from localhost, so the code points to the Firebase Hosting address.

## Run

```bash
cd frontend
npm install
npm test            # unit tests of the calculations (vitest)
npm run demo        # demo mode: generated week of data, no Firebase, no back end
```

**Demo mode** needs nothing else: sign in with anything, then use "Simulate a warm probe" in the
yellow bar to see WARNING → ALARM → acknowledge. Its data is `src/demo/demo-data.json`, made by
`npm run seed -- --dump ../frontend/src/demo/demo-data.json` in `backend/` (with `STORE=memory`).

**With Firebase:**

```bash
cp .env.example .env.local    # fill in the web app config from the Firebase console
npm run dev                   # http://localhost:5173 (the back end must allow this origin in CORS_ORIGIN)
```

To have something to look at before the hardware runs, seed the real database once from
`backend/`: `npm run seed` (about 3 300 writes; the free tier allows 20 000 per day).

## Deploy (Firebase Hosting)

```bash
npm run build                          # writes ../firebase/public
cd ../firebase
firebase deploy --only hosting
```

Then add `https://<project-id>.web.app` to the back end's `CORS_ORIGIN`, and set
`VITE_BACKEND_URL` to the Railway URL before building.

## Code layout

| Folder | |
|---|---|
| `src/data/` | `firebaseData.js` (Firestore + Auth + back end calls) and `demoData.js`, same functions |
| `src/lib/` | Pure calculations and formatting (MKT, % in range, periods, CSV), unit-tested |
| `src/pages/` | One file per page |
| `src/components/` | Chart setup (safe band / period shading plugin) and the card |
