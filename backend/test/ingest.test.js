// MQTT ingest: Firestore write limits, old (replayed) messages, events, excursions, summaries.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { meanKineticTemperature } from '../src/summaries.js';
import { publicEvent } from '../src/ingest.js';
import { event, makeHarness, T0, telemetry, UNIT } from './helpers.js';

const unitWrites = (h) => h.store.db.units.size; // not enough: count calls instead
function countUnitWrites(h) {
  let n = 0;
  const original = h.store.updateUnit.bind(h.store);
  h.store.updateUnit = async (...args) => {
    n += 1;
    return original(...args);
  };
  return () => n;
}

test('telemetry updates the live state and the unit document', async () => {
  const h = makeHarness();
  await h.send('telemetry', telemetry({ internalTemp: 4.6, thresholds: { minC: 2, maxC: 8, confirmDelayS: 300, doorLimitS: 120 } }));
  assert.equal(h.ingest.live(UNIT).internalTemp, 4.6);
  assert.equal(h.ingest.live(UNIT).status, 'OK');
  assert.equal(h.ingest.thresholds(UNIT).confirmDelayS, 300);
  const doc = h.store.db.units.get(UNIT);
  assert.equal(doc.internalTemp, 4.6);
  assert.equal(doc.online, true);
  assert.equal(doc.lastSeen, T0);
  assert.equal(unitWrites(h), 1);
});

test('unit document: at most one write per 15 s, but at once on status/door/power changes', async () => {
  const h = makeHarness();
  await h.send('telemetry', telemetry({ ts: h.now() }));
  const writes = countUnitWrites(h);
  for (let i = 1; i <= 4; i += 1) {          // telemetry every 5 s with small changes
    h.clock.t += 5000;
    await h.send('telemetry', telemetry({ ts: h.now(), internalTemp: 5 + i * 0.3 }));
  }
  assert.equal(writes(), 1);                  // only at 15 s
  h.clock.t += 1000;
  await h.send('telemetry', telemetry({ ts: h.now(), doorOpen: true, status: 'WARNING' }));
  assert.equal(writes(), 2);                  // important change: written at once
});

test('readings are stored at most once per 60 s', async () => {
  const h = makeHarness();
  for (let s = 0; s <= 300; s += 30) {        // telemetry every 30 s for 5 minutes
    await h.send('telemetry', telemetry({ ts: T0 + s * 1000 }));
  }
  assert.equal(h.store.db.readings.length, 6); // 0, 60, 120, 180, 240, 300 s
});

test('old telemetry replayed from the node queue does not overwrite live state', async () => {
  const h = makeHarness();
  await h.send('telemetry', telemetry({ ts: T0 + 600000, internalTemp: 5.0 }));
  await h.send('telemetry', telemetry({ ts: T0 + 60000, internalTemp: 9.9 }));
  assert.equal(h.ingest.live(UNIT).internalTemp, 5.0);
});

test('invalid messages are ignored', async () => {
  const h = makeHarness();
  await h.send('telemetry', 'not json');
  await h.send('telemetry', { ts: 'yesterday' });
  await h.send('event', { id: 'e', ts: T0, type: 'SELF_DESTRUCT', details: {} });
  assert.equal(h.store.db.readings.length, 0);
  assert.equal(h.store.db.events.size, 0);
  assert.equal(h.ingest.isOnline(UNIT), false);
});

test('messages for unknown units are ignored', async () => {
  const h = makeHarness();
  await h.ingest.handleMessage('coldchain/other-unit/telemetry', Buffer.from(JSON.stringify(telemetry())));
  assert.equal(h.store.db.units.size, 0);
});

test('events are stored once; delayed ones are marked', async () => {
  const h = makeHarness();
  const ev = event('DOOR_CLOSED', { openSeconds: 12, alarmed: false });
  await h.send('event', ev);
  await h.send('event', ev);
  h.clock.t += 10 * 60000;
  await h.send('event', event('DOOR_CLOSED', { openSeconds: 5, alarmed: false }, { ts: T0 }));
  const stored = [...h.store.db.events.values()];
  assert.equal(stored.length, 2);
  assert.equal(stored[0].delayed, false);
  assert.equal(stored[1].delayed, true);
});

