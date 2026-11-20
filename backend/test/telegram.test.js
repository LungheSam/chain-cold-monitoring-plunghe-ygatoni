// Telegram backup channel: every SMS text also goes to Telegram, and a failure on one channel
// never stops the other.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createSmsNotifier, createTelegramSender } from '../src/sms.js';

const quietLog = { info() {}, warn() {}, error() {} };
const UNIT = 'cold-unit-01';
const highEvent = () => ({
  type: 'OUT_OF_RANGE_HIGH', ts: Date.UTC(2026, 10, 20, 12, 0),
  details: { temp: 9.4, limit: 8, since: Date.UTC(2026, 10, 20, 12, 0), outOfRangeSeconds: 60 },
});

// Small fake store with just what the notifier uses
function fakeStore(phones = ['+250788000001']) {
  const smsLog = [];
  let state = { lastAlertAt: {}, open: {} };
  return {
    smsLog,
    async getContactsForUnit() { return phones.map((phone) => ({ phone })); },
    async getSmsState() { return state; },
    async setSmsState(_unit, s) { state = s; },
    async addSmsLog(entry) { smsLog.push(entry); },
  };
}

function fakeChannel({ fail = false } = {}) {
  const sent = [];
  return {
    sent,
    async send(...args) {
      if (fail) throw new Error('down');
      sent.push(args.at(-1)); // the message is the last argument for both channels
      return 'ok';
    },
  };
}

test('an alert goes to SMS and to Telegram, and both results are logged', async () => {
  const store = fakeStore();
  const sms = fakeChannel();
  const tg = fakeChannel();
  const n = createSmsNotifier({ store, sender: sms, backup: tg, log: quietLog });
  await n.onEvent(UNIT, highEvent());
  assert.equal(sms.sent.length, 1);
  assert.deepEqual(tg.sent, sms.sent);
  assert.equal(store.smsLog[0].providerStatus, 'ok');
  assert.equal(store.smsLog[0].telegramStatus, 'ok');
});

test('SMS failing still sends Telegram', async () => {
  const store = fakeStore();
  const tg = fakeChannel();
  const n = createSmsNotifier({ store, sender: fakeChannel({ fail: true }), backup: tg, log: quietLog });
  await n.onEvent(UNIT, highEvent());
  assert.equal(tg.sent.length, 1);
  assert.match(store.smsLog[0].providerStatus, /^error/);
});

test('Telegram failing does not stop the SMS', async () => {
  const store = fakeStore();
  const sms = fakeChannel();
  const n = createSmsNotifier({ store, sender: sms, backup: fakeChannel({ fail: true }), log: quietLog });
  await n.onEvent(UNIT, highEvent());
  assert.equal(sms.sent.length, 1);
  assert.match(store.smsLog[0].telegramStatus, /^error/);
});

test('no SMS contacts: Telegram still gets the alert', async () => {
  const store = fakeStore([]);
  const sms = fakeChannel();
  const tg = fakeChannel();
  const n = createSmsNotifier({ store, sender: sms, backup: tg, log: quietLog });
  await n.onEvent(UNIT, highEvent());
  assert.equal(sms.sent.length, 0);
  assert.equal(tg.sent.length, 1);
});

test('Telegram sender posts to every chat and reports each result', async () => {
  const calls = [];
  const fetchFn = async (url, opts) => {
    calls.push({ url, body: JSON.parse(opts.body) });
    const ok = JSON.parse(opts.body).chat_id === '111';
    return { status: ok ? 200 : 400, json: async () => (ok ? { ok: true } : { ok: false, description: 'chat not found' }) };
  };
  const tg = createTelegramSender({ botToken: 'TOKEN', chatIds: ['111', '222'], fetchFn });
  const status = await tg.send('hello');
  assert.equal(calls.length, 2);
  assert.equal(calls[0].url, 'https://api.telegram.org/botTOKEN/sendMessage');
  assert.deepEqual(calls[0].body, { chat_id: '111', text: 'hello' });
  assert.equal(status, '111:ok, 222:error 400 chat not found');
});
