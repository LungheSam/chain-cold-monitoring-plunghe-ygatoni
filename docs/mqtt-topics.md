# MQTT topics

Unit ID: `cold-unit-01`. All payloads are UTF-8 JSON. `ts` is milliseconds since the Unix epoch (UTC).

| Topic | Direction | QoS / retain | Payload |
|---|---|---|---|
| `coldchain/{unitId}/telemetry` | node → cloud | 1 | `{ts, internalTemp, ambientTemp, humidity, doorOpen, mainsPower, status, outOfRangeSeconds, timeSynced}` |
| `coldchain/{unitId}/event` | node → cloud | 1 | `{id, ts, type, details, timeSynced}` |
| `coldchain/{unitId}/status` | node → cloud | 1, **retained** | `"online"` / `"offline"` (LWT) |
| `coldchain/{unitId}/cmd` | cloud → node | 1 | `{id, action, params, expiresAt, sig}` |
| `coldchain/{unitId}/cmd/result` | node → cloud | 1 | `{id, ok, error}` |

## Telemetry

- Sent every 30 s, or at once when the internal temperature has changed by more than 0.2 °C since
  the last message. At most one message every 5 s, so a fast change cannot flood the broker.
- `internalTemp`, `ambientTemp` and `humidity` are `null` when the sensor has failed.
- `status` is `OK`, `WARNING` or `ALARM` (the back end adds `OFFLINE`). See `decisions.md` (D9).
- `timeSynced` is `false` if the Pi clock was not NTP-synchronised when the message was made
  (see D6). The back end then trusts its own receive time for live state.

## Events

`type` is one of:

`OUT_OF_RANGE_HIGH`, `OUT_OF_RANGE_LOW`, `BACK_IN_RANGE`, `DOOR_OPEN_TOO_LONG`, `DOOR_CLOSED`,
`POWER_LOST`, `POWER_RESTORED`, `SENSOR_FAULT`, `ALARM_ACKNOWLEDGED`, `ACCESS_GRANTED`, `ACCESS_DENIED`.

- `id` is a UUID made on the node, so the back end can drop duplicates (QoS 1 can deliver twice, and
  the offline queue can resend).
- `details` examples:
  - `OUT_OF_RANGE_HIGH`: `{temp: 9.4, limit: 8.0, since: <ts left range>, outOfRangeSeconds}`
  - `BACK_IN_RANGE`: `{durationS, minTemp, maxTemp, excursionId}`
  - `POWER_RESTORED`: `{durationS}`
  - `SENSOR_FAULT`: `{sensor: "ds18b20" | "dht22", reason: "missing" | "85C" | "read_error"}`
  - `ACCESS_GRANTED`: `{user, method: "keypad" | "qr"}`

## Commands

- `action`: `acknowledgeAlarm`, `setThresholds`, `unlockDoor`.
- `expiresAt` = send time + 30 s. The node ignores a command that has expired, or whose `id` it has
  already seen (it keeps the last 100 IDs).
- `sig` = HMAC-SHA256 of `id|action|expiresAt|JSON(params)` with the shared `CMD_HMAC_SECRET`.
  The node rejects a command with a bad signature (D11).
- The node always answers on `cmd/result` with the same `id`.

## Online / offline

- The node connects with a Last Will on `status` = `"offline"` (QoS 1, retained), then publishes a
  retained `"online"`.
- The back end also keeps `lastSeen` and treats a unit silent for > 2 min as offline, because the
  broker only fires the LWT after the keep-alive (60 s × 1.5) runs out.

## Offline queue on the node

- SQLite file `DATA_DIR/queue.db`, one row per message, sent in insertion order on reconnect.
- **Events are never dropped.** Telemetry is thinned when the queue is large: keep at most one
  telemetry message per minute of backlog (enough for the history chart).
- The back end must not overwrite the unit's live state with an older buffered message: it only
  updates live state when `ts` is newer than the stored `lastTelemetryTs`.
