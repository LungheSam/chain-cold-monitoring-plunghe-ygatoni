// Back end entry point: connects MQTT, the store and SMS, and starts the HTTP server.
//   npm run dev     (reads backend/.env, restarts on file changes)
//   npm start       (production / Railway)
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import mqtt from 'mqtt';
import { loadConfig } from './config.js';
import { createMemoryStore } from './store/memoryStore.js';
import { createSummaries } from './summaries.js';
import { createAfricasTalkingSender, createConsoleSender, createSmsNotifier, createTelegramSender } from './sms.js';
import { createCommandBus } from './commands.js';
import { createHub } from './sse.js';
import { createIngest } from './ingest.js';
import { createAuth } from './auth.js';
import { createApp } from './app.js';

const log = console;
const config = loadConfig();

// ---- store and auth
let store;
let verifyIdToken = async () => {
  throw new Error('no Firebase');
};
if (config.store === 'memory') {
  log.warn('STORE=memory: data is kept in memory only and lost on restart');
  store = createMemoryStore();
} else {
  // Loaded only when needed: firebase-admin is large and slow to load
  const { createFirestoreStore, initFirebase } = await import('./store/firestoreStore.js');
  const firebase = initFirebase(config);
  store = createFirestoreStore(firebase.db);
  verifyIdToken = (token) => firebase.auth.verifyIdToken(token);
}

// ---- SMS
const sender = config.sms.apiKey ? createAfricasTalkingSender(config.sms) : createConsoleSender(log);
if (!config.sms.apiKey) log.warn('AT_API_KEY not set: SMS are only printed to the console');
// Telegram backup: on only when both the bot token and at least one chat id are set
const tg = config.telegram;
const backup = tg.botToken && tg.chatIds.length ? createTelegramSender(tg) : null;
log.info(backup ? `Telegram backup on (${tg.chatIds.length} chat(s))` : 'Telegram backup off (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_IDS not set)');

// ---- MQTT
const mqttOptions = {
  clientId: `coldchain-backend-${randomUUID().slice(0, 8)}`,
  username: config.mqtt.username || undefined,
  password: config.mqtt.password || undefined,
  reconnectPeriod: 2000,
  clean: true,
};
if (config.mqtt.caFile) mqttOptions.ca = readFileSync(config.mqtt.caFile);
let client;   // connected below, once the saved unit state is loaded

const summaries = createSummaries({ store, log });
const sms = createSmsNotifier({ store, sender, backup, log });
const bus = createCommandBus({
  publish: (topic, payload) => client.publish(topic, payload, { qos: 1 }),
  timeoutMs: config.commandTimeoutMs,
});
const hub = createHub();
const ingest = createIngest({ config, store, summaries, sms, bus, hub, log });
for (const unitId of config.unitIds) await ingest.load(unitId);

// Connect only now, and attach the handlers in the same step: if the connection finished while
// Firestore was still loading, the 'connect' event would be missed and we would never subscribe.
client = mqtt.connect(config.mqtt.url, mqttOptions);
client.on('connect', () => {
  log.info(`MQTT connected to ${config.mqtt.url}`);
  client.subscribe(['coldchain/+/telemetry', 'coldchain/+/event', 'coldchain/+/status', 'coldchain/+/cmd/result'], { qos: 1 });
});
client.on('reconnect', () => log.info('MQTT reconnecting...'));
client.on('error', (err) => log.error(`MQTT error: ${err.message}`));
client.on('message', (topic, payload) => ingest.handleMessage(topic, payload));

// ---- HTTP
const auth = createAuth({ verifyIdToken, getUserRole: (uid) => store.getUserRole(uid), devAuth: config.devAuth, log });
const app = createApp({ config, store, ingest, bus, hub, auth, log });
// Express 5 calls this also when listening FAILS (port in use, or reserved by Windows), so check the error
const server = app.listen(config.port, (err) => {
  if (err) {
    log.error(`Cannot listen on port ${config.port}: ${err.code || err.message}. Set another PORT in backend/.env `
      + '(on Windows, see reserved ports with: netsh interface ipv4 show excludedportrange protocol=tcp)');
    process.exit(1);
  }
  log.info(`HTTP on port ${config.port}, TD at ${config.publicBaseUrl}/things/${config.unitIds[0]}`);
});

// ---- timers
const offlineTimer = setInterval(() => ingest.checkOffline().catch((err) => log.error(err)), 10000);
const flushTimer = setInterval(() => summaries.flush().catch((err) => log.error(err)), 5 * 60 * 1000);

// ---- clean shutdown (Railway sends SIGTERM on redeploy)
async function shutdown() {
  log.info('shutting down');
  clearInterval(offlineTimer);
  clearInterval(flushTimer);
  hub.close();
  server.close();
  await summaries.flush().catch((err) => log.error(err));
  client.end(false, {}, () => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
