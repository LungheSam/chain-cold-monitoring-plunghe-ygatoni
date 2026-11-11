// HTTP: public reads, auth and roles, actions round-trip to the (simulated) node, SSE, contacts API.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { event, listen, makeHarness, telemetry, UNIT, wait } from './helpers.js';

const SUP = { Authorization: 'Bearer tok-sup', 'Content-Type': 'application/json' };
const VIEW = { Authorization: 'Bearer tok-view', 'Content-Type': 'application/json' };

// Simulated node: answers every command it receives on MQTT
function autoReply(h, answer = (cmd) => ({ id: cmd.id, ok: true, error: null })) {
  const original = h.published.push.bind(h.published);
  h.published.push = (msg) => {
    original(msg);
    setTimeout(() => h.send('cmd/result', answer(msg.cmd)), 5);
    return h.published.length;
  };
}

async function withServer(fn, options) {
  const h = makeHarness(options);
  await h.send('telemetry', telemetry({ ts: h.now(), internalTemp: 5.1, status: 'ALARM' }));
  const server = await listen(h.app);
  try {
    await fn(h, server.url);
  } finally {
    await server.close();
    h.hub.close();
  }
}

test('public: TD, properties and health need no token', () => withServer(async (h, url) => {
  const td = await fetch(`${url}/things/${UNIT}`);
  assert.equal(td.status, 200);
  assert.match(td.headers.get('content-type'), /application\/td\+json/);
  const all = await (await fetch(`${url}/things/${UNIT}/properties`)).json();
  assert.equal(all.internalTemperature, 5.1);
  assert.equal(all.status, 'ALARM');
  assert.equal(all.thresholds.maxC, 8);
  assert.equal((await fetch(`${url}/things/${UNIT}/properties/nope`)).status, 404);
  assert.equal((await fetch(`${url}/things/unknown-unit`)).status, 404);
  assert.equal((await (await fetch(`${url}/health`)).json()).ok, true);
}));

test('actions: 401 without token, 403 for viewers and unknown users', () => withServer(async (h, url) => {
  const post = (headers) => fetch(`${url}/things/${UNIT}/actions/acknowledgeAlarm`, { method: 'POST', headers, body: '{}' });
  assert.equal((await post({})).status, 401);
  assert.equal((await post({ Authorization: 'Bearer garbage' })).status, 401);
  assert.equal((await post(VIEW)).status, 403);
  assert.equal((await post({ Authorization: 'Bearer tok-stranger' })).status, 403);
  assert.equal(h.published.length, 0);
}));

test('acknowledgeAlarm: sent to the node with who did it, node result returned', () => withServer(async (h, url) => {
  autoReply(h);
  const res = await fetch(`${url}/things/${UNIT}/actions/acknowledgeAlarm`, { method: 'POST', headers: SUP, body: '{}' });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).ok, true);
  assert.equal(h.published[0].topic, `coldchain/${UNIT}/cmd`);
  assert.equal(h.published[0].cmd.action, 'acknowledgeAlarm');
  assert.equal(h.published[0].cmd.params.by, 'sup@example.org');
}));

test('node refuses -> 422 with its error; no answer -> 504; unit offline -> 409', () => withServer(async (h, url) => {
  autoReply(h, (cmd) => ({ id: cmd.id, ok: false, error: 'lock not installed' }));
  let res = await fetch(`${url}/things/${UNIT}/actions/unlockDoor`, { method: 'POST', headers: SUP, body: '{}' });
  assert.equal(res.status, 422);
  assert.equal((await res.json()).error, 'lock not installed');
  assert.equal(h.published[0].cmd.params.method, 'qr');

  h.published.push = Array.prototype.push.bind(h.published); // node stops answering
  res = await fetch(`${url}/things/${UNIT}/actions/acknowledgeAlarm`, { method: 'POST', headers: SUP, body: '{}' });
  assert.equal(res.status, 504);

  await h.send('status', 'offline');
  res = await fetch(`${url}/things/${UNIT}/actions/acknowledgeAlarm`, { method: 'POST', headers: SUP, body: '{}' });
  assert.equal(res.status, 409);
}, { timeoutMs: 100 }));

