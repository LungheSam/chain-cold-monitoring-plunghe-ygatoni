// Command bus: id + 30 s expiry, waits for the matching cmd/result, gives up after the timeout.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createCommandBus } from '../src/commands.js';

function makeBus(timeoutMs = 100) {
  const published = [];
  const now = () => 1_000_000;
  const bus = createCommandBus({ publish: (topic, payload) => published.push({ topic, cmd: JSON.parse(payload) }), now, timeoutMs });
  return { bus, published };
}

test('command has an id, the action, params and expires 30 s after it is sent', async () => {
  const { bus, published } = makeBus();
  const pending = bus.send('cold-unit-01', 'setThresholds', { maxC: 9 });
  const { topic, cmd } = published[0];
  assert.equal(topic, 'coldchain/cold-unit-01/cmd');
  assert.equal(cmd.action, 'setThresholds');
  assert.deepEqual(cmd.params, { maxC: 9 });
  assert.equal(cmd.expiresAt, 1_000_000 + 30000);
  assert.match(cmd.id, /^[0-9a-f-]{36}$/);
  bus.onResult('cold-unit-01', { id: cmd.id, ok: true, error: null });
  assert.deepEqual(await pending, { id: cmd.id, ok: true, error: null });
});

test('ids are unique', () => {
  const { bus, published } = makeBus();
  bus.send('cold-unit-01', 'acknowledgeAlarm');
  bus.send('cold-unit-01', 'acknowledgeAlarm');
  assert.notEqual(published[0].cmd.id, published[1].cmd.id);
});

test('no answer: resolves with a timeout error and forgets the command', async () => {
  const { bus } = makeBus(50);
  const result = await bus.send('cold-unit-01', 'unlockDoor');
  assert.equal(result.ok, false);
  assert.equal(result.error, 'timeout');
  assert.equal(bus.pendingCount(), 0);
});

test('a late answer after the timeout is ignored', async () => {
  const { bus, published } = makeBus(30);
  await bus.send('cold-unit-01', 'unlockDoor');
  assert.equal(bus.onResult('cold-unit-01', { id: published[0].cmd.id, ok: true }), false);
});

test('a result from another unit or with an unknown id does not complete the command', async () => {
  const { bus, published } = makeBus(50);
  const pending = bus.send('cold-unit-01', 'acknowledgeAlarm');
  assert.equal(bus.onResult('cold-unit-02', { id: published[0].cmd.id, ok: true }), false);
  assert.equal(bus.onResult('cold-unit-01', { id: 'nope', ok: true }), false);
  assert.equal((await pending).error, 'timeout');
});

test('node errors are passed through (e.g. the node refused an expired command)', async () => {
  const { bus, published } = makeBus();
  const pending = bus.send('cold-unit-01', 'setThresholds', { maxC: 9 });
  bus.onResult('cold-unit-01', { id: published[0].cmd.id, ok: false, error: 'expired' });
  assert.deepEqual(await pending, { id: published[0].cmd.id, ok: false, error: 'expired' });
});