test('excursion record from OUT_OF_RANGE and BACK_IN_RANGE, with cause guess "door"', async () => {
  const h = makeHarness();
  // door was open from 13:50 to 13:55 local; excursion starts at 13:58
  await h.send('event', event('DOOR_CLOSED', { openSeconds: 300, alarmed: true }, { ts: T0 - 5 * 60000 }));
  const start = T0 - 2 * 60000;
  await h.send('event', event('OUT_OF_RANGE_HIGH', { temp: 9.1, limit: 8, since: start, excursionId: 'x9', outOfRangeSeconds: 20 }));
  let exc = h.store.db.excursions.get(`${UNIT}/x9`);
  assert.equal(exc.end, null);
  assert.equal(exc.causeGuess, 'door');
  await h.send('event', event('BACK_IN_RANGE', {
    excursionId: 'x9', direction: 'HIGH', start, end: T0 + 600000, durationS: 720, outOfRangeSeconds: 700,
    minTemp: 7.6, maxTemp: 9.8, confirmed: true, offlineGapS: 0,
  }));
  exc = h.store.db.excursions.get(`${UNIT}/x9`);
  assert.equal(exc.maxTemp, 9.8);
  assert.equal(exc.durationS, 720);
  assert.equal(exc.causeGuess, 'door');
});

test('cause guess "power" wins over "door", and "unknown" when nothing happened', async () => {
  const h = makeHarness();
  await h.send('event', event('POWER_LOST', {}, { ts: T0 - 20 * 60000 }));
  await h.send('event', event('OUT_OF_RANGE_HIGH', { temp: 9, limit: 8, since: T0, excursionId: 'p1', outOfRangeSeconds: 20 }));
  assert.equal(h.store.db.excursions.get(`${UNIT}/p1`).causeGuess, 'power');

  const h2 = makeHarness();
  await h2.send('event', event('OUT_OF_RANGE_LOW', { temp: 1, limit: 2, since: T0, excursionId: 'u1', outOfRangeSeconds: 20 }));
  assert.equal(h2.store.db.excursions.get(`${UNIT}/u1`).causeGuess, 'unknown');
});

test('access events go to the access log; the public SSE copy has no user name', async () => {
  const h = makeHarness();
  const ev = event('ACCESS_GRANTED', { user: 'Samuel', method: 'keypad' });
  await h.send('event', ev);
  const entry = h.store.db.access.get(`${UNIT}/${ev.id}`);
  assert.equal(entry.result, 'GRANTED');
  assert.equal(entry.user, 'Samuel');
  assert.equal(publicEvent(ev).details.user, undefined);
  assert.equal(publicEvent(ev).details.method, 'keypad');
});

test('hourly and daily summaries: readings, % in range, door openings, power cuts, MKT', async () => {
  const h = makeHarness();
  // 50 minutes in range at 5 C, then 10 minutes at 9 C
  for (let m = 0; m < 60; m += 1) {
    await h.send('telemetry', telemetry({ ts: T0 + m * 60000, internalTemp: m < 50 ? 5 : 9 }));
  }
  await h.send('event', event('DOOR_CLOSED', { openSeconds: 40, alarmed: false }, { ts: T0 + 10 * 60000 }));
  await h.send('event', event('DOOR_CLOSED', { openSeconds: 130, alarmed: true }, { ts: T0 + 20 * 60000 }));
  await h.send('event', event('POWER_RESTORED', { durationS: 300 }, { ts: T0 + 40 * 60000 }));
  await h.summaries.flush(T0 + 30 * 60000);

  const hour = h.store.db.summaries.get(`${UNIT}/hourly/2026111514`);
  assert.equal(hour.count, 60);
  assert.equal(hour.secondsInRange, 50 * 60);
  assert.equal(hour.secondsOutOfRange, 10 * 60);
  assert.equal(hour.minTemp, 5);
  assert.equal(hour.maxTemp, 9);
  assert.equal(hour.doorOpenings, 2);
  assert.equal(hour.longestDoorOpenS, 130);
  assert.equal(hour.powerCuts, 1);
  assert.equal(hour.powerCutSeconds, 300);
  assert.equal(hour.sumAmbient / hour.countAmbient, 24);
  const day = h.store.db.summaries.get(`${UNIT}/daily/20261115`);
  assert.equal(day.count, 60);
  // MKT is above the plain mean (5.67 C) because warm periods count more
  const mkt = meanKineticTemperature(hour);
  assert.ok(mkt > 5.67 && mkt < 9, `MKT ${mkt}`);
});

test('summaries continue from the stored document after a restart', async () => {
  const h = makeHarness();
  await h.send('telemetry', telemetry({ ts: T0, internalTemp: 5 }));
  await h.summaries.flush(T0);
  // "restart": new summaries object on the same store
  const { createSummaries } = await import('../src/summaries.js');
  const fresh = createSummaries({ store: h.store });
  await fresh.addReading(UNIT, T0 + 60000, 6, 2, 8);
  await fresh.flush(T0 + 60000);
  assert.equal(h.store.db.summaries.get(`${UNIT}/hourly/2026111514`).count, 2);
});

test('a reading during a probe fault is stored but not counted in the summaries', async () => {
  const h = makeHarness();
  await h.send('telemetry', telemetry({ internalTemp: null, status: 'ALARM' }));
  await h.summaries.flush(T0);
  assert.equal(h.store.db.readings.length, 1);
  assert.equal(h.store.db.summaries.size, 0);
});
