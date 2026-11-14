// Checks that the cloud settings actually work, without printing any secret:
//   cd backend && npm run check
// 1. MQTT: logs in to the broker with the back end's user (backend/.env) and the node's user
//    (edge/.env), each with its own short-lived test connection.
// 2. Firestore: reads the unit document with the service-account key.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import mqtt from 'mqtt';

const ROOT = path.resolve(import.meta.dirname, '..', '..');

function readEnv(file) {
  const values = {};
  for (const line of readFileSync(path.join(ROOT, file), 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=(.*)$/);
    if (m) values[m[1]] = m[2].trim();
  }
  return values;
}

function tryMqtt(label, url, username, password) {
  return new Promise((resolve) => {
    const client = mqtt.connect(url, {
      username, password, clientId: `setup-check-${label}-${Date.now()}`, reconnectPeriod: 0, connectTimeout: 10000,
    });
    const done = (text) => {
      client.end(true);
      resolve(`${label.padEnd(8)} user "${username}": ${text}`);
    };
    client.on('connect', () => done('OK, logged in'));
    client.on('error', (err) => done(`FAILED: ${err.message}`));
  });
}

const be = readEnv('backend/.env');
const ed = readEnv('edge/.env');
const edgeUrl = `${ed.MQTT_TLS === '1' ? 'mqtts' : 'mqtt'}://${ed.MQTT_HOST}:${ed.MQTT_PORT}`;

console.log('MQTT broker:');
console.log('  ' + await tryMqtt('backend', be.MQTT_URL, be.MQTT_USERNAME, be.MQTT_PASSWORD));
console.log('  ' + await tryMqtt('node', edgeUrl, ed.MQTT_USERNAME, ed.MQTT_PASSWORD));

console.log('Firestore:');
try {
  if (be.STORE !== 'firestore') throw new Error(`STORE is ${be.STORE}, not firestore`);
  process.env.GOOGLE_APPLICATION_CREDENTIALS = path.join(ROOT, 'backend', be.GOOGLE_APPLICATION_CREDENTIALS);
  const { initFirebase } = await import('../src/store/firestoreStore.js');
  const { db } = initFirebase({ firebase: { projectId: be.FIREBASE_PROJECT_ID } });
  const unit = await db.collection('units').doc(be.UNIT_IDS.split(',')[0]).get();
  const users = await db.collection('users').get();
  console.log(`  OK: unit document ${unit.exists ? 'exists' : 'not created yet (fine before the first data)'}, `
    + `${users.size} user role(s) set`);
} catch (err) {
  console.log(`  FAILED: ${err.message.split('\n')[0]}`);
}
process.exit(0);
