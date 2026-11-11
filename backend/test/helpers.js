// Test harness: the whole back end wired together with the memory store, a fake clock,
// a fake SMS sender and a fake MQTT publish. No network, no Firebase.
import { loadConfig } from '../src/config.js';
import { createMemoryStore } from '../src/store/memoryStore.js';
import { createSummaries } from '../src/summaries.js';
import { createSmsNotifier } from '../src/sms.js';
import { createCommandBus } from '../src/commands.js';
import { createHub } from '../src/sse.js';
import { createIngest } from '../src/ingest.js';
import { createAuth } from '../src/auth.js';
import { createApp } from '../src/app.js';

export const UNIT = 'cold-unit-01';
export const T0 = Date.UTC(2026, 10, 15, 12, 0, 0); // 15 Nov 2026 14:00 in Kigali

export const quietLog = { info() {}, warn() {}, error() {} };

export function makeHarness({ timeoutMs = 200 } = {}) {
  const clock = { t: T0 };
  const now = () => clock.t;
  const config = loadConfig({ STORE: 'memory', PUBLIC_BASE_URL: 'http://localhost:3000', UNIT_IDS: UNIT });
  const store = createMemoryStore();
  const smsSent = [];
  const sender = { async send(to, message) { smsSent.push({ to, message }); return 'fake'; } };
  const published = [];
  const summaries = createSummaries({ store, log: quietLog });
  const sms = createSmsNotifier({ store, sender, now, log: quietLog, holdMs: 20 });
  const bus = createCommandBus({ publish: (topic, payload) => published.push({ topic, cmd: JSON.parse(payload) }), now, timeoutMs });
  const hub = createHub();
  const ingest = createIngest({ config, store, summaries, sms, bus, hub, now, log: quietLog });

  // Fake Firebase: token "tok-<uid>" is valid for user <uid>
  const auth = createAuth({
    verifyIdToken: async (token) => {
      if (!token.startsWith('tok-')) throw new Error('bad token');
      return { uid: token.slice(4), email: `${token.slice(4)}@example.org` };
    },
    getUserRole: (uid) => store.getUserRole(uid),
    log: quietLog,
  });
  store.db.users.set('sup', { role: 'supervisor' });
  store.db.users.set('view', { role: 'viewer' });
  store.db.contacts.set('c1', { name: 'Nurse', phone: '+250788000001', units: [UNIT], active: true });

  const app = createApp({ config, store, ingest, bus, hub, auth, log: quietLog });

  const send = (kind, msg) => ingest.handleMessage(`coldchain/${UNIT}/${kind}`, Buffer.from(typeof msg === 'string' ? msg : JSON.stringify(msg)));

  return { clock, now, config, store, smsSent, published, summaries, sms, bus, hub, ingest, app, send };
}

export function telemetry(overrides = {}) {
  return {
    ts: overrides.ts ?? T0, internalTemp: 5.0, ambientTemp: 24.0, humidity: 60.0, doorOpen: false,
    mainsPower: true, status: 'OK', outOfRangeSeconds: 0, timeSynced: true, ...overrides,
  };
}

let eventCounter = 0;
export function event(type, details = {}, overrides = {}) {
  eventCounter += 1;
  return { id: `ev-${eventCounter}`, ts: overrides.ts ?? T0, type, details, timeSynced: true, ...overrides };
}

// Start the app on a free port; returns {url, close}
export async function listen(app) {
  const server = await new Promise((resolve) => {
    const s = app.listen(0, () => resolve(s));
  });
  return {
    url: `http://127.0.0.1:${server.address().port}`,
    close: () => new Promise((resolve) => {
      server.closeAllConnections();
      server.close(resolve);
    }),
  };
}

export const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
