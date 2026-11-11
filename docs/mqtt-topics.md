# MQTT topics

Unit ID: `cold-unit-01`. All payloads are UTF-8 JSON. `ts` is milliseconds since the Unix epoch (UTC).

| Topic | Direction | QoS / retain | Payload |
|---|---|---|---|
| `coldchain/{unitId}/telemetry` | node → cloud | 1 | `{ts, internalTemp, ambientTemp, humidity, doorOpen, mainsPower, status, outOfRangeSeconds, timeSynced}` |
| `coldchain/{unitId}/event` | node → cloud | 1 | `{id, ts, type, details, timeSynced}` |
| `coldchain/{unitId}/status` | node → cloud | 1, **retained** | `"online"` / `"offline"` (LWT) |
| `coldchain/{unitId}/cmd` | cloud → node | 1 | `{id, action, params, expiresAt}` |
| `coldchain/{unitId}/cmd/result` | node → cloud | 1 | `{id, ok, error}` |

## Telemetry

- Sent every 30 s, or at once when the internal temperature has changed by more than 0.2 °C since
  the last message. At most one message every 5 s, so a fast change cannot flood the broker.
- `internalTemp`, `ambientTemp` and `humidity` are `null` when the sensor has failed.
- `status` is `OK`, `WARNING` or `ALARM` (the back end adds `OFFLINE`). See `decisions.md` (D9).
- `timeSynced` is `false` if the Pi clock was not NTP-synchronised when the message was made.
  The node holds such messages in its queue and fixes their `ts` once the clock syncs (D6), so in
  practice the back end only sees `timeSynced: true`. If one arrives anyway, the back end uses its
  own receive time for live state.

## Events

`type` is one of:

`OUT_OF_RANGE_HIGH`, `OUT_OF_RANGE_LOW`, `BACK_IN_RANGE`, `DOOR_OPEN_TOO_LONG`, `DOOR_CLOSED`,
`POWER_LOST`, `POWER_RESTORED`, `SENSOR_FAULT`, `SENSOR_RESTORED`, `ALARM_ACKNOWLEDGED`,
`ACCESS_GRANTED`, `ACCESS_DENIED`.

`SENSOR_RESTORED` was added to the original list, so the back end knows when a sensor fault has
cleared (needed for the "problem cleared" SMS).

When each event is sent:

- `OUT_OF_RANGE_*`: when the alarm is confirmed (after `TEMP_CONFIRM_S`).
- `BACK_IN_RANGE`: when **any** excursion closes, including a short blip that never alarmed
  (`confirmed: false`). The back end stores every excursion, but sends the "cleared" SMS only for
  confirmed ones.
- `DOOR_CLOSED`: after **every** door opening, with `openSeconds` and `alarmed`. This gives the
  dashboard the number and length of door openings. The "cleared" SMS is only for `alarmed: true`.
- `POWER_LOST` / `POWER_RESTORED`: after `POWER_CONFIRM_S`. `durationS` is measured from the first
  LOW sample to the first HIGH sample.

- `id` is a UUID made on the node, so the back end can drop duplicates (QoS 1 can deliver twice, and
  the offline queue can resend).
- `details` (as implemented in `edge/coldchain/alarm.py`):
  - `OUT_OF_RANGE_HIGH|LOW`: `{temp, limit, since (ms, when it left the range), excursionId, outOfRangeSeconds}`
  - `BACK_IN_RANGE`: the full excursion record `{excursionId, id, direction, start, end, durationS,
    outOfRangeSeconds, offlineGapS, offlineGapUnknown, minTemp, maxTemp, confirmed}`
  - `DOOR_OPEN_TOO_LONG`: `{openSeconds, limitS}`; `DOOR_CLOSED`: `{openSeconds, alarmed}`
  - `POWER_LOST`: `{}`; `POWER_RESTORED`: `{durationS}`
  - `SENSOR_FAULT`: `{sensor: "ds18b20" | "dht22", reason: "read_error" | "85C" | "-127C"}`;
    `SENSOR_RESTORED`: `{sensor}`
  - `ALARM_ACKNOWLEDGED`: `{by, alarms: ["TEMP_HIGH", "DOOR_OPEN", ...]}`
  - `ACCESS_GRANTED` (Phase 5): `{user, method: "keypad" | "qr"}`

## Commands

- `action`: `acknowledgeAlarm`, `setThresholds`, `unlockDoor`.
- `expiresAt` = send time + 30 s. The node ignores a command that has expired, or whose `id` it has
  already seen (it keeps the last 100 IDs).
- Security is TLS plus broker passwords: only the back end's MQTT user may publish on `cmd` (D11).
- The node always answers on `cmd/result` with the same `id`.

## Online / offline

- The node connects with a Last Will on `status` = `"offline"` (QoS 1, retained), then publishes a
  retained `"online"`.
- The back end also keeps `lastSeen` and treats a unit silent for > 2 min as offline, because the
  broker only fires the LWT after the keep-alive (60 s × 1.5) runs out.

## Offline queue on the node

Phase 1 (now): events are kept in memory while offline and sent on reconnect; telemetry is dropped.
Phase 2 replaces this with the SQLite queue below, which also survives a reboot.

- SQLite file `DATA_DIR/queue.db`, one row per message, sent in insertion order on reconnect.
- **Events are never dropped.** Telemetry is thinned when the queue is large: keep at most one
  telemetry message per minute of backlog (enough for the history chart).
- The back end must not overwrite the unit's live state with an older buffered message: it only
  updates live state when `ts` is newer than the stored `lastTelemetryTs`.
