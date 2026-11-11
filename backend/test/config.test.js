import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadConfig } from '../src/config.js';

test('defaults are sensible', () => {
  const c = loadConfig({});
  assert.equal(c.port, 3000);
  assert.deepEqual(c.unitIds, ['cold-unit-01']);
  assert.equal(c.sms.username, 'sandbox');
});

test('UNIT_IDS is split on commas', () => {
  const c = loadConfig({ UNIT_IDS: 'a, b' });
  assert.deepEqual(c.unitIds, ['a', 'b']);
});
