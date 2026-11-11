"""Alarm logic for the cold chain node.

Pure Python: no GPIO, no MQTT, no files. The node calls update() with each new sensor reading, and
gets back a list of events to publish. Time comes from an injected clock (see clock.py), so the
unit tests can run hours of fridge time in milliseconds.

Rules (see docs/decisions.md D7, D9, D17):
- Temperature: out of range above max (8.0) or below min (2.0). The alarm fires when an excursion
  has lasted TEMP_CONFIRM_S and the temperature is still out of range. It clears with 0.3 C
  hysteresis (back within 2.3 to 7.7 C).
- The cumulative out-of-range timer counts raw seconds outside min..max, from the first bad
  reading, confirmed or not.
- Door: debounced 50 ms; alarm when open longer than DOOR_OPEN_LIMIT_S.
- Power: POWER_LOST after the sense line is LOW for POWER_CONFIRM_S, restored after HIGH as long.
- Internal probe failure (missing / 85.0 C / -127 C, 3 times in a row) is an alarm: we are blind.
  Ambient sensor failure (5 times in a row) is only a warning.
"""
import copy
import uuid
from dataclasses import dataclass
from typing import Optional

DOOR_DEBOUNCE_S = 0.05
DS18B20_BAD_VALUES = (85.0, -127.0)  # 85.0 = power-on reset value, -127 = "no sensor"
INTERNAL_FAIL_LIMIT = 3
AMBIENT_FAIL_LIMIT = 5
MAX_EXCURSION_HISTORY = 200  # closed excursions kept in the state file


@dataclass
class Reading:
    """One set of raw sensor values. None means the read failed.

    The main loop runs every 0.1 s but the DS18B20 gives a new sample about once a second and the
    DHT22 every few seconds. internal_new / ambient_new say whether this reading carries a *new*
    sample, so that "3 bad reads in a row" counts samples, not loop passes.
    """
    internal_temp: Optional[float]
    ambient_temp: Optional[float]
    humidity: Optional[float]
    door_open: bool
    mains_present: bool
    internal_new: bool = True
    ambient_new: bool = True


class Debouncer:
    """Reports a new value only after the raw input has stayed at it for hold_s seconds."""

    def __init__(self, hold_s, initial):
        self.hold_s = hold_s
        self.value = initial
        self._candidate = initial
        self._since = None      # when the raw input started to differ from value
        self.changed_at = None  # when the last confirmed change was first seen

    def update(self, raw, now):
        if raw == self.value:
            self._since = None  # a glitch that went away
        else:
            if self._since is None or raw != self._candidate:
                self._candidate = raw
                self._since = now
            if now - self._since >= self.hold_s:
                self.value = raw
                self.changed_at = self._since
                self._since = None
        return self.value

    @property
    def pending(self):
        """True while the raw input differs but is not yet confirmed."""
        return self._since is not None


