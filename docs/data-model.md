# Firestore data model

Only the back end writes (Admin SDK). The dashboard only reads (see `firebase/firestore.rules`).
Timestamps are Firestore `Timestamp`s. Field names are camelCase.

## Collections

### `units/{unitId}`: live state (one document per fridge)

```
name, location
status: "OK" | "WARNING" | "ALARM" | "OFFLINE"
online: bool, lastSeen: Timestamp, lastTelemetryTs: Timestamp
internalTemp, ambientTemp, humidity: number | null
doorOpen: bool, mainsPower: bool
outOfRangeSeconds: number           // cumulative, from the node
activeAlarms: ["OUT_OF_RANGE_HIGH", ...], acknowledged: bool
thresholds: {minC: 2.0, maxC: 8.0, confirmDelayS: 300, doorLimitS: 120}
```

### `units/{unitId}/readings/{autoId}`: one reading per minute at most

```
ts, internalTemp, ambientTemp, humidity, doorOpen, mainsPower, status
```

### `units/{unitId}/hourly/{YYYYMMDDHH}` and `units/{unitId}/daily/{YYYYMMDD}`: pre-computed summaries

```
start, count, minTemp, maxTemp, sumTemp (→ mean), sumArrhenius (→ MKT), countAmbient, sumAmbient,
secondsInRange, secondsOutOfRange, doorOpenings, doorOpenSeconds, longestDoorOpenS,
powerCuts, powerCutSeconds
```

These exist only to keep Firestore reads low (see the arithmetic below). The 7-day chart and the
analytics page read these, not the raw readings.

### `units/{unitId}/events/{eventId}`

`eventId` is the UUID made by the node (so a duplicate delivery overwrites, not duplicates).

```
ts, type, details, receivedAt, delayed: bool, smsSent: bool
```

### `units/{unitId}/excursions/{excursionId}`

```
start, end (null while open), durationS, outOfRangeSeconds, minTemp, maxTemp,
direction: "HIGH" | "LOW", confirmed: bool,
causeGuess: "door" | "power" | "unknown"     // door open or power lost overlapping the start
```

### `units/{unitId}/access/{eventId}`

```
ts, result: "GRANTED" | "DENIED", method: "keypad" | "qr", user (PIN owner's name or supervisor email; null for a wrong PIN),
details (the event details: seconds, or reason / attempt / lockedOutS)
```

### `users/{uid}`

```
email, displayName, role: "supervisor" | "viewer"
```

Created by hand (or by a small admin script) after the person signs up in Firebase Auth.

### `contacts/{contactId}`

```
name, phone ("+2507XXXXXXXX"), units: ["cold-unit-01"], active: bool
```

### `smsLog/{autoId}` and `smsState/{unitId}` (back end only, not readable by clients)

```
smsLog:   ts, unitId, type, kind: "alert" | "clear", to, message, providerStatus
smsState: lastAlertAt: {<eventType>: ms}, open: {<problem>: {sentAt, ts}}
```

`smsLog` is the audit trail. `smsState` holds the 15-minute de-duplication and which alerts still
wait for a follow-up, so both survive a back end restart.

## Indexes

Every dashboard query filters and sorts on one field only (`ts` or `start`): readings, summaries
and events by time range, the latest events / excursions / access entries. Firestore creates those
single-field indexes automatically, so `firebase/firestore.indexes.json` is empty. Filtering events
by type happens in the browser.

## Free-tier arithmetic (Spark plan: 50 000 reads, 20 000 writes per day)

Writes per day, one unit:

| What | Rule | Writes/day |
|---|---|---|
| unit document | at most every 15 s, plus on status/door/power change | ≤ 5 760 + ~100 |
| readings | at most 1 per 60 s | 1 440 |
| hourly summaries | written once per hour | 24 |
| daily summaries | once per day | 1 |
| events + excursions + access + SMS log | maybe 50–200 on a busy demo day | ≤ 200 |
| **Total** | | **≈ 7 500 (≈ 38 % of 20 000)** |

In normal running telemetry arrives every 30 s, so the unit document is about 2 880 writes/day and
the total is ≈ 4 600 (23 %).

Reads per day:

| What | Reads |
|---|---|
| Overview listener on the unit doc: 1 read per change per open dashboard | ≈ 2 880 per open tab per day |
| History 1 h (raw readings) | 60 per load |
| History 24 h (raw readings) | 1 440 per load |
| History 7 days (hourly summaries) | 168 per load |
| Analytics 30 days (daily summaries) | 30 per load |

If the 7-day chart read raw readings it would cost 10 080 reads per load, so 5 loads would use the
whole daily quota. That is why the hourly and daily summaries exist.

**Seeding a week of fake data writes ~10 000 documents**, half the daily write quota. Seed the
**Firestore emulator** during development, and seed the real project at most once.
