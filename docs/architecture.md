# Architecture

Four layers. **All alarm logic runs on the edge node**, so the buzzer, LED and LCD keep working without Internet.

```mermaid
flowchart LR
  subgraph Edge["1. Perception and edge (Raspberry Pi 4)"]
    S1[DS18B20 internal probe] --> N
    S2[DHT22 ambient] --> N
    S3[Reed switch door] --> N
    S4[12 V sense divider] --> N
    K[4x4 keypad] --> N
    N[coldchain node<br/>alarm logic + timer<br/>SQLite offline queue]
    N --> A1[Buzzer + red/green LED]
    N --> A2[16x2 LCD]
    N --> A3[Solenoid lock]
  end
  subgraph Net["2. Network"]
    B[(MQTT broker<br/>TLS 8883)]
  end
  subgraph Cloud["3. Cloud / Web of Things"]
    BE[Node.js back end<br/>WoT TD + HTTP + SSE]
    FS[(Firestore)]
    AT[Africa's Talking SMS]
  end
  subgraph App["4. Application"]
    D[React dashboard]
    Q[QR unlock page]
  end
  N <-->|telemetry, event, status / cmd| B
  B <--> BE
  BE --> FS
  BE --> AT
  FS -->|real-time listeners| D
  D -->|actions + ID token| BE
  Q -->|unlockDoor + ID token| BE
```

## Data flow

1. The node reads the sensors every ~2 s, runs the alarm state machine and drives the local outputs.
2. It publishes telemetry (every 30 s or on a 0.2 °C change), events and a retained `online` status.
   If the broker is unreachable, messages go into a SQLite queue and are sent in order later.
3. The back end subscribes, keeps the latest state in memory (for the WoT property reads), writes to
   Firestore, pushes events to SSE clients and decides on SMS.
4. The dashboard reads Firestore directly with real-time listeners. It calls the back end only for
   actions, with a Firebase ID token.
5. Actions become MQTT commands with an ID, a 30 s expiry and an HMAC signature. The node replies
   on `cmd/result`, and the back end returns that result in the HTTP response.

## What still works when

| Failure | Local alarm | Dashboard | SMS |
|---|---|---|---|
| Internet / Wi-Fi down | yes | shows OFFLINE after LWT or 2 min silence | "offline" SMS from the back end |
| Mains (12 V) cut | yes (Pi on UPS) | yes, if the Wi-Fi router is still powered | yes |
| Back end down | yes | shows stale data ("last updated" grows) | no |
| Pi off / crashed | no | OFFLINE (LWT) | "offline" SMS |

Known limit: SMS goes out from the cloud, so a site with no Internet gets no SMS. A GSM module
(e.g. SIM800) on the node would fix this; it is future work, not in scope.
