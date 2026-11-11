// SMS rules: alert types, de-duplication (one per type per unit per 15 min), follow-ups only
// after an alert, delayed events, offline alerts, and message length.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { alertText, clearText } from '../src/sms.js';
import { event, makeHarness, telemetry, UNIT, wait } from './helpers.js';

const MIN = 60000;

function highEvent(h, extra = {}) {
  return event('OUT_OF_RANGE_HIGH', { temp: 9.4, limit: 8, since: h.now() - 20000, excursionId: 'x1', outOfRangeSeconds: 720, ...extra }, { ts: h.now() });
}

test('an out-of-range event sends one clear SMS to the contacts', async () => {
  const h = makeHarness();
  await h.send('event', highEvent(h));
  assert.equal(h.smsSent.length, 1);
  assert.deepEqual(h.smsSent[0].to, ['+250788000001']);
  assert.equal(h.smsSent[0].message, 'ALERT cold-unit-01: temp 9.4C above 8C since 13:59. Out of range total 12 min.');
  assert.equal(h.store.db.smsLog.length, 1);
});

test('de-duplication: at most one SMS per event type per unit per 15 minutes', async () => {
  const h = makeHarness();
  await h.send('event', highEvent(h));
  h.clock.t += 10 * MIN;
  await h.send('event', highEvent(h));                         // same type within 15 min: suppressed
  await h.send('event', event('POWER_LOST', {}, { ts: h.now() })); // other type: sent
  h.clock.t += 6 * MIN;                                         // 16 min after the first
  await h.send('event', highEvent(h));
  const alerts = h.smsSent.map((s) => s.message.split(':')[1].trim().split(' ')[0]);
  assert.equal(h.smsSent.length, 3);
  assert.deepEqual(alerts, ['temp', 'mains', 'temp']);
});

test('duplicate delivery of the same event never sends twice', async () => {
  const h = makeHarness();
  const ev = highEvent(h);
  await h.send('event', ev);
  await h.send('event', ev);
  assert.equal(h.smsSent.length, 1);
});

test('follow-up when the problem clears, with its duration', async () => {
  const h = makeHarness();
  await h.send('event', event('POWER_LOST', {}, { ts: h.now() }));
  h.clock.t += 12 * MIN;
  await h.send('event', event('POWER_RESTORED', { durationS: 720 }, { ts: h.now() }));
  assert.equal(h.smsSent.length, 2);
  assert.equal(h.smsSent[1].message, 'OK cold-unit-01: mains power restored after 12 min.');
});

test('no follow-up for problems that never alerted', async () => {
  const h = makeHarness();
  // short blip (unconfirmed) and a short door opening: no SMS at all
  await h.send('event', event('BACK_IN_RANGE', { confirmed: false, direction: 'HIGH', excursionId: 'b1', durationS: 10 }));
  await h.send('event', event('DOOR_CLOSED', { openSeconds: 5, alarmed: false }));
  assert.equal(h.smsSent.length, 0);
});

test('no follow-up when the alert itself was suppressed', async () => {
  const h = makeHarness();
  await h.send('event', event('DOOR_OPEN_TOO_LONG', { openSeconds: 15, limitS: 15 }, { ts: h.now() }));
  await h.send('event', event('DOOR_CLOSED', { openSeconds: 20, alarmed: true }, { ts: h.now() }));
  h.clock.t += 5 * MIN;
  await h.send('event', event('DOOR_OPEN_TOO_LONG', { openSeconds: 15, limitS: 15 }, { ts: h.now() })); // suppressed
  await h.send('event', event('DOOR_CLOSED', { openSeconds: 30, alarmed: true }, { ts: h.now() }));     // no follow-up
  assert.deepEqual(h.smsSent.map((s) => s.message.slice(0, 5)), ['ALERT', 'OK co']);
});

test('excursion follow-up gives duration and peak temperature', async () => {
  const h = makeHarness();
  await h.send('event', highEvent(h));
  h.clock.t += 18 * MIN;
  await h.send('event', event('BACK_IN_RANGE', {
    excursionId: 'x1', direction: 'HIGH', confirmed: true, start: h.now() - 18 * MIN, end: h.now(),
    durationS: 1080, outOfRangeSeconds: 1060, minTemp: 7.6, maxTemp: 9.6,
  }, { ts: h.now() }));
  assert.equal(h.smsSent[1].message, 'OK cold-unit-01: temp back in range at 14:18. Excursion lasted 18 min (max 9.6C).');
});