class AlarmEngine:
    def __init__(self, settings, clock):
        self.clock = clock
        self.min_c = settings["TEMP_MIN_C"]
        self.max_c = settings["TEMP_MAX_C"]
        self.hyst_c = settings["TEMP_HYSTERESIS_C"]
        self.confirm_s = settings["TEMP_CONFIRM_S"]
        self.door_limit_s = settings["DOOR_OPEN_LIMIT_S"]

        now = clock.monotonic()
        self.start_mono = now        # when this program started (used for the reboot gap)
        self.last_update = None

        # Latest good values
        self.internal_temp = None
        self.ambient_temp = None
        self.humidity = None

        # Sensor health
        self.internal_fail_count = 0
        self.internal_fault = False
        self.ambient_fail_count = 0
        self.ambient_fault = False

        # Temperature and excursions
        self.total_oor_s = 0.0
        self.excursion = None        # the open excursion (dict) or None
        self.excursions = []         # closed excursions, oldest first
        self.temp_alarm = None       # None, "HIGH" or "LOW"

        # Door
        self.door = Debouncer(DOOR_DEBOUNCE_S, False)
        self.door_opened_at = None
        self.door_alarm = False

        # Power (the debouncer *is* the confirmation delay)
        self.power = Debouncer(settings["POWER_CONFIRM_S"], True)
        self.power_lost_at = None
        self.power_alarm = False

        # Alarms silenced by acknowledgeAlarm
        self.acknowledged = set()

        # Reboot in the middle of an excursion (see load_state)
        self.restored_saved_at = None   # wall time (s) of the last save before the restart
        self.gap_check_pending = False  # waiting for the first reading after the restart
        self.gap_pending = False        # still out of range after restart: add the gap once synced

        self.dirty = False              # something important changed: save the state file now

    # ------------------------------------------------------------------ main entry point

    def update(self, reading):
        """Feed one reading. Returns the list of events that happened."""
        now = self.clock.monotonic()
        events = []

        # 1. Count out-of-range time since the previous reading (using the previous temperature).
        if self.last_update is not None and self.excursion and self._is_out(self.internal_temp):
            dt = now - self.last_update
            self.total_oor_s += dt
            self.excursion["outOfRangeSeconds"] += dt
        self.last_update = now

        # 2. Sensors (only when they have produced a new sample)
        if reading.internal_new:
            self._check_internal(reading.internal_temp, now, events)
        if reading.ambient_new:
            self._check_ambient(reading.ambient_temp, reading.humidity, events)

        # 3. Door and power
        self._check_door(reading.door_open, now, events)
        self._check_power(reading.mains_present, now, events)

        # 4. Time the Pi was off during an excursion, once the clock can be trusted
        if self.gap_pending and self.clock.synced():
            self._apply_offline_gap(now)

        # Forget acknowledgements of alarms that have cleared, so a repeat sounds again
        self.acknowledged &= self.active_alarms()
        if events:
            self.dirty = True
        return events

    # ------------------------------------------------------------------ sensors

    def _check_internal(self, temp, now, events):
        if temp is None or temp in DS18B20_BAD_VALUES:
            self.internal_fail_count += 1
            if self.internal_fail_count >= INTERNAL_FAIL_LIMIT and not self.internal_fault:
                self.internal_fault = True
                self.internal_temp = None
                if temp is None:
                    reason = "read_error"
                else:
                    reason = "%gC" % temp
                events.append(self._event("SENSOR_FAULT", {"sensor": "ds18b20", "reason": reason}))
            return

        self.internal_fail_count = 0
        if self.internal_fault:
            self.internal_fault = False
            events.append(self._event("SENSOR_RESTORED", {"sensor": "ds18b20"}))
        self.internal_temp = temp
        self._check_temperature(temp, now, events)

    def _check_ambient(self, temp, humidity, events):
        if temp is None or humidity is None:
            self.ambient_fail_count += 1
            if self.ambient_fail_count >= AMBIENT_FAIL_LIMIT and not self.ambient_fault:
                self.ambient_fault = True
                self.ambient_temp = None
                self.humidity = None
                events.append(self._event("SENSOR_FAULT", {"sensor": "dht22", "reason": "read_error"}))
            return  # keep the last good value until the fault is declared

        self.ambient_fail_count = 0
        if self.ambient_fault:
            self.ambient_fault = False
            events.append(self._event("SENSOR_RESTORED", {"sensor": "dht22"}))
        self.ambient_temp = temp
        self.humidity = humidity

    # ------------------------------------------------------------------ temperature

    def _is_out(self, temp):
        return temp is not None and (temp > self.max_c or temp < self.min_c)

    def _direction(self, temp):
        if temp > self.max_c:
            return "HIGH"
        if temp < self.min_c:
            return "LOW"
        return None

    def _check_temperature(self, temp, now, events):
        direction = self._direction(temp)

        # First reading after a restart in the middle of an excursion
        if self.gap_check_pending:
            self.gap_check_pending = False
            if self.excursion and direction == self.excursion["direction"]:
                self.gap_pending = True

        # Jumped straight from too hot to too cold (or back): close the old excursion first
        if self.excursion and direction and direction != self.excursion["direction"]:
            self._close_excursion(now, events)

        if direction and self.excursion is None:
            self._open_excursion(direction, temp, now)

        exc = self.excursion
        if exc is None:
            return
        exc["minTemp"] = min(exc["minTemp"], temp)
        exc["maxTemp"] = max(exc["maxTemp"], temp)

        if not exc["confirmed"]:
            if direction and now - exc["startMono"] >= self.confirm_s:
                exc["confirmed"] = True
                self.temp_alarm = exc["direction"]
                limit = self.max_c if exc["direction"] == "HIGH" else self.min_c
                events.append(self._event("OUT_OF_RANGE_" + exc["direction"], {
                    "temp": round(temp, 2),
                    "limit": limit,
                    "since": exc["start"],
                    "excursionId": exc["id"],
                    "outOfRangeSeconds": int(round(self.total_oor_s)),
                }))
                return

        # Back in range, with hysteresis
        if self.min_c + self.hyst_c <= temp <= self.max_c - self.hyst_c:
            self._close_excursion(now, events)

    def _open_excursion(self, direction, temp, now):
        self.excursion = {
            "id": str(uuid.uuid4()),
            "direction": direction,
            "start": self._wall_ms(),
            "startMono": now,
            "end": None,
            "durationS": 0,
            "outOfRangeSeconds": 0.0,
            "offlineGapS": 0,
            "offlineGapUnknown": False,
            "minTemp": temp,
            "maxTemp": temp,
            "confirmed": False,
        }
        self.dirty = True

    def _close_excursion(self, now, events):
        exc = self.excursion
        if self.gap_pending:  # closed before the clock synced: we cannot know the gap
            self.gap_pending = False
            exc["offlineGapUnknown"] = True
        exc["end"] = self._wall_ms()
        exc["durationS"] = int(round(now - exc["startMono"] + exc["offlineGapS"]))
        exc["outOfRangeSeconds"] = int(round(exc["outOfRangeSeconds"]))
        record = self._excursion_record(exc)
        self.excursions.append(record)
        del self.excursions[:-MAX_EXCURSION_HISTORY]

        # BACK_IN_RANGE is also sent for short unconfirmed blips (confirmed: false), so the back
        # end gets a record of every excursion. It only sends an SMS for confirmed ones.
        events.append(self._event("BACK_IN_RANGE", dict(record, excursionId=record["id"])))
        if exc["confirmed"]:
            self.temp_alarm = None
        self.excursion = None
        self.dirty = True

    def _excursion_record(self, exc):
        record = {k: v for k, v in exc.items() if k != "startMono"}
        record["minTemp"] = round(record["minTemp"], 2)
        record["maxTemp"] = round(record["maxTemp"], 2)
        return record

    # ------------------------------------------------------------------ door and power

    def _check_door(self, raw_open, now, events):
        was_open = self.door.value
        is_open = self.door.update(raw_open, now)

        if is_open and not was_open:
            self.door_opened_at = self.door.changed_at   # first moment seen open
        elif was_open and not is_open:
            # Sent for every opening, so the dashboard can count openings and their length
            events.append(self._event("DOOR_CLOSED", {
                "openSeconds": round(self.door.changed_at - self.door_opened_at, 1),
                "alarmed": self.door_alarm,
            }))
            self.door_alarm = False
            self.door_opened_at = None

        if is_open and not self.door_alarm and now - self.door_opened_at >= self.door_limit_s:
            self.door_alarm = True
            events.append(self._event("DOOR_OPEN_TOO_LONG", {
                "openSeconds": round(now - self.door_opened_at, 1),
                "limitS": self.door_limit_s,
            }))

    def _check_power(self, raw_present, now, events):
        was_present = self.power.value
        present = self.power.update(raw_present, now)

        # The event is sent after POWER_CONFIRM_S, but the duration is measured from the moments
        # the sense line first went LOW and first came back HIGH.
        if was_present and not present:
            self.power_alarm = True
            self.power_lost_at = self.power.changed_at
            events.append(self._event("POWER_LOST", {}))
        elif present and not was_present:
            self.power_alarm = False
            duration = self.power.changed_at - self.power_lost_at if self.power_lost_at is not None else 0
            events.append(self._event("POWER_RESTORED", {"durationS": int(round(duration))}))
            self.power_lost_at = None

    # ------------------------------------------------------------------ restart gap

    def _apply_offline_gap(self, now):
        """Add the time the Pi was off, now that the wall clock is trusted (D6)."""
        self.gap_pending = False
        if self.excursion is None or self.restored_saved_at is None:
            return
        program_started_at = self.clock.time() - (now - self.start_mono)
        gap = max(0, int(round(program_started_at - self.restored_saved_at)))
        self.excursion["offlineGapS"] += gap
        self.total_oor_s += gap
        self.dirty = True

    # ------------------------------------------------------------------ alarms and outputs

    def active_alarms(self):
        alarms = set()
        if self.temp_alarm:
            alarms.add("TEMP_" + self.temp_alarm)
        if self.door_alarm:
            alarms.add("DOOR_OPEN")
        if self.power_alarm:
            alarms.add("POWER_LOST")
        if self.internal_fault:
            alarms.add("SENSOR_INTERNAL")
        return alarms

    def status(self):
        if self.active_alarms():
            return "ALARM"
        if (self.excursion is not None or self.door.value or self.power.pending
                or self.ambient_fault or self.internal_fail_count > 0):
            return "WARNING"
        return "OK"

    def acknowledge(self, by="unknown"):
        """Silence the buzzer for the current alarms. Returns an event, or None if no alarm."""
        active = self.active_alarms()
        if not active:
            return None
        self.acknowledged = set(active)
        self.dirty = True
        return self._event("ALARM_ACKNOWLEDGED", {"by": by, "alarms": sorted(active)})

    def outputs(self):
        """What the LEDs and buzzer should do. The driver turns 'blink' into blinking."""
        alarms = self.active_alarms()
        return {
            "red": "blink" if alarms else "off",
            "green": "on" if self.status() == "OK" else "off",
            "buzzer": bool(alarms - self.acknowledged),
        }

    # ------------------------------------------------------------------ thresholds

    def thresholds(self):
        return {
            "minC": self.min_c,
            "maxC": self.max_c,
            "confirmDelayS": self.confirm_s,
            "doorLimitS": self.door_limit_s,
        }

    def set_thresholds(self, minC=None, maxC=None, confirmDelayS=None, doorLimitS=None):
        """Change limits. Raises ValueError if the new values do not make sense."""
        new_min = self.min_c if minC is None else float(minC)
        new_max = self.max_c if maxC is None else float(maxC)
        new_confirm = self.confirm_s if confirmDelayS is None else int(confirmDelayS)
        new_door = self.door_limit_s if doorLimitS is None else int(doorLimitS)

        if not -30 <= new_min < new_max <= 30:
            raise ValueError("need -30 <= minC < maxC <= 30")
        if new_max - new_min <= 2 * self.hyst_c:
            raise ValueError("minC and maxC are too close together")
        if not 0 <= new_confirm <= 3600:
            raise ValueError("confirmDelayS must be 0..3600")
        if not 1 <= new_door <= 3600:
            raise ValueError("doorLimitS must be 1..3600")

        self.min_c, self.max_c = new_min, new_max
        self.confirm_s, self.door_limit_s = new_confirm, new_door
        self.dirty = True
        return self.thresholds()

    # ------------------------------------------------------------------ telemetry and LCD

    def snapshot(self):
        now = self.clock.monotonic()
        door_open_s = 0
        if self.door.value and self.door_opened_at is not None:
            door_open_s = int(now - self.door_opened_at)
        return {
            "internalTemp": None if self.internal_temp is None else round(self.internal_temp, 2),
            "ambientTemp": None if self.ambient_temp is None else round(self.ambient_temp, 1),
            "humidity": None if self.humidity is None else round(self.humidity, 1),
            "doorOpen": self.door.value,
            "doorOpenSeconds": door_open_s,
            "mainsPower": self.power.value,
            "status": self.status(),
            "outOfRangeSeconds": int(round(self.total_oor_s)),
            "activeAlarms": sorted(self.active_alarms()),
        }

    # ------------------------------------------------------------------ save / restore

    def to_state(self):
        """Everything that must survive a reboot, as plain JSON-able data."""
        open_exc = None
        if self.excursion:
            open_exc = self._excursion_record(self.excursion)
            open_exc["outOfRangeSeconds"] = self.excursion["outOfRangeSeconds"]
            open_exc["ageS"] = self.clock.monotonic() - self.excursion["startMono"]
        return {
            "version": 1,
            "savedAt": self.clock.time(),
            "savedAtSynced": self.clock.synced(),
            "outOfRangeSeconds": self.total_oor_s,
            "tempAlarm": self.temp_alarm,
            "openExcursion": open_exc,
            "excursions": self.excursions,
            "thresholds": self.thresholds(),
        }

    def load_state(self, state):
        """Restore after a restart. Call before the first update()."""
        if not state or state.get("version") != 1:
            return
        self.total_oor_s = float(state.get("outOfRangeSeconds", 0))
        self.excursions = list(state.get("excursions", []))
        t = state.get("thresholds") or {}
        try:
            self.set_thresholds(t.get("minC"), t.get("maxC"), t.get("confirmDelayS"), t.get("doorLimitS"))
        except ValueError:
            pass  # keep the defaults if the saved thresholds are bad

        exc = state.get("openExcursion")
        if exc:
            exc = dict(exc)
            exc["startMono"] = self.clock.monotonic() - exc.pop("ageS", 0)
            self.excursion = exc
            self.temp_alarm = state.get("tempAlarm") if exc.get("confirmed") else None
            self.gap_check_pending = True
            self.restored_saved_at = state.get("savedAt") if state.get("savedAtSynced") else None
            if self.restored_saved_at is None:
                exc["offlineGapUnknown"] = True
        self.dirty = False

    # ------------------------------------------------------------------ helpers

    def _wall_ms(self):
        return int(self.clock.time() * 1000)

    def _event(self, event_type, details):
        return {
            "id": str(uuid.uuid4()),
            "ts": self._wall_ms(),
            "type": event_type,
            "details": copy.deepcopy(details),
            "timeSynced": self.clock.synced(),
        }
