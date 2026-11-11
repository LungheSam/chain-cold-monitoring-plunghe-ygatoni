# Web Thing (W3C WoT Thing Description 1.1)

The back end serves the TD at `GET /things/cold-unit-01` with `Content-Type: application/td+json`.
The node itself speaks MQTT; the back end acts as its WoT front end (the TD's `base` is the back end URL).

## Interaction affordances

| Kind | Name | Type | Access | Form |
|---|---|---|---|---|
| property | `internalTemperature` | number, °C, may be null | read-only | `GET /things/{id}/properties/internalTemperature` |
| property | `ambientTemperature` | number, °C | read-only | `GET .../properties/ambientTemperature` |
| property | `humidity` | number, % RH | read-only | `GET .../properties/humidity` |
| property | `doorOpen` | boolean | read-only | `GET .../properties/doorOpen` |
| property | `mainsPower` | boolean | read-only | `GET .../properties/mainsPower` |
| property | `status` | enum `OK`, `WARNING`, `ALARM`, `OFFLINE` | read-only | `GET .../properties/status` |
| property | `outOfRangeSeconds` | integer, s | read-only | `GET .../properties/outOfRangeSeconds` |
| property | `thresholds` | object `{minC, maxC, confirmDelayS, doorLimitS}` | read + write | `GET` and `PUT .../properties/thresholds` |
| all properties | | | read-only | `GET /things/{id}/properties` (op `readallproperties`) |
| action | `acknowledgeAlarm` | no input | supervisor | `POST /things/{id}/actions/acknowledgeAlarm` |
| action | `setThresholds` | same object as `thresholds` | supervisor | `POST .../actions/setThresholds` |
| action | `unlockDoor` | no input (`{seconds}` optional, max 5) | supervisor | `POST .../actions/unlockDoor` |
| events | all event types from `mqtt-topics.md` | | public | `GET /things/{id}/events` (SSE, `subprotocol: "sse"`, op `subscribeallevents`) |

`PUT thresholds` and `POST setThresholds` do the same thing (send the same command). We keep both
because the brief asks for a writable property *and* an action.

Actions are synchronous: the HTTP response comes back once the node answers on `cmd/result` (or
returns `504` after a 10 s timeout, `409` if the unit is offline).

## Security (recommendation)

- **Public (`nosec`)**: the TD, read-only property reads and the SSE event stream. Fridge
  temperatures are not sensitive, and this lets any WoT client (or the TA) try the Thing without a
  Firebase account. The SSE stream carries **no personal data**: access events show the method but
  not the user name.
- **Bearer JWT (Firebase ID token)**: `PUT thresholds` and every action. The TD declares
  `securityDefinitions` with `nosec_sc` and `bearer_sc` (`scheme: "bearer", format: "jwt",
  alg: "RS256"`), and each write form sets `"security": ["bearer_sc"]`.
- Browsers' `EventSource` cannot send an `Authorization` header, which is another reason the event
  stream is public.

## Validation

`backend/test/td.test.js` validates the served TD against the official W3C TD 1.1 JSON Schema
(`backend/test/fixtures/td-schema-v1.1.json`, downloaded from its `$id`
<https://www.w3.org/2022/wot/td-schema/v1.1>), and calls every form in the TD against the running
server. Note: the `main` branch of the `w3c/wot-thing-description` repository holds the draft of the
next TD version and rejects the 1.1 `@context`, so it is not used.

Event forms: `events` (all events) and `events/{TYPE}` (one type), both `subprotocol: "sse"`.