test('delayed alert is marked, and skipped if it cleared in the same batch', async () => {
  const h = makeHarness();
  h.clock.t += 30 * MIN;
  const old = h.now() - 20 * MIN;
  // Replayed batch: power lost and restored long ago -> no SMS at all
  await h.send('event', event('POWER_LOST', {}, { ts: old }));
  await h.send('event', event('POWER_RESTORED', { durationS: 60 }, { ts: old + MIN }));
  // Replayed alert still going on -> "(delayed)" after the hold
  await h.send('event', event('DOOR_OPEN_TOO_LONG', { openSeconds: 15, limitS: 15 }, { ts: old }));
  await wait(60);
  assert.equal(h.smsSent.length, 1);
  assert.match(h.smsSent[0].message, /^\(delayed\) ALERT cold-unit-01: door open/);
});

test('offline for more than 2 minutes sends an SMS, and coming back sends a follow-up', async () => {
  const h = makeHarness();
  await h.send('telemetry', telemetry({ ts: h.now() }));
  h.clock.t += 90000;
  await h.send('status', 'offline');            // Last Will from the broker
  await h.ingest.checkOffline();
  assert.equal(h.smsSent.length, 0);            // only 1.5 min since last seen
  assert.equal(h.ingest.live(UNIT).status, 'OFFLINE');
  h.clock.t += 31000;
  await h.ingest.checkOffline();
  assert.equal(h.smsSent.length, 1);
  assert.match(h.smsSent[0].message, /^ALERT cold-unit-01: unit offline since 14:00/);
  await h.ingest.checkOffline();
  assert.equal(h.smsSent.length, 1);            // only once
  h.clock.t += 5 * MIN;
  await h.send('status', 'online');
  assert.equal(h.smsSent.length, 2);
  assert.match(h.smsSent[1].message, /back online after 7 min/);
});

test('silence without a Last Will also counts as offline', async () => {
  const h = makeHarness();
  await h.send('telemetry', telemetry({ ts: h.now() }));
  h.clock.t += 2 * MIN + 1000;
  await h.ingest.checkOffline();
  assert.equal(h.ingest.isOnline(UNIT), false);
  assert.equal(h.smsSent.length, 1);
});

test('no contacts: nothing sent, nothing crashes', async () => {
  const h = makeHarness();
  h.store.db.contacts.clear();
  await h.send('event', highEvent(h));
  assert.equal(h.smsSent.length, 0);
});

test('every message fits in one SMS (160 characters)', () => {
  const t = Date.UTC(2026, 10, 15, 12, 2);
  const unit = 'cold-unit-01';
  const texts = [
    alertText(unit, { type: 'OUT_OF_RANGE_LOW', ts: t, details: { temp: -12.35, limit: 2, since: t, outOfRangeSeconds: 360000 } }),
    alertText(unit, { type: 'DOOR_OPEN_TOO_LONG', ts: t, details: { openSeconds: 7200, limitS: 120 } }),
    alertText(unit, { type: 'POWER_LOST', ts: t, details: {} }),
    alertText(unit, { type: 'SENSOR_FAULT', ts: t, details: { sensor: 'ds18b20', reason: 'read_error' } }),
    alertText(unit, { type: 'OFFLINE', ts: t, details: {} }),
    '(delayed) ' + alertText(unit, { type: 'OUT_OF_RANGE_HIGH', ts: t, details: { temp: 12.5, limit: 8, since: t, outOfRangeSeconds: 99999 } }),
    clearText(unit, { type: 'BACK_IN_RANGE', ts: t, details: { direction: 'LOW', durationS: 99999, minTemp: -1.25 } }),
    clearText(unit, { type: 'SENSOR_RESTORED', ts: t, details: { sensor: 'ds18b20' } }),
  ];
  for (const text of texts) assert.ok(text.length <= 160, `${text.length}: ${text}`);
});
