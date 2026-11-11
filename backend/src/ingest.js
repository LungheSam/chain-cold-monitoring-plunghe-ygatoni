// MQTT ingest: everything the node publishes comes through handleMessage().
//
// - telemetry   -> live state (for the WoT property reads), unit document (at most every 15 s,
//                  at once on status/door/power changes), one reading per 60 s, summaries
// - event       -> stored once (duplicates dropped by event id), excursion and access records,
//                  summaries, SSE, SMS
// - status      -> online/offline (retained message + Last Will)
// - cmd/result  -> the waiting HTTP request
// A unit that has sent nothing for 2 minutes is OFFLINE (checkOffline(), called every 10 s), and
// gets an SMS.
//
// Messages are handled one at a time, in arrival order, so records are never updated out of order.
import {
  validateCmdResult, validateEvent, validateTelemetry,
} from './schemas.js';

export const UNIT_WRITE_EVERY_MS = 15000;
export const READING_EVERY_MS = 60000;
export const OFFLINE_AFTER_MS = 2 * 60 * 1000;
export const DELAYED_AFTER_MS = 5 * 60 * 1000;

const LIVE_FIELDS = ['internalTemp', 'ambientTemp', 'humidity', 'doorOpen', 'mainsPower', 'status', 'outOfRangeSeconds'];

