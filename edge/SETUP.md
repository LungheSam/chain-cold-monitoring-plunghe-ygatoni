# Raspberry Pi setup and bring-up

Pi 4 Model B, Raspberry Pi OS 64-bit (Bookworm or Trixie, both work). Commands run on the Pi over SSH
unless noted. Wiring for each part: `docs/wiring.md`.

## 1. Flash the SD card (on the laptop)

Raspberry Pi Imager → Raspberry Pi OS (64-bit). In the settings: hostname `coldchain-pi`, your user
name and password, the Wi-Fi network, the time zone `Africa/Kigali`, and **enable SSH**.

```bash
ssh <user>@coldchain-pi.local
```

## 2. Packages

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-gpiozero python3-lgpio i2c-tools
```

## 3. Interfaces: `/boot/firmware/config.txt`

```bash
sudo nano /boot/firmware/config.txt
```

Add at the end, under `[all]`:

```
# Cold chain monitor
dtparam=i2c_arm=on
dtoverlay=w1-gpio,gpiopin=4
dtoverlay=dht11,gpiopin=17
```

(`sudo raspi-config nonint do_i2c 0` does the same as the `dtparam` line.) Then reboot:

```bash
sudo reboot
```

After the reboot, with the sensors wired:

```bash
ls /sys/bus/w1/devices/             # a 28-xxxxxxxxxxxx folder = DS18B20 found
cat /sys/bus/iio/devices/*/name     # a line starting with dht11 = DHT driver loaded
i2cdetect -y 1                      # 27 (or 3f) = LCD backpack found
groups                              # must include gpio and i2c; if not: sudo usermod -aG gpio,i2c $USER
timedatectl                         # "System clock synchronized: yes"
which pinctrl                       # /usr/bin/pinctrl (used by the service as a safety net)
```

## 4. Code

```bash
git clone <your GitHub repo URL> ~/coldchain
cd ~/coldchain/edge
python3 -m venv --system-site-packages .venv     # so gpiozero/lgpio come from the OS
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                     # all unit tests must pass on the Pi too
cp .env.example .env
nano .env                                         # MOCK_HARDWARE=0, PROFILE, MQTT settings
```

MQTT settings in `.env`:

- **Dev broker on the laptop**: `MQTT_HOST=<laptop LAN IP>`, `MQTT_PORT=8883`, and copy the CA
  certificate from the laptop:
  `scp broker/mosquitto/certs/ca.crt <user>@coldchain-pi.local:~/coldchain/broker/mosquitto/certs/`
  (create that folder first). The laptop certificate must include its LAN IP (`./make-certs.sh <ip>`).
- **HiveMQ Cloud**: `MQTT_HOST=<cluster>.hivemq.cloud`, `MQTT_PORT=8883`, `MQTT_CA_FILE=` (empty).

## 5. Bring-up checklist: one part at a time

Rules: **shut the Pi down before changing wires** (`sudo shutdown -h now`, then unplug). Add one
part, run its test, tick it, then go on. Each test prints the wiring it expects and PASS/FAIL.
Run tests from `~/coldchain/edge` as `.venv/bin/python -m tests.hw.<name>`.

| # | Part | Before powering on | Test | Expected |
|---|---|---|---|---|
| 0 | Pi alone | – | `ssh`, `.venv/bin/python -m pytest -q` | boots, all tests pass |
| 1 | Red + green LEDs | long leg to the 330 Ω resistor | `test_leds` | they alternate 5 times |
| 2 | Buzzer + NPN | check the transistor pin order (E/B/C) on its datasheet | `test_buzzer` | 3 beeps then a rising tone |
| 3 | Reed switch | – | `test_reed` | DOOR CLOSED with the magnet near, DOOR OPEN when away |
| 4 | DS18B20 + 4.7 kΩ | overlay line in config.txt, reboot | `test_ds18b20` | ~room temperature, rises when held, never 85.0 |
| 5 | DHT22 (+10 kΩ if bare sensor) | overlay line, reboot | `test_dht22` | sensible °C and %RH, at most a few read errors |
| 6 | 12 V sense divider | **measure the divider output with a multimeter first: about 2.55 V, must be < 3.3 V**; join the 12 V GND to the Pi GND; fuse in the 12 V line | `test_mains` | POWER PRESENT / POWER LOST as you plug and unplug |
| 7 | LCD + level shifter | check the backpack pull-ups (`docs/wiring.md`); `i2cdetect -y 1` shows 27 | `test_lcd` (or `test_lcd 3f`) | text and a counter; adjust contrast if blank |
| 8 | Keypad | – | `test_keypad` | all 16 keys print the right character |
| 9 | Lock + MOSFET (last) | diode across the solenoid, own 5 V 2 A adapter, common GND | `test_lock` | one click; current about 1 A (VERIFY with a meter) |
| 9b | PINs | `KEYPAD_INSTALLED=1`, `LOCK_INSTALLED=1` in `.env` | `.venv/bin/python -m coldchain.pins add <name>` for each person, then `python -m coldchain.pins time` | one check takes well under 100 ms (VERIFY); `1234#` on the keypad clicks the lock |
| 10 | Everything, node in the foreground | `MOCK_HARDWARE=0` in `.env` | `.venv/bin/python -m coldchain.node --no-mqtt` | LCD shows `IN  xx.xC  OK`, green LED on; warm the probe above 8 °C → after the confirm delay red LED + buzzer |
| 11 | With MQTT | broker running, `.env` filled in | `.venv/bin/python -m coldchain.node` | log says `MQTT connected`; the laptop's `mosquitto_sub` shows telemetry |
| 12 | systemd service | see section 6 | reboot the Pi | node starts by itself, `journalctl` shows it |

If a test fails, fix that part before adding the next one; tell Claude the exact output.

## 6. Install the service

```bash
cd ~/coldchain/edge
sed -e "s|__USER__|$USER|" -e "s|__EDGE_DIR__|$HOME/coldchain/edge|" systemd/coldchain-node.service \
  | sudo tee /etc/systemd/system/coldchain-node.service
sudo systemctl daemon-reload
sudo systemctl enable --now coldchain-node
journalctl -u coldchain-node -f                  # live log, one line per event
```

Day-to-day:

```bash
sudo systemctl stop coldchain-node               # needed before running a tests/hw script
sudo systemctl start coldchain-node
sudo systemctl status coldchain-node
cd ~/coldchain && git pull && sudo systemctl restart coldchain-node   # after a code change
```

**Crash safety check (do this once, with the lock wired):**

```bash
sudo systemctl kill -s KILL coldchain-node       # simulate a crash
pinctrl get 25                                   # expect: input, pull down ("ip pd")
journalctl -u coldchain-node -n 5                # the service restarts after 5 s
```

## 7. Files on the Pi

| File | Content |
|---|---|
| `edge/.env` | settings and MQTT password (not in git) |
| `edge/data/state.json` | out-of-range total, open excursion, excursion history, thresholds |
| `edge/data/outbox.db` | SQLite queue of events/telemetry not yet acknowledged by the broker |
| `edge/pins.json` | keypad PINs as salted hashes (not in git); keep a copy only on the Pi |

To start the out-of-range total from zero (for example before the demo):
`sudo systemctl stop coldchain-node && rm ~/coldchain/edge/data/state.json && sudo systemctl start coldchain-node`.
