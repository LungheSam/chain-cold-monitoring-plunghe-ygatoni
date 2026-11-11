"""Offline queue (outbox) for events and telemetry, in a small SQLite file.

Every event and telemetry message goes into the outbox first. pump() sends them in order whenever
MQTT is connected, and a row is deleted only when the broker has acknowledged it (PUBACK, QoS 1).
So nothing is lost if Wi-Fi drops, the broker restarts or the Pi reboots. A message may be sent
twice after a reconnect; the back end drops duplicates by event id.

- Events are never dropped.
- Telemetry is thinned while offline: at most one per TELEMETRY_OFFLINE_EVERY_S (60 s), and at most
  MAX_TELEMETRY rows (a week at one per minute). Enough for the history chart.

Clock (docs/decisions.md D6): a message made before NTP synced has a wrong wall-clock time. Each row
stores time.monotonic() and the boot id. When the clock syncs, the timestamps of such rows from the
current boot are corrected before sending: ts = now_wall - (now_mono - row_mono). Messages are held
(not sent) until then, but at most HOLD_UNSYNCED_S after connecting, so a broker on a LAN without
Internet still gets the data (marked timeSynced: false).
"""
import json
import logging
import os
import sqlite3

log = logging.getLogger(__name__)

TELEMETRY_OFFLINE_EVERY_S = 60
MAX_TELEMETRY = 10_080
MAX_IN_FLIGHT = 20
HOLD_UNSYNCED_S = 300
TIME_KEYS_IN_DETAILS = ("start", "end", "since")   # wall-clock times inside event details


class Outbox:
    def __init__(self, path, clock, boot_id):
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,        -- 'event' or 'telemetry'
            payload TEXT NOT NULL,     -- JSON
            mono REAL NOT NULL,        -- time.monotonic() when created
            boot_id TEXT NOT NULL,
            synced INTEGER NOT NULL    -- was the wall clock NTP-synced when created?
        )""")
        self.db.commit()
        self.clock = clock
        self.boot_id = boot_id

        self.in_flight = {}            # MQTT message id -> row id
        self.last_sent_id = 0          # rows are sent in id order
        self.epoch = None              # connection number seen last time
        self.connected_at = None
        self.last_offline_telemetry = None

    # ---------------------------------------------------------------- adding

    def add(self, kind, payload, connected=True):
        """Store a message. Returns False if a telemetry message was thinned out."""
        now = self.clock.monotonic()
        if kind == "telemetry" and not connected:
            if (self.last_offline_telemetry is not None
                    and now - self.last_offline_telemetry < TELEMETRY_OFFLINE_EVERY_S):
                return False
            self.last_offline_telemetry = now
        self.db.execute(
            "INSERT INTO outbox (kind, payload, mono, boot_id, synced) VALUES (?, ?, ?, ?, ?)",
            (kind, json.dumps(payload), now, self.boot_id, 1 if payload.get("timeSynced", True) else 0),
        )
        if kind == "telemetry":
            # Keep only the newest MAX_TELEMETRY telemetry rows
            self.db.execute("""DELETE FROM outbox WHERE kind = 'telemetry' AND id NOT IN (
                SELECT id FROM outbox WHERE kind = 'telemetry' ORDER BY id DESC LIMIT ?)""", (MAX_TELEMETRY,))
        self.db.commit()
        return True

    def count(self, kind=None):
        if kind:
            return self.db.execute("SELECT COUNT(*) FROM outbox WHERE kind = ?", (kind,)).fetchone()[0]
        return self.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]

    # ---------------------------------------------------------------- sending

    def pump(self, link):
        """Delete acknowledged rows and send the next ones. Call every loop pass."""
        if link.epoch != self.epoch:
            # New connection: anything in flight before was not acknowledged, so send it again
            self.epoch = link.epoch
            self.in_flight = {}
            self.last_sent_id = 0
            self.connected_at = self.clock.monotonic()

        acked = [self.in_flight.pop(mid) for mid in link.take_acked() if mid in self.in_flight]
        if acked:
            self.db.executemany("DELETE FROM outbox WHERE id = ?", [(row_id,) for row_id in acked])
            self.db.commit()

        if not link.connected:
            return
        room = MAX_IN_FLIGHT - len(self.in_flight)
        if room <= 0:
            return
        rows = self.db.execute(
            "SELECT id, kind, payload, mono, boot_id, synced FROM outbox WHERE id > ? ORDER BY id LIMIT ?",
            (self.last_sent_id, room)).fetchall()
        for row_id, kind, payload_text, mono, boot_id, synced in rows:
            payload = json.loads(payload_text)
            if not synced:
                if not self._fix_time(payload, mono, boot_id):
                    break      # hold this and everything after it (keeps the order)
            mid = link.send(kind, json.dumps(payload))
            if mid is None:
                break
            self.in_flight[mid] = row_id
            self.last_sent_id = row_id

    def _fix_time(self, payload, mono, boot_id):
        """Correct the timestamps of a message made before NTP synced. False = hold it for now."""
        if self.clock.synced() and boot_id == self.boot_id:
            corrected = int((self.clock.time() - (self.clock.monotonic() - mono)) * 1000)
            shift = corrected - payload["ts"]
            payload["ts"] = corrected
            details = payload.get("details") or {}
            for key in TIME_KEYS_IN_DETAILS:
                if isinstance(details.get(key), int):
                    details[key] += shift
            payload["timeSynced"] = True
            return True
        if boot_id != self.boot_id:
            return True        # from an earlier boot: cannot be corrected, send as it is
        if self.clock.monotonic() - self.connected_at >= HOLD_UNSYNCED_S:
            return True        # clock never synced: send it anyway, marked timeSynced: false
        return False

    def close(self):
        self.db.close()