export function createIngest({ config, store, summaries, sms, bus, hub, now = Date.now, log = console }) {
  const units = new Map();
  let chain = Promise.resolve(); // handles one message at a time

  function unitState(unitId) {
    if (!units.has(unitId)) {
      units.set(unitId, {
        unitId,
        online: false,
        lastSeen: null,
        offlineSince: null,
        offlineSmsSent: false,
        lastTelemetryTs: 0,
        lastReadingTs: 0,
        lastUnitWrite: 0,
        unitWriteTimer: null,
        live: { internalTemp: null, ambientTemp: null, humidity: null, doorOpen: false, mainsPower: true,
          status: 'OK', outOfRangeSeconds: 0, activeAlarms: [] },
        thresholds: { ...config.defaultThresholds },
        doorIntervals: [],   // [openedMs, closedMs] of recent openings (for the cause guess)
        powerIntervals: [],  // [lostMs, restoredMs]
        powerLostAt: null,
      });
    }
    return units.get(unitId);
  }

  // ---------------------------------------------------------------- unit document

  function effectiveStatus(u) {
    return u.online ? u.live.status : 'OFFLINE';
  }

  async function writeUnit(u) {
    clearTimeout(u.unitWriteTimer);
    u.unitWriteTimer = null;
    u.lastUnitWrite = now();
    await store.updateUnit(u.unitId, {
      ...u.live,
      status: effectiveStatus(u),
      online: u.online,
      lastSeen: u.lastSeen,
      lastTelemetryTs: u.lastTelemetryTs || null,
      thresholds: u.thresholds,
    });
  }

  // Write now if something important changed, else at most once per 15 s
  async function scheduleUnitWrite(u, important) {
    const elapsed = now() - u.lastUnitWrite;
    if (important || elapsed >= UNIT_WRITE_EVERY_MS) return writeUnit(u);
    if (!u.unitWriteTimer) {
      u.unitWriteTimer = setTimeout(() => {
        chain = chain.then(() => writeUnit(u)).catch((err) => log.error(`unit write failed: ${err.message}`));
      }, UNIT_WRITE_EVERY_MS - elapsed);
      u.unitWriteTimer.unref?.();
    }
  }

  // Returns true if the unit has just come (back) online
  async function markSeen(u) {
    u.lastSeen = now();
    if (u.online) return false;
    const offlineMs = u.offlineSince ? now() - u.offlineSince : null;
    u.online = true;
    u.offlineSince = null;
    if (u.offlineSmsSent) {
      u.offlineSmsSent = false;
      await sms.onUnitOnline(u.unitId, offlineMs);
    }
    log.info(`${u.unitId} online`);
    await writeUnit(u);
    return true;
  }

  async function markOffline(u, sinceMs) {
    if (!u.online && u.offlineSince) return;
    u.online = false;
    u.offlineSince = sinceMs;
    log.warn(`${u.unitId} offline (last seen ${u.lastSeen ? new Date(u.lastSeen).toISOString() : 'never'})`);
    await writeUnit(u);
  }

  // ---------------------------------------------------------------- handlers

  async function onTelemetry(u, t) {
    const cameOnline = await markSeen(u);
    // A clock that was not synced gives wrong times: use the time we received it instead
    const ts = t.timeSynced === false ? now() : t.ts;

    // Older messages (replayed from the node's offline queue) must not overwrite live state
    if (ts > u.lastTelemetryTs) {
      const before = u.live;
      u.lastTelemetryTs = ts;
      u.live = Object.fromEntries(LIVE_FIELDS.map((k) => [k, t[k] ?? null]));
      u.live.activeAlarms = t.activeAlarms || [];
      if (t.thresholds) u.thresholds = { ...u.thresholds, ...t.thresholds };
      const important = cameOnline || before.status !== u.live.status || before.doorOpen !== u.live.doorOpen
        || before.mainsPower !== u.live.mainsPower;
      await scheduleUnitWrite(u, important);
    }

    if (ts - u.lastReadingTs >= READING_EVERY_MS) {
      u.lastReadingTs = ts;
      await store.addReading(u.unitId, {
        ts,
        internalTemp: t.internalTemp,
        ambientTemp: t.ambientTemp ?? null,
        humidity: t.humidity ?? null,
        doorOpen: t.doorOpen,
        mainsPower: t.mainsPower,
        status: t.status,
      });
      await summaries.addReading(u.unitId, ts, t.internalTemp, u.thresholds.minC, u.thresholds.maxC);
    }
  }

  // Why did an excursion start? Power cut in the 30 min before, else door open in the 10 min before.
  function guessCause(u, startMs) {
    const overlaps = ([from, to], windowMs) => from <= startMs && (to ?? Infinity) >= startMs - windowMs;
    if (u.powerLostAt || u.powerIntervals.some((i) => overlaps(i, 30 * 60000))) return 'power';
    if (u.live.doorOpen || u.doorIntervals.some((i) => overlaps(i, 10 * 60000))) return 'door';
    return 'unknown';
  }

  async function onEvent(u, ev) {
    await markSeen(u);
    const receivedAt = now();
    const delayed = ev.timeSynced !== false && receivedAt - ev.ts > DELAYED_AFTER_MS;
    const isNew = await store.saveEventIfNew(u.unitId, { ...ev, receivedAt, delayed });
    if (!isNew) {
      log.info(`duplicate event ${ev.id} ignored`);
      return;
    }
    const d = ev.details;

    switch (ev.type) {
      case 'OUT_OF_RANGE_HIGH':
      case 'OUT_OF_RANGE_LOW':
        await store.upsertExcursion(u.unitId, d.excursionId, {
          direction: ev.type.endsWith('HIGH') ? 'HIGH' : 'LOW',
          start: d.since ?? ev.ts, end: null, confirmed: true,
          causeGuess: guessCause(u, d.since ?? ev.ts),
        });
        break;
      case 'BACK_IN_RANGE':
        await store.upsertExcursion(u.unitId, d.excursionId, {
          direction: d.direction, start: d.start, end: d.end, durationS: d.durationS,
          outOfRangeSeconds: d.outOfRangeSeconds, offlineGapS: d.offlineGapS ?? 0,
          offlineGapUnknown: !!d.offlineGapUnknown, minTemp: d.minTemp, maxTemp: d.maxTemp,
          confirmed: !!d.confirmed, causeGuess: guessCause(u, d.start),
        });
        break;
      case 'DOOR_CLOSED': {
        const openedAt = ev.ts - Math.round((d.openSeconds ?? 0) * 1000);
        u.doorIntervals = [...u.doorIntervals.slice(-49), [openedAt, ev.ts]];
        await summaries.addDoorOpening(u.unitId, openedAt, d.openSeconds ?? 0);
        break;
      }
      case 'POWER_LOST':
        u.powerLostAt = ev.ts;
        break;
      case 'POWER_RESTORED': {
        const lostAt = ev.ts - (d.durationS ?? 0) * 1000;
        u.powerIntervals = [...u.powerIntervals.slice(-49), [lostAt, ev.ts]];
        u.powerLostAt = null;
        await summaries.addPowerCut(u.unitId, lostAt, d.durationS ?? 0);
        break;
      }
      case 'ACCESS_GRANTED':
      case 'ACCESS_DENIED':
        await store.addAccess(u.unitId, ev.id, {
          ts: ev.ts, result: ev.type === 'ACCESS_GRANTED' ? 'GRANTED' : 'DENIED',
          method: d.method ?? 'unknown', user: d.user ?? null, details: d,
        });
        break;
      default:
        break;
    }

    hub.broadcast(u.unitId, publicEvent(ev));
    await sms.onEvent(u.unitId, ev, { delayed });
  }

  async function onStatus(u, text) {
    if (text === 'online') await markSeen(u);
    else if (text === 'offline') await markOffline(u, u.lastSeen ?? now());
  }

  async function handle(topic, payload) {
    // coldchain/{unitId}/{telemetry|event|status|cmd|cmd/result}
    const parts = topic.split('/');
    if (parts[0] !== 'coldchain' || parts.length < 3) return;
    const unitId = parts[1];
    const kind = parts.slice(2).join('/');
    if (!config.unitIds.includes(unitId)) return;
    if (kind === 'cmd') return; // our own commands
    const u = unitState(unitId);
    const text = payload.toString();

    if (kind === 'status') return onStatus(u, text.trim());

    let msg;
    try {
      msg = JSON.parse(text);
    } catch {
      log.warn(`not JSON on ${topic}`);
      return;
    }
    if (kind === 'telemetry') {
      if (!validateTelemetry(msg)) return log.warn(`bad telemetry from ${unitId}: ${JSON.stringify(validateTelemetry.errors)}`);
      return onTelemetry(u, msg);
    }
    if (kind === 'event') {
      if (!validateEvent(msg)) return log.warn(`bad event from ${unitId}: ${JSON.stringify(validateEvent.errors)}`);
      return onEvent(u, msg);
    }
    if (kind === 'cmd/result') {
      if (!validateCmdResult(msg)) return log.warn(`bad cmd/result from ${unitId}`);
      bus.onResult(unitId, msg);
    }
  }

  return {
    // Queue a message; resolves when it has been handled
    handleMessage(topic, payload) {
      chain = chain.then(() => handle(topic, payload)).catch((err) => log.error(`ingest ${topic}: ${err.stack || err}`));
      return chain;
    },

    // Called every 10 s: a unit silent for 2 min is offline, and gets one SMS
    async checkOffline() {
      for (const u of units.values()) {
        if (u.online && u.lastSeen && now() - u.lastSeen > OFFLINE_AFTER_MS) {
          await markOffline(u, u.lastSeen);
        }
        if (!u.online && u.offlineSince && !u.offlineSmsSent && now() - u.offlineSince >= OFFLINE_AFTER_MS) {
          u.offlineSmsSent = true;
          await sms.onUnitOffline(u.unitId, u.offlineSince);
        }
      }
    },

    // Restore thresholds and last values from the store after a restart
    async load(unitId) {
      const u = unitState(unitId);
      const doc = await store.getUnit(unitId);
      if (doc) {
        for (const k of LIVE_FIELDS) if (k in doc) u.live[k] = doc[k];
        if (doc.status === 'OFFLINE') u.live.status = 'OK';
        if (doc.thresholds) u.thresholds = { ...u.thresholds, ...doc.thresholds };
        u.lastTelemetryTs = doc.lastTelemetryTs || 0;
        u.lastSeen = doc.lastSeen || null;
      }
    },

    // ---- read access for the WoT routes
    isOnline: (unitId) => unitState(unitId).online,
    live: (unitId) => ({ ...unitState(unitId).live, status: effectiveStatus(unitState(unitId)) }),
    thresholds: (unitId) => ({ ...unitState(unitId).thresholds }),
    setThresholds(unitId, t) {
      const u = unitState(unitId);
      u.thresholds = { ...u.thresholds, ...t };
      return writeUnit(u);
    },
    lastSeen: (unitId) => unitState(unitId).lastSeen,
  };
}

// Events on the public SSE stream carry no personal data (docs/thing-description.md)
export function publicEvent(ev) {
  if (ev.type !== 'ACCESS_GRANTED' && ev.type !== 'ACCESS_DENIED') return ev;
  const { user, ...details } = ev.details || {}; // eslint-disable-line no-unused-vars
  return { ...ev, details };
}
