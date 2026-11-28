"""Settings for the edge node.

Two timing profiles: "real" for a real fridge and "demo" for a quick Open Day demo.
Everything else comes from environment variables (see edge/.env.example).
"""
import os

# Timing profiles (seconds)
PROFILES = {
    "real": {"TEMP_CONFIRM_S": 300, "DOOR_OPEN_LIMIT_S": 120, "POWER_CONFIRM_S": 5},
    "demo": {"TEMP_CONFIRM_S": 20, "DOOR_OPEN_LIMIT_S": 15, "POWER_CONFIRM_S": 3},
}

# Vaccine storage range (WHO: +2 to +8 C)
TEMP_MIN_C = 2.0
TEMP_MAX_C = 8.0
TEMP_HYSTERESIS_C = 0.3

# Telemetry
TELEMETRY_PERIOD_S = 30
TELEMETRY_DELTA_C = 0.2


def load_settings(env=None):
    """Return a plain dict of settings. `env` defaults to os.environ (handy for tests)."""
    if env is None:
        env = os.environ
    profile = env.get("PROFILE", "demo")
    if profile not in PROFILES:
        raise ValueError(f"PROFILE must be one of {list(PROFILES)}, got {profile!r}")

    lock_type = env.get("LOCK_TYPE", "relay")
    if lock_type not in ("relay", "servo"):
        raise ValueError(f"LOCK_TYPE must be relay or servo, got {lock_type!r}")
    settings = {
        "UNIT_ID": env.get("UNIT_ID", "cold-unit-01"),
        "PROFILE": profile,
        "MOCK_HARDWARE": env.get("MOCK_HARDWARE", "1") == "1",
        "TEMP_MIN_C": TEMP_MIN_C,
        "TEMP_MAX_C": TEMP_MAX_C,
        "TEMP_HYSTERESIS_C": TEMP_HYSTERESIS_C,
        "TELEMETRY_PERIOD_S": TELEMETRY_PERIOD_S,
        "TELEMETRY_DELTA_C": TELEMETRY_DELTA_C,
        "DATA_DIR": env.get("DATA_DIR", "./data"),
        # Extension (Phase 5): keypad and solenoid lock. Off unless fitted.
        "KEYPAD_INSTALLED": env.get("KEYPAD_INSTALLED", "0") == "1",
        "LOCK_INSTALLED": env.get("LOCK_INSTALLED", "0") == "1",
        # Cabinet locks like ours only need a short pulse to release the latch
        # (label: "power-on time 500 ms"). The coil is never powered longer than this.
        "LOCK_PULSE_S": float(env.get("LOCK_PULSE_S", "0.5")),
        # 1 for relay modules that switch on with a LOW input. Prefer a module (or jumper) that
        # switches on with HIGH: an active-LOW module can click on while the Pi boots.
        "LOCK_ACTIVE_LOW": env.get("LOCK_ACTIVE_LOW", "0") == "1",
        # What opens the door: "relay" (relay module + solenoid cabinet lock) or "servo" (a hobby
        # servo turns a latch; used for the demo because the 12 V lock did not arrive in time).
        "LOCK_TYPE": lock_type,
        # Servo: the two latch positions, and the pulse widths for 0 and 180 degrees.
        # 0.5-2.4 ms is typical for SG90-class micro servos: VERIFY on yours with tests/hw/test_lock.py
        "SERVO_LOCKED_DEG": float(env.get("SERVO_LOCKED_DEG", "0")),
        "SERVO_UNLOCKED_DEG": float(env.get("SERVO_UNLOCKED_DEG", "90")),
        "SERVO_MIN_PULSE_MS": float(env.get("SERVO_MIN_PULSE_MS", "0.5")),
        "SERVO_MAX_PULSE_MS": float(env.get("SERVO_MAX_PULSE_MS", "2.4")),
        # 1 if the reed switch reads the wrong way round (contact OPEN when the magnet is near).
        "REED_INVERTED": env.get("REED_INVERTED", "0") == "1",
        "PINS_FILE": env.get("PINS_FILE", "./pins.json"),
    }
    settings.update(PROFILES[profile])
    return settings
