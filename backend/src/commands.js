// Commands to the node over MQTT: coldchain/{unitId}/cmd -> coldchain/{unitId}/cmd/result.
// Each command gets a random id and expires 30 s after it is sent (the node refuses it after
// that). The HTTP request waits for the node's answer, or gives up after `timeoutMs`.
import { randomUUID } from 'node:crypto';

export function createCommandBus({ publish, now = Date.now, expiryMs = 30000, timeoutMs = 10000 }) {
  const pending = new Map(); // command id -> {unitId, resolve, timer}

  return {
    // Resolves to the node's reply {id, ok, error}, or {ok: false, error: 'timeout'}
    send(unitId, action, params = {}) {
      const id = randomUUID();
      const cmd = { id, action, params, expiresAt: now() + expiryMs };
      return new Promise((resolve) => {
        const timer = setTimeout(() => {
          pending.delete(id);
          resolve({ id, ok: false, error: 'timeout' });
        }, timeoutMs);
        timer.unref?.();
        pending.set(id, { unitId, resolve, timer });
        publish(`coldchain/${unitId}/cmd`, JSON.stringify(cmd));
      });
    },

    // Called by the MQTT ingest for every cmd/result message
    onResult(unitId, result) {
      const entry = pending.get(result.id);
      if (!entry || entry.unitId !== unitId) return false; // unknown or too late: ignore
      clearTimeout(entry.timer);
      pending.delete(result.id);
      entry.resolve({ id: result.id, ok: result.ok, error: result.error ?? null });
      return true;
    },

    pendingCount() {
      return pending.size;
    },
  };
}
