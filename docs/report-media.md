# Screenshots and photos for the report

The report must not contain code, so pictures carry most of the evidence. Each item says what it
proves and which report section it belongs to. Save them in a `report-media/` folder with the file names
below, so the report and the slides use the same pictures.

## Already made by the scripts (just copy them)

| File | Where it is | Proves | Section |
|---|---|---|---|
| `enclosure-overview.png` | `hardware/freecad/exports/png/overview.png` | all printed parts | Mechanical design |
| `enclosure-lid.png` | `hardware/freecad/exports/png/lid_top.png` and `lid_inside.png` | LCD window, LEDs, buzzer, keypad slot | Mechanical design |
| `enclosure-box.png` | `hardware/freecad/exports/png/box_back.png` | glands, grommet, vents, fixing tabs | Mechanical design |
| `pcb-3d.png` | `hardware/kicad/output/carrier-3d.png` | the carrier board as it would look | Hardware / PCB |
| `pcb-top.png`, `pcb-bottom.png` | `hardware/kicad/output/` | layout, socket underneath, GND pour | Hardware / PCB |
| `schematic.pdf` | `hardware/kicad/output/carrier-schematic.pdf` | the circuit (ERC clean) | Hardware |
| `architecture.png` | render the mermaid diagram in `docs/architecture.md` (GitHub shows it; screenshot it) | system overview | Architecture |

Also quote the check results (numbers, not code): ERC 0 errors, DRC 0 errors with schematic parity,
enclosure fit check passed, 149 unit tests and 34 end-to-end checks passing.

## Screenshots to take

| File | What to capture | Proves | Section |
|---|---|---|---|
| `fritzing-breadboard.png` | Fritzing breadboard view (drawn from `docs/wiring.md`) | wiring (course requirement) | Hardware |
| `dash-overview-ok.png` | Overview page, status OK | live monitoring | Dashboard |
| `dash-overview-alarm.png` | Overview page during an alarm, with the Acknowledge button | alarm reaches the cloud | Dashboard |
| `dash-history-24h.png` | History, 24 h, with a door opening and an excursion visible | readings, safe band, events on the chart | Dashboard |
| `dash-analytics.png` | Analytics page | high-level analytics (course requirement) | Dashboard |
| `dash-excursions.png` | Excursions table + the opened CSV in Excel | stock identification | Dashboard |
| `dash-events-access.png` | Events page with the access log | audit trail | Dashboard / Access |
| `dash-phone.png` | Overview on a phone | mobile use | Dashboard |
| `td-json.png` | `/things/cold-unit-01` in the browser (Firefox shows JSON nicely) | WoT Thing Description (course requirement) | Web of Things |
| `td-sse.png` | `/things/cold-unit-01/events` in the browser while an event happens | WoT events | Web of Things |
| `firestore-console.png` | Firebase console: `units/cold-unit-01` with its `readings`, `events`, `excursions` | the database (course requirement) | Data |
| `emqx-console.png` | EMQX Cloud: connected clients / usage | the broker in use | Architecture |
| `railway-logs.png` | Railway log with "MQTT connected" and an event line | back end deployed | Deployment |
| `sms-phone.png` | The alert SMS and the "back in range" SMS on a phone (hide the number) | SMS alerts | Alerts |
| `unlock-phone.png` | `/unlock/cold-unit-01` on the phone after unlocking | QR unlock | Access |
| `e2e-run.png` | Terminal with the end of `npm run e2e`: "34 passed, 0 failed" | end-to-end test | Testing |
| `journal-alarm.png` | `journalctl -u coldchain-node` during an alarm | the node's own log | Edge |

## Photos to take

Use daylight, a plain background and a ruler or coin for scale where size matters.

| File | What | Proves | Section |
|---|---|---|---|
| `photo-setup.jpg` | the whole setup on the table | the working prototype | Introduction / Results |
| `photo-breadboard.jpg` | the breadboard wiring from above, labels visible | matches the Fritzing model | Hardware |
| `photo-inside-box.jpg` | the open enclosure: Pi, carrier/protoboard, cables in glands | assembly | Mechanical |
| `photo-lcd-ok.jpg`, `photo-lcd-alarm.jpg` | LCD showing `OK` and `ALARM` with the red LED on | local alarm | Edge |
| `photo-keypad-lock.jpg` | keypad on the lid and the solenoid on the door | access extension | Access |
| `photo-probe.jpg` | the DS18B20 probe inside the fridge, cable through the door seal | sensor placement | Sensors |
| `photo-dht-pod.jpg` | DHT22 pod mounted outside | ambient sensing | Sensors |
| `photo-ice-test.jpg` | probe in ice water with the LCD reading next to it (test A1) | sensor accuracy | Testing |
| `photo-qr-label.jpg` | printed QR label on the fridge | QR unlock | Access |

## Tables for the testing section

Copy the filled-in tables from `docs/test-plan.md` (sections A–G) with the measured values, plus the
"Faults found and fixed" table at its end.
