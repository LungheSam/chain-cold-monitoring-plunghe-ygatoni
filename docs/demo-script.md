# Open Day demo (Wed 2 Dec 2026): 5-minute script

Two presenters: **S** = Samuel (hardware side), **Y** = Yves (dashboard side). The node runs with
`PROFILE=demo` (alarm confirmed after 20 s, door after 15 s, power cut after 3 s), so everything
happens in front of the audience. Say once that a real fridge uses 5 min / 2 min / 5 s.

## On the table

- The cooler box (Peltier fridge), the probe inside, the Pi box with LCD, LEDs, buzzer and keypad, the
  DHT22 pod outside, reed switch and solenoid lock on the door.
- Laptop on the dashboard Overview page (full screen), second tab on the Analytics page.
- Supervisor phone: signed in to the dashboard, ready to receive the SMS. Printed Door QR label on the fridge.
- A small flask of warm water (about 30 °C) and a cup of ice water. A towel.
- Poster or slide: architecture diagram, enclosure and PCB renders.

## Run sheet

| Time | Who | Do | Say (key points) |
|---|---|---|---|
| 0:00 | S | Point at the fridge | Vaccines must stay between +2 and +8 °C. If a fridge fails at night nobody knows, and nobody can tell which vials were too warm, and for how long. |
| 0:30 | Y | Point at each sensor, then the dashboard | Probe inside, ambient sensor outside, door switch, 12 V supply sense. The Pi decides alarms by itself, so the alarm works without Internet. Live data on the dashboard. |
| 1:00 | S | Put the probe in the warm water | LCD shows WARNING at once. We wait 20 s before alarming, so opening the door to take vials out does not cause false alarms. |
| 1:25 | S | (alarm starts) | Buzzer, red LED, LCD `ALARM`. |
| 1:30 | Y | Show the red dashboard, hold up the phone | Dashboard turned red; the supervisor got an SMS. |
| 1:45 | S | Type `#` PIN `#` on the keypad | Acknowledge with your PIN: the buzzer stops, the red LED keeps blinking until the temperature is back. The name is logged. |
| 2:00 | S | Probe into the ice water, then back in the fridge | We count every second outside 2–8 °C from the first bad reading. |
| 2:15 | Y | Excursions page | Each excursion: start, end, minimum, maximum and the likely cause. This tells the pharmacist which stock to check. CSV export for their records. |
| 2:40 | S | Open the fridge door and leave it | Door open too long: alarm after 15 s. Every opening is logged with its duration. Close it. |
| 3:00 | S | Unplug the 12 V adapter, plug it back | Power cut detected in 3 s; the Pi stays on its own supply and reports when power returns. |
| 3:15 | S | Type the PIN then `#` | The lock clicks open for 5 s: access only with a PIN, three wrong PINs lock the keypad for a minute. |
| 3:35 | Y | Scan the QR label with the phone, press Unlock | Supervisors can also open it from their phone. Both openings appear in the access log with the person's name. |
| 4:00 | Y | Analytics tab | A week of history (generated test data, say so): % of time in range, excursions, door openings, power cuts, mean kinetic temperature. |
| 4:20 | Y | Open `/things/cold-unit-01` in a new tab | The fridge is a W3C Web Thing: any WoT client can read its properties, call its actions and subscribe to its events. |
| 4:40 | S | Point at the poster | If Wi-Fi drops, the Pi queues every event and sends it later with the right time. Enclosure printed in PETG, and a carrier PCB designed in KiCad. Questions? |

## Checklist

**The day before**
- [ ] `PROFILE=demo` in `edge/.env` on the Pi; `sudo systemctl restart coldchain-node`
- [ ] Both Railway services up: back end `/health` answers; its `CORS_ORIGIN` includes the dashboard's Railway URL
- [ ] SMS contacts set in Settings (both phones); Africa's Talking **live** account with credit
      (the sandbox does not send to real phones). Send one test alert and time it.
- [ ] Analytics history: `npm run seed` in `backend/` against the real project (about 3 300 writes)
- [ ] Keypad PIN for each presenter (`python -m coldchain.pins add <name>`); Door QR label printed from the deployed dashboard
- [ ] Phone hotspot configured on the Pi as a second Wi-Fi network (in case the venue Wi-Fi blocks MQTT on 8883)
- [ ] Run the whole script twice

**30 minutes before**
- [ ] Fridge cold (below 8 °C) for at least 20 min; dashboard OK and green
- [ ] Reset the out-of-range total so the audience sees it start from zero:
      `sudo systemctl stop coldchain-node && rm ~/coldchain/edge/data/state.json && sudo systemctl start coldchain-node`
- [ ] Warm water flask filled, ice water, towel, chargers, extension lead
- [ ] Laptop: dashboard signed in, browser zoom large enough to read from 2 m

**Between visitor groups** (2 min): close the door, probe back in the fridge, wait for OK on the LCD.

## If something fails

| Problem | What to do |
|---|---|
| Venue Wi-Fi down or MQTT blocked | Switch the Pi to the phone hotspot. Meanwhile show that the **local alarm still works** (that is the design) and that events will arrive later. |
| Cloud back end down | Show the local alarm and LCD; show the dashboard in demo mode on the laptop (`npm run demo` in `frontend/`). |
| SMS late | Carry on; show the SMS when it arrives (Africa's Talking delivery can take up to a minute). |
| Probe warms too slowly | Hold it in a closed hand; the confirm delay is 20 s once it passes 8 °C. |
| Lock does not click | Check the 5 V lock adapter is plugged in; the rest of the demo does not depend on it. |
