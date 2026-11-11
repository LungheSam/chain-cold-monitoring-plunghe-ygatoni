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
    }
    settings.update(PROFILES[profile])
    return settings
