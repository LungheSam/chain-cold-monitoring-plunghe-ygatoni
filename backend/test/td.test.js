// The Thing Description must be valid against the official W3C TD 1.1 JSON Schema, and every
// form in it must point at a route that really works.
//
// test/fixtures/td-schema-v1.1.json is the official TD 1.1 JSON Schema, downloaded on 11 Nov 2026
// from https://www.w3.org/2022/wot/td-schema/v1.1 (its $id). Do not use the `main` branch of the
// w3c/wot-thing-description repository: it holds the draft of the next TD version.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { buildThingDescription } from '../src/td.js';
import { listen, makeHarness, telemetry, UNIT } from './helpers.js';

const schema = JSON.parse(readFileSync(new URL('./fixtures/td-schema-v1.1.json', import.meta.url)));

function validator() {
  const ajv = new Ajv({ strict: false, allErrors: true });
  addFormats(ajv);
  return ajv.compile(schema);
}

test('TD is valid against the W3C TD 1.1 JSON Schema', () => {
  const validate = validator();
  const td = buildThingDescription(UNIT, 'https://coldchain.example.org');
  const ok = validate(td);
  assert.ok(ok, JSON.stringify(validate.errors, null, 2));
});

test('the schema check really catches a broken TD', () => {
  const validate = validator();
  const td = buildThingDescription(UNIT, 'https://coldchain.example.org');
  delete td.security;
  assert.equal(validate(td), false);
});

test('TD has the required properties, actions and events', () => {
  const td = buildThingDescription(UNIT, 'http://localhost:3000');
  assert.deepEqual(Object.keys(td.properties).sort(), [
    'ambientTemperature', 'doorOpen', 'humidity', 'internalTemperature', 'mainsPower',
    'outOfRangeSeconds', 'status', 'thresholds']);
  assert.deepEqual(Object.keys(td.actions).sort(), ['acknowledgeAlarm', 'setThresholds', 'unlockDoor']);
  assert.ok(td.events.OUT_OF_RANGE_HIGH && td.events.POWER_LOST && td.events.ACCESS_GRANTED);
  assert.equal(td.properties.thresholds.readOnly, false);
  assert.equal(td.properties.internalTemperature.readOnly, true);
  assert.equal(td.base, 'http://localhost:3000/things/cold-unit-01/');
});

test('every TD form works against the running server', async () => {
  const h = makeHarness();
  await h.send('telemetry', telemetry({ internalTemp: 5.2 }));
  const server = await listen(h.app);
  try {
    const td = await (await fetch(`${server.url}/things/${UNIT}`)).json();
    const base = td.base.replace('http://localhost:3000', server.url);
    const forms = [
      ...td.forms,
      ...Object.values(td.properties).flatMap((p) => p.forms),
      ...Object.values(td.actions).flatMap((a) => a.forms),
      ...Object.values(td.events).flatMap((e) => e.forms),
    ];
    for (const form of forms) {
      const url = new URL(form.href, base).href;
      const op = form.op[0];
      if (op === 'readproperty' || op === 'readallproperties') {
        const res = await fetch(url);
        assert.equal(res.status, 200, `${op} ${url}`);
      } else if (op === 'subscribeevent' || op === 'subscribeallevents') {
        const controller = new AbortController();
        const res = await fetch(url, { signal: controller.signal });
        assert.equal(res.status, 200, url);
        assert.match(res.headers.get('content-type'), /text\/event-stream/);
        controller.abort();
      } else {
        // writeproperty / invokeaction without a token: the route exists and asks for auth
        const method = form['htv:methodName'];
        const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: '{}' });
        assert.equal(res.status, 401, `${method} ${url}`);
      }
    }
    const temp = await (await fetch(`${base}properties/internalTemperature`)).json();
    assert.equal(temp, 5.2);
  } finally {
    await server.close();
    h.hub.close();
  }
});
