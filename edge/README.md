# Edge node

Python code for the Raspberry Pi 4. All alarm logic runs here, so the local alarm works without Internet.

| File | What it does |
|---|---|
| `coldchain/alarm.py` | **Alarm engine** (pure, no hardware): confirm delays, hysteresis, door/power, sensor faults, out-of-range timer, excursion records, acknowledge |
| `coldchain/clock.py` | Real clock (with NTP check) and `FakeClock` for tests |
| `coldchain/store.py` | Atomic JSON save (temp file + rename) |
| `coldchain/telemetry.py` | When to send telemetry (30 s / 0.2 °C / status change) |
| `coldchain/display.py` | Text for the 16x2 LCD |
| `coldchain/commands.py` | Commands from the back end (expiry, repeated IDs) |
| `coldchain/mqtt_link.py` | MQTT over TLS, Last Will, command subscription, PUBACK tracking |
| `coldchain/outbox.py` | SQLite offline queue: events never lost, telemetry thinned, re-timing after NTP sync |
| `coldchain/sysfs.py` | DS18B20 and DHT22 readers (sysfs / IIO), Wi-Fi state, boot id |
| `coldchain/hardware.py` | Real Pi drivers (gpiozero): reed, mains, LEDs, buzzer, LCD, lock output (OFF at start) |
| `coldchain/keypad.py` | 4x4 keypad scanner (thread, 20 ms scan, debounce) |
| `coldchain/pins.py` | Keypad PINs as salted PBKDF2 hashes in `pins.json`; `python -m coldchain.pins add <name>` |
| `coldchain/access.py` | Lock pulse timer (5 s max, 5 s rest), PIN entry, 3-strike lockout, `#`+PIN acknowledge, QR unlock |
| `systemd/coldchain-node.service` | Service file with the pin safety net (`ExecStopPost`) |
| `tests/hw/` | One hardware test script per part, run on the Pi |
| `coldchain/mock.py` | Fake sensors, LEDs, buzzer and LCD for `MOCK_HARDWARE=1` |
| `coldchain/node.py` | Main loop that ties it all together |
| `scenarios/demo.txt` | Scripted run: heat, ack, door, power cut, probe fault |
| `scenarios/keypad.txt` | Scripted run: PIN unlock, 3 wrong PINs and lockout, `#`+PIN acknowledge |

## Run on a laptop (mock hardware)

```bash
cd edge
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
cp .env.example .env                              # then set the MQTT user and password
.venv/Scripts/python -m pytest                    # unit tests
.venv/Scripts/python -m coldchain.node --no-mqtt  # simulator without a broker
.venv/Scripts/python -m coldchain.node            # simulator publishing to the broker in .env
.venv/Scripts/python -m coldchain.node --script scenarios/demo.txt
```

Simulator commands (type them and press Enter):

| Command | Effect |
|---|---|
| `heat` / `cool` / `normal` | temperature drifts to 12 / 0 / 5 °C at 0.1 °C/s |
| `temp 9.5` | jump to 9.5 °C |
| `door`, `door open`, `door close` | door |
| `power`, `power off`, `power on` | 12 V supply |
| `probe 85`, `probe -127`, `probe missing`, `probe ok` | DS18B20 faults |
| `dht fail`, `dht ok` | DHT22 fault |
| `key 1234#` | type on the keypad (needs `KEYPAD_INSTALLED=1`) |
| `ack` | acknowledge the alarm (without a PIN) |
| `status` | show the LCD and the state |
| `quit` | stop (state is saved) |

## Keypad and lock (extension)

| Keys | Effect |
|---|---|
| `PIN #` | right PIN: lock open for 5 s, `ACCESS_GRANTED {user, method: "keypad"}`; wrong PIN: `ACCESS_DENIED` |
| `# PIN #` | acknowledge the alarm (buzzer off); the door stays locked |
| `*` | clear what was typed (also forgotten after 10 s) |

Three wrong PINs in a row lock the keypad for 60 s (the third `ACCESS_DENIED` has `lockedOutS: 60`).
The LCD's second line shows `PIN ****`, then the result for 3 s. A QR unlock (`unlockDoor` command)
uses the same lock timer. After each pulse the lock rests 5 s before it can open again.

PINs are 4 to 8 digits, one per person, stored only as salted hashes in `pins.json` (git-ignored):

```bash
.venv/Scripts/python -m coldchain.pins add Samuel     # asks for the PIN twice
.venv/Scripts/python -m coldchain.pins list
.venv/Scripts/python -m coldchain.pins remove Samuel
.venv/Scripts/python -m coldchain.node --no-mqtt --script scenarios/keypad.txt
```

The out-of-range total and excursions are saved in `data/state.json` (git-ignored). Delete that
file to start from zero.

To watch the MQTT traffic of the dev broker:

```bash
mosquitto_sub -h localhost -p 8883 --cafile ../broker/mosquitto/certs/ca.crt -u dev -P 'PASSWORD3' -t 'coldchain/#' -v
```

## Run on the Pi

See [SETUP.md](SETUP.md): config.txt lines, install, the bring-up checklist (one part at a
time, with `tests/hw/` scripts) and the systemd service.
