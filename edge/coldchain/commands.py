"""Handles commands from the back end: {id, action, params, expiresAt}.

- A command whose id was already seen is ignored (QoS 1 can deliver twice). No reply is sent.
- An expired command is refused (expiresAt is Unix time in milliseconds).
- Every other command gets a reply {id, ok, error} for coldchain/{unitId}/cmd/result.
"""
import collections
import logging

log = logging.getLogger(__name__)

REMEMBER_IDS = 100


class CommandHandler:
    def __init__(self, engine, clock, unlock_fn=None):
        self.engine = engine
        self.clock = clock
        self.unlock_fn = unlock_fn  # set in Phase 5 (lock driver)
        self.seen_ids = collections.deque(maxlen=REMEMBER_IDS)

    def handle(self, cmd):
        """Returns (result or None, list of events)."""
        if not isinstance(cmd, dict) or not cmd.get("id"):
            return {"id": None, "ok": False, "error": "missing id"}, []
        cmd_id = cmd["id"]
        if cmd_id in self.seen_ids:
            log.info("Ignoring repeated command %s", cmd_id)
            return None, []
        self.seen_ids.append(cmd_id)

        expires_at = cmd.get("expiresAt")
        # Without a synced clock we cannot judge expiry; the id check still stops repeats.
        if expires_at is not None and self.clock.synced() and self.clock.time() * 1000 > expires_at:
            return self._reply(cmd_id, False, "expired"), []

        action = cmd.get("action")
        params = cmd.get("params") or {}

        if action == "acknowledgeAlarm":
            event = self.engine.acknowledge(by=str(params.get("by", "dashboard")))
            if event is None:
                return self._reply(cmd_id, False, "no active alarm"), []
            return self._reply(cmd_id, True), [event]

        if action == "setThresholds":
            allowed = {k: params[k] for k in ("minC", "maxC", "confirmDelayS", "doorLimitS") if k in params}
            try:
                self.engine.set_thresholds(**allowed)
            except (ValueError, TypeError) as e:
                return self._reply(cmd_id, False, str(e)), []
            return self._reply(cmd_id, True), []

        if action == "unlockDoor":
            if self.unlock_fn is None:
                return self._reply(cmd_id, False, "lock not installed"), []
            ok, error, events = self.unlock_fn(params)
            return self._reply(cmd_id, ok, error), events

        return self._reply(cmd_id, False, "unknown action %r" % action), []

    @staticmethod
    def _reply(cmd_id, ok, error=None):
        return {"id": cmd_id, "ok": ok, "error": error}
