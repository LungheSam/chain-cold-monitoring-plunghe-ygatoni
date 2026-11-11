// Seed the database with a realistic week of data, so the dashboard charts can be built before the
// hardware is ready. The generated MQTT messages are replayed through the real ingest code, so
// readings, summaries, events and excursions look exactly like live data.
//
//   npm run seed                          # into Firestore (uses backend/.env), raw readings for the last 2 days
//   npm run seed -- --readings-days 7     # all 7 days of raw readings (about 10 000 writes!)
//   npm run seed -- --dump ../frontend/src/demo/demo-data.json   # no Firebase: file for the dashboard demo mode
//
// Firestore free tier: 20 000 writes per day. The default seed writes about 3 500 documents
// (2 days of readings + summaries + events + excursions + access log). Seed the real project once.
import { writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { loadConfig } from '../src/config.js';
import { createMemoryStore } from '../src/store/memoryStore.js';
import { createSummaries } from '../src/summaries.js';
import { createIngest } from '../src/ingest.js';
import { generateWeek } from './lib/generate-week.js';

const { values: args } = parseArgs({
  options: {
    dump: { type: 'string' },
    'readings-days': { type: 'string', default: '2' },
    seed: { type: 'string', default: '42' },
  },
});

const config = loadConfig();
const unitId = config.unitIds[0];
const readingsDays = Number(args['readings-days']);
const quiet = { info() {}, warn() {}, error: console.error };

let store;
if (args.dump) {
  store = createMemoryStore();
} else {
  const { createFirestoreStore, initFirebase } = await import('../src/store/firestoreStore.js');
  store = createFirestoreStore(initFirebase(config).db);
}

const week = generateWeek({ end: Date.now(), seed: Number(args.seed) });
const keepReadingsFrom = week.end - readingsDays * 86400000;

// Wrap the store: count writes, write the unit document only once at the end, and skip raw
// readings older than --readings-days (the summaries still cover the whole week).
let writes = 0;
let lastUnitFields = {};
const seedStore = {
  ...store,
  async updateUnit(id, fields) {
    lastUnitFields = { ...lastUnitFields, ...fields };
  },
  async addReading(id, reading) {
    if (reading.ts < keepReadingsFrom) return;
    writes += 1;
    return store.addReading(id, reading);
  },
};
for (const name of ['setSummary', 'saveEventIfNew', 'upsertExcursion', 'addAccess']) {
  seedStore[name] = async (...a) => {
    writes += 1;
    return store[name](...a);
  };
}

const clock = { t: week.start };
const summaries = createSummaries({ store: seedStore, log: quiet });
const noSms = { async onEvent() {}, async onUnitOffline() {}, async onUnitOnline() {} };
const ingest = createIngest({
  config, store: seedStore, summaries, sms: noSms, bus: { onResult() {} }, hub: { broadcast() {} },
  now: () => clock.t, log: quiet,
});

console.log(`Seeding ${unitId}: ${week.messages.length} messages from ${new Date(week.start).toISOString()} to ${new Date(week.end).toISOString()}`);
let done = 0;
for (const m of week.messages) {
  clock.t = m.ts;
  await ingest.handleMessage(`coldchain/${unitId}/${m.kind}`, Buffer.from(JSON.stringify(m.msg)));
  done += 1;
  if (!args.dump && done % 1000 === 0) console.log(`  ${done} / ${week.messages.length}`);
}
await summaries.flush(week.end + 2 * 86400000);   // write every bucket
await store.updateUnit(unitId, { ...lastUnitFields, lastSeen: week.end, online: true });
writes += 1;
console.log(`Done: about ${writes} documents written.`);

if (args.dump) {
  const db = store.db;
  const forUnit = (map) => [...map.entries()].filter(([k]) => k.startsWith(`${unitId}/`)).map(([, v]) => v);
  const summariesOf = (kind) => [...db.summaries.entries()]
    .filter(([k]) => k.startsWith(`${unitId}/${kind}/`))
    .map(([k, v]) => ({ key: k.split('/')[2], ...v }));
  const round2 = (r) => ({ ...r, internalTemp: r.internalTemp, unitId: undefined });
  const data = {
    generatedAt: week.end,
    unitId,
    unit: db.units.get(unitId),
    readings: db.readings.filter((r) => r.unitId === unitId).map(round2),
    hourly: summariesOf('hourly'),
    daily: summariesOf('daily'),
    events: forUnit(db.events).map(({ receivedAt, delayed, ...e }) => e), // eslint-disable-line no-unused-vars
    excursions: [...db.excursions.entries()].filter(([k]) => k.startsWith(`${unitId}/`)).map(([k, v]) => ({ id: k.split('/')[1], ...v })),
    access: [...db.access.entries()].filter(([k]) => k.startsWith(`${unitId}/`)).map(([k, v]) => ({ id: k.split('/')[1], ...v })),
  };
  writeFileSync(args.dump, JSON.stringify(data));
  console.log(`Wrote ${args.dump}: ${data.readings.length} readings, ${data.hourly.length} hourly, ${data.daily.length} daily, ` +
    `${data.events.length} events, ${data.excursions.length} excursions, ${data.access.length} access entries`);
}
process.exit(0);