test('thresholds: validated, written with PUT, then readable', () => withServer(async (h, url) => {
  autoReply(h);
  const put = (body) => fetch(`${url}/things/${UNIT}/properties/thresholds`, { method: 'PUT', headers: SUP, body: JSON.stringify(body) });
  assert.equal((await put({ maxC: 'hot' })).status, 400);
  assert.equal((await put({ colour: 'red' })).status, 400);
  assert.equal((await put({})).status, 400);
  assert.equal((await put({ maxC: 9, doorLimitS: 60 })).status, 204);
  const t = await (await fetch(`${url}/things/${UNIT}/properties/thresholds`)).json();
  assert.equal(t.maxC, 9);
  assert.equal(t.doorLimitS, 60);
  assert.equal(h.store.db.units.get(UNIT).thresholds.maxC, 9);
  // read-only property
  const ro = await fetch(`${url}/things/${UNIT}/properties/internalTemperature`, { method: 'PUT', headers: SUP, body: '{"value": 5}' });
  assert.equal(ro.status, 405);
  // unlockDoor input is checked too
  const bad = await fetch(`${url}/things/${UNIT}/actions/unlockDoor`, { method: 'POST', headers: SUP, body: '{"seconds": 60}' });
  assert.equal(bad.status, 400);
}));

test('SSE: events arrive on the stream; per-event stream is filtered', () => withServer(async (h, url) => {
  const all = new AbortController();
  const one = new AbortController();
  const resAll = await fetch(`${url}/things/${UNIT}/events`, { signal: all.signal });
  const resOne = await fetch(`${url}/things/${UNIT}/events/POWER_LOST`, { signal: one.signal });
  await h.send('event', event('DOOR_CLOSED', { openSeconds: 3, alarmed: false }, { ts: h.now() }));
  await h.send('event', event('POWER_LOST', {}, { ts: h.now() }));
  await wait(50);
  const read = async (res) => {
    const reader = res.body.getReader();
    const { value } = await reader.read();
    let text = new TextDecoder().decode(value);
    // read whatever else is already buffered
    const more = await Promise.race([reader.read(), wait(50).then(() => null)]);
    if (more?.value) text += new TextDecoder().decode(more.value);
    return text;
  };
  const textAll = await read(resAll);
  const textOne = await read(resOne);
  all.abort();
  one.abort();
  assert.match(textAll, /event: DOOR_CLOSED/);
  assert.match(textAll, /event: POWER_LOST/);
  assert.doesNotMatch(textOne, /DOOR_CLOSED/);
  assert.match(textOne, /event: POWER_LOST\ndata: \{/);
}));

test('dashboard API: /api/me and contacts (supervisor only, phone validated)', () => withServer(async (h, url) => {
  const me = await (await fetch(`${url}/api/me`, { headers: VIEW })).json();
  assert.deepEqual(me, { uid: 'view', email: 'view@example.org', role: 'viewer' });
  assert.equal((await fetch(`${url}/api/contacts`, { headers: VIEW })).status, 403);

  const bad = await fetch(`${url}/api/contacts`, { method: 'POST', headers: SUP, body: JSON.stringify({ name: 'X', phone: '0788123456' }) });
  assert.equal(bad.status, 400);
  const created = await fetch(`${url}/api/contacts`, { method: 'POST', headers: SUP, body: JSON.stringify({ name: 'Yves', phone: '+250788123456' }) });
  assert.equal(created.status, 201);
  const { id } = await created.json();
  const list = await (await fetch(`${url}/api/contacts`, { headers: SUP })).json();
  assert.equal(list.length, 2);
  assert.deepEqual(list.find((c) => c.id === id).units, [UNIT]);
  assert.equal((await fetch(`${url}/api/contacts/${id}`, { method: 'DELETE', headers: SUP })).status, 204);
  assert.equal((await fetch(`${url}/api/contacts/${id}`, { method: 'DELETE', headers: SUP })).status, 404);
}));

test('bad JSON body gives 400, unknown route 404, CORS for the dashboard origin', () => withServer(async (h, url) => {
  const res = await fetch(`${url}/api/contacts`, { method: 'POST', headers: SUP, body: '{oops' });
  assert.equal(res.status, 400);
  assert.equal((await fetch(`${url}/nothing-here`)).status, 404);
  const pre = await fetch(`${url}/api/me`, { method: 'OPTIONS', headers: { Origin: 'http://localhost:5173' } });
  assert.equal(pre.status, 204);
  assert.equal(pre.headers.get('access-control-allow-origin'), 'http://localhost:5173');
  const other = await fetch(`${url}/api/me`, { method: 'OPTIONS', headers: { Origin: 'https://evil.example' } });
  assert.equal(other.headers.get('access-control-allow-origin'), null);
}));
