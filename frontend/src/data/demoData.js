// Offline demo data source (npm run demo): no Firebase, no back end.
// Uses a week of data made by `npm run seed -- --dump` in backend/ (demo-data.json), moved in time so
// that it ends "now". The live unit is simulated: the temperature drifts every 5 s, and the
// "Simulate alarm" button in the demo banner pushes it out of range so the alarm flow can be shown.
import raw from '../demo/demo-data.json';

const TIME_KEYS = ['ts', 'start', 'end', 'since', 'lastSeen', 'lastTelemetryTs'];

// Move every known time field by `shift` ms (also inside event details)
function shifted(obj, shift) {
  const out = { ...obj };
  for (const k of TIME_KEYS) if (typeof out[k] === 'number') out[k] += shift;
  if (out.details) out.details = shifted(out.details, shift);
  return out;
}

export function createDemoData() {
  const shift = Date.now() - raw.generatedAt;
  const readings = raw.readings.map((r) => shifted(r, shift));
  const summaries = { hourly: raw.hourly.map((s) => shifted(s, shift)), daily: raw.daily.map((s) => shifted(s, shift)) };
  const events = raw.events.map((e) => shifted(e, shift)).sort((a, b) => a.ts - b.ts);
  const excursions = raw.excursions.map((e) => shifted(e, shift));
  const access = raw.access.map((a) => shifted(a, shift));
  let unit = shifted(raw.unit, shift);
  let contacts = [
    { id: 'demo-1', name: 'Samuel (demo)', phone: '+250788000001', units: [raw.unitId], active: true },
    { id: 'demo-2', name: 'Yves (demo)', phone: '+250788000002', units: [raw.unitId], active: true },
  ];

  const listeners = { unit: new Set(), events: new Set(), excursions: new Set(), access: new Set() };
  const notify = (name, value) => listeners[name].forEach((cb) => cb(value));
  const newestFirst = (list) => [...list].sort((a, b) => (b.ts ?? b.start) - (a.ts ?? a.start));
  let counter = 0;
  const addEvent = (type, details) => {
    counter += 1;
    events.push({ id: `demo-live-${counter}`, ts: Date.now(), type, details });
    notify('events', newestFirst(events));
  };

  // Simulated live unit: small drift every 5 s; "heat" pushes it above 8 C
  let target = 4.8;
  let excursion = null;
  setInterval(() => {
    const t = unit.internalTemp + (target - unit.internalTemp) * 0.15 + (Math.random() - 0.5) * 0.08;
    const now = Date.now();
    unit = { ...unit, internalTemp: Number(t.toFixed(2)), lastTelemetryTs: now, lastSeen: now };
    if (t > 8 && !excursion) {
      excursion = { id: `demo-exc-${now}`, direction: 'HIGH', start: now, end: null, minTemp: t, maxTemp: t, confirmed: false, causeGuess: 'unknown' };
      unit.status = 'WARNING';
    }
    if (excursion) {
      excursion.maxTemp = Math.max(excursion.maxTemp, t);
      unit.outOfRangeSeconds += t > 8 ? 5 : 0;
      if (!excursion.confirmed && t > 8 && now - excursion.start >= 20000) {
        excursion.confirmed = true;
        unit.status = 'ALARM';
        unit.activeAlarms = ['TEMP_HIGH'];
        excursions.unshift(excursion);
        notify('excursions', newestFirst(excursions));
        addEvent('OUT_OF_RANGE_HIGH', { temp: t.toFixed(2), limit: 8, since: excursion.start });
      } else if (t <= 7.7) {
        Object.assign(excursion, { end: now, durationS: Math.round((now - excursion.start) / 1000) });
        if (excursion.confirmed) {
          addEvent('BACK_IN_RANGE', { ...excursion, excursionId: excursion.id });
          notify('excursions', newestFirst(excursions));
        }
        excursion = null;
        unit.status = 'OK';
        unit.activeAlarms = [];
      }
    }
    notify('unit', unit);
  }, 5000);

  const subscribe = (name, initial, cb) => {
    listeners[name].add(cb);
    cb(initial());
    return () => listeners[name].delete(cb);
  };
  const ok = (data = {}) => new Promise((resolve) => setTimeout(() => resolve({ ok: true, status: 200, data }), 400));
  const fail = (status, error) => Promise.resolve({ ok: false, status, data: { error } });
  const inRange = (list, from, to, key = 'ts') => list.filter((x) => x[key] >= from && x[key] <= to);

  return {
    demo: true,
    simulateAlarm() {
      target = target > 6 ? 4.8 : 9.5;
      return target > 6;
    },
    auth: {
      onChange(cb) {
        const saved = sessionStorage.getItem('demoUser');
        cb(saved ? JSON.parse(saved) : null);
        this._cb = cb;
        return () => {};
      },
      async signIn(email) {
        const user = { uid: 'demo', email: email || 'demo@example.org' };
        sessionStorage.setItem('demoUser', JSON.stringify(user));
        this._cb?.(user);
      },
      async signOut() {
        sessionStorage.removeItem('demoUser');
        this._cb?.(null);
      },
    },
    getRole: async () => 'supervisor',
    subscribeUnit: (unitId, cb) => subscribe('unit', () => unit, cb),
    getReadings: async (unitId, from, to) => inRange(readings, from, to),
    getSummaries: async (unitId, kind, from, to) => inRange(summaries[kind], from, to, 'start'),
    getEvents: async (unitId, from, to) => inRange(events, from, to),
    subscribeEvents: (unitId, max, cb) => subscribe('events', () => newestFirst(events).slice(0, max), (list) => cb(list.slice(0, max))),
    subscribeExcursions: (unitId, cb) => subscribe('excursions', () => newestFirst(excursions), cb),
    subscribeAccess: (unitId, max, cb) => subscribe('access', () => newestFirst(access).slice(0, max), cb),
    api: {
      async action(unitId, name, body) {
        if (name === 'acknowledgeAlarm') {
          if (!unit.activeAlarms?.length) return fail(422, 'no active alarm');
          addEvent('ALARM_ACKNOWLEDGED', { by: 'demo user', alarms: unit.activeAlarms });
          return ok({ ok: true });
        }
        if (name === 'unlockDoor') return fail(422, 'lock not installed');
        if (name === 'setThresholds') return this.putThresholds(unitId, body);
        return fail(404, 'unknown action');
      },
      async putThresholds(unitId, body) {
        unit = { ...unit, thresholds: { ...unit.thresholds, ...body } };
        notify('unit', unit);
        return ok();
      },
      listContacts: async () => ({ ok: true, status: 200, data: contacts }),
      async saveContact(id, body) {
        if (!/^\+[1-9][0-9]{7,14}$/.test(body.phone || '')) return fail(400, 'phone must look like +250788123456');
        const saved = { id: id || `demo-${Date.now()}`, units: [raw.unitId], active: true, ...body };
        contacts = [...contacts.filter((c) => c.id !== saved.id), saved];
        return ok(saved);
      },
      async deleteContact(id) {
        contacts = contacts.filter((c) => c.id !== id);
        return ok();
      },
    },
  };
}
