"""Decides when to publish a telemetry message.

Send when:
- nothing has been sent yet, or the status changed (OK / WARNING / ALARM), or
- PERIOD_S (30 s) have passed, or
- the internal temperature moved more than DELTA_C (0.2 C), but never more often than MIN_GAP_S (5 s).
"""


class TelemetryPolicy:
    def __init__(self, period_s=30, delta_c=0.2, min_gap_s=5):
        self.period_s = period_s
        self.delta_c = delta_c
        self.min_gap_s = min_gap_s
        self.last_time = None
        self.last_temp = None
        self.last_status = None

    def should_send(self, now, temp, status):
        if self.last_time is None or status != self.last_status:
            return True
        elapsed = now - self.last_time
        if elapsed >= self.period_s:
            return True
        if elapsed < self.min_gap_s:
            return False
        if temp is None or self.last_temp is None:
            return temp != self.last_temp  # sensor failed or came back
        return abs(temp - self.last_temp) > self.delta_c

    def mark_sent(self, now, temp, status):
        self.last_time = now
        self.last_temp = temp
        self.last_status = status
