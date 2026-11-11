"""Text for the 16x2 LCD. Pure functions, so they can be tested without the LCD.

Line 1: internal temperature and status, e.g. "IN   5.2C     OK".
Line 2: rotates through ambient/humidity, door, power, out-of-range total and Wi-Fi/MQTT.
"""

WIDTH = 16
PAGES = ["ambient", "door", "power", "total", "network"]
STATUS_SHORT = {"OK": "OK", "WARNING": "WARN", "ALARM": "ALARM", "OFFLINE": "OFFL"}


def fit(text):
    """Cut or pad to exactly 16 characters."""
    return text[:WIDTH].ljust(WIDTH)


def format_duration(seconds):
    """Short duration: 45s, 12m30s, 3h05m, 120h."""
    seconds = int(seconds)
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm%02ds" % (seconds // 60, seconds % 60)
    if seconds < 100 * 3600:
        return "%dh%02dm" % (seconds // 3600, (seconds % 3600) // 60)
    return "%dh" % (seconds // 3600)


def line1(snap):
    temp = snap["internalTemp"]
    temp_text = "--.-" if temp is None else "%.1f" % temp
    status = STATUS_SHORT.get(snap["status"], snap["status"])
    left = "IN %6sC" % temp_text                        # 10 characters
    return fit(left + status.rjust(WIDTH - len(left)))


def line2(snap, page, wifi_ok, mqtt_ok):
    name = PAGES[page % len(PAGES)]
    if name == "ambient":
        amb, hum = snap["ambientTemp"], snap["humidity"]
        amb_text = "--.-" if amb is None else "%.1f" % amb
        hum_text = "--" if hum is None else "%.0f" % hum
        return fit("AMB %sC %s%%RH" % (amb_text, hum_text))
    if name == "door":
        if snap["doorOpen"]:
            return fit("DOOR OPEN " + format_duration(snap["doorOpenSeconds"]))
        return fit("DOOR CLOSED")
    if name == "power":
        return fit("POWER OK" if snap["mainsPower"] else "POWER LOST")
    if name == "total":
        return fit("OUT RNG " + format_duration(snap["outOfRangeSeconds"]))
    return fit("WIFI %s MQTT %s" % ("OK" if wifi_ok else "--", "OK" if mqtt_ok else "--"))
