// End-to-end test of the whole chain, on one laptop, with nothing to install or sign up for:
//
//   MQTT broker (aedes, inside this process)  <->  mock edge node (edge/, real code, fake sensors)
//                                              <->  back end (real code, STORE=memory, DEV_AUTH=1)
//   and this script talks to the back end only through the Web Thing HTTP API + SSE, like the dashboard.
//
// Run:  cd backend && npm run e2e        (about 1.5 minutes; the edge venv must exist, see edge/README.md)
//
// It drives the node by typing simulator commands into it (temp 9.5, door open, key 2468#, ...), and
// checks: alarm confirm delay, SMS, acknowledge, thresholds, back in range, QR and keypad unlock,
// keypad lockout, a broker outage (events queued on the node and delivered later, in order),
// power cut, a crash (Last Will -> OFFLINE) and that the out-of-range total survives a restart.
import { execFileSync, spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { Aedes } from 'aedes';

const ROOT = path.resolve(import.meta.dirname, '..', '..');
const EDGE = path.join(ROOT, 'edge');
const PY = process.platform === 'win32'
  ? path.join(EDGE, '.venv', 'Scripts', 'python.exe')
  : path.join(EDGE, '.venv', 'bin', 'python');
const MQTT_PORT = 18884;
const HTTP_PORT = 3998;
const BASE = `http://localhost:${HTTP_PORT}`;
const THING = `${BASE}/things/cold-unit-01`;
const SUP = { Authorization: 'Bearer dev-supervisor', 'Content-Type': 'application/json' };
const VIEWER = { Authorization: 'Bearer dev-viewer', 'Content-Type': 'application/json' };
const PIN = '2468';

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const tmp = mkdtempSync(path.join(tmpdir(), 'coldchain-e2e-'));
const results = [];
const backendLog = [];
const events = [];           // every event received on the public SSE stream

// ---------------------------------------------------------------- small helpers

function record(ok, text) {
  results.push({ ok, text });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${text}`);
}

async function waitFor(text, fn, timeoutMs) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    const value = await fn().catch(() => null);
    if (value) {
      record(true, text);
      return value;
    }
    await wait(500);
  }
  record(false, `${text} (nothing after ${timeoutMs / 1000} s)`);
  return null;
}

const prop = async (name) => (await fetch(`${THING}/properties/${name}`)).json();
const action = (name, body = {}, headers = SUP) =>
  fetch(`${THING}/actions/${name}`, { method: 'POST', headers, body: JSON.stringify(body) });
const eventsOf = (type) => events.filter((e) => e.type === type);
const newEvent = (type, after) => () => Promise.resolve(eventsOf(type).find((e) => events.indexOf(e) >= after));

// ---------------------------------------------------------------- the three programs

let broker;
let brokerServer;
async function startBroker() {
  broker = await Aedes.createBroker();
  brokerServer = createServer(broker.handle);
  await new Promise((resolve) => brokerServer.listen(MQTT_PORT, resolve));
}
async function stopBroker() {
  await new Promise((resolve) => broker.close(resolve));       // drops every client connection
  await new Promise((resolve) => brokerServer.close(resolve));
}

function startBackend() {
  const proc = spawn(process.execPath, ['src/index.js'], {
    cwd: path.join(ROOT, 'backend'),
    env: {
      ...process.env, STORE: 'memory', DEV_AUTH: '1', PORT: String(HTTP_PORT), PUBLIC_BASE_URL: BASE,
      MQTT_URL: `mqtt://localhost:${MQTT_PORT}`, MQTT_USERNAME: '', MQTT_PASSWORD: '', AT_API_KEY: '',
    },
  });
  for (const stream of [proc.stdout, proc.stderr]) stream.on('data', (d) => backendLog.push(String(d)));
  return proc;
}

function startNode() {
  const proc = spawn(PY, ['-u', '-m', 'coldchain.node', '--env', path.join(tmp, 'none.env')], {
    cwd: EDGE,
    env: {
      ...process.env, UNIT_ID: 'cold-unit-01', PROFILE: 'demo', MOCK_HARDWARE: '1',
      MQTT_HOST: 'localhost', MQTT_PORT: String(MQTT_PORT), MQTT_TLS: '0', MQTT_USERNAME: '', MQTT_PASSWORD: '',
      DATA_DIR: path.join(tmp, 'data'), KEYPAD_INSTALLED: '1', LOCK_INSTALLED: '1',
      PINS_FILE: path.join(tmp, 'pins.json'), PYTHONUNBUFFERED: '1',
    },
  });
  proc.stdout.resume();
  proc.stderr.resume();
  return proc;
}

function type(nodeProc, line) {
  console.log(`      node> ${line}`);
  nodeProc.stdin.write(line + '\n');
}

function listenToEvents() {
  const ctl = new AbortController();
  fetch(`${THING}/events`, { signal: ctl.signal }).then(async (res) => {
    let buffer = '';
    for await (const chunk of res.body) {
      buffer += new TextDecoder().decode(chunk);
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop();
      for (const block of blocks) {
        const data = block.split('\n').find((l) => l.startsWith('data: '));
        if (data) events.push(JSON.parse(data.slice(6)));
      }
    }
  }).catch(() => {});
  return ctl;
}

// ---------------------------------------------------------------- the test

async function main() {
  // A keypad PIN for the node (stored hashed, like on the Pi)
  execFileSync(PY, ['-c', `from coldchain.pins import PinStore; PinStore(r"${path.join(tmp, 'pins.json')}").add("Tester", "${PIN}")`],
    { cwd: EDGE });

  await startBroker();
  const backend = startBackend();
  await waitFor('back end answers on /health', async () => (await fetch(`${BASE}/health`)).ok, 30000);
  await fetch(`${BASE}/api/contacts`, { method: 'POST', headers: SUP, body: JSON.stringify({ name: 'E2E', phone: '+250788000001' }) });
  const sse = listenToEvents();
  let node = startNode();

  console.log('\n-- 1. Node online, Web Thing readable');
  await waitFor('status property becomes OK (node online, first telemetry)', async () => (await prop('status')) === 'OK', 30000);
  const td = await (await fetch(THING)).json();
  record(td.title && td.properties.internalTemperature && td.actions.unlockDoor, 'Thing Description served with properties and actions');
  const t0 = await prop('internalTemperature');
  record(t0 > 4 && t0 < 6, `internalTemperature is about 5 C (${t0})`);

  console.log('\n-- 2. Temperature alarm (demo profile: confirmed after 20 s)');
  let mark = events.length;
  type(node, 'temp 9.5');
  await waitFor('status WARNING while the 20 s confirm delay runs', async () => (await prop('status')) === 'WARNING', 15000);
  const high = await waitFor('OUT_OF_RANGE_HIGH event after the confirm delay', newEvent('OUT_OF_RANGE_HIGH', mark), 40000);
  record(high && high.details.outOfRangeSeconds >= 19, `the out-of-range time counts from the first bad reading (${high?.details.outOfRangeSeconds} s)`);
  await waitFor('status ALARM', async () => (await prop('status')) === 'ALARM', 10000);
  await waitFor('SMS alert sent (console sender)', async () => backendLog.join('').includes('[console SMS'), 10000);

  console.log('\n-- 3. Acknowledge and thresholds (supervisor only)');
  record((await action('acknowledgeAlarm', {}, VIEWER)).status === 403, 'viewer cannot acknowledge (403)');
  mark = events.length;
  record((await action('acknowledgeAlarm')).status === 200, 'supervisor acknowledges (200)');
  await waitFor('ALARM_ACKNOWLEDGED event', newEvent('ALARM_ACKNOWLEDGED', mark), 10000);
  const put = (body) => fetch(`${THING}/properties/thresholds`, { method: 'PUT', headers: SUP, body: JSON.stringify(body) });
  record((await put({ doorLimitS: 12 })).status === 204, 'PUT thresholds {doorLimitS: 12} accepted by the node (204)');
  record((await prop('thresholds')).doorLimitS === 12, 'thresholds property shows the new door limit');
  record((await put({ minC: 25 })).status === 422, 'node refuses minC 25 (above maxC) with 422');

  console.log('\n-- 4. Back in range');
  mark = events.length;
  type(node, 'temp 5.0');
  const back = await waitFor('BACK_IN_RANGE event', newEvent('BACK_IN_RANGE', mark), 30000);
  record(back && back.details.confirmed && back.details.maxTemp >= 9.4, `excursion record: ${back?.details.durationS} s, max ${back?.details.maxTemp} C`);
  await waitFor('status back to OK', async () => (await prop('status')) === 'OK', 15000);
  const totalBefore = await prop('outOfRangeSeconds');
  record(totalBefore >= 20, `outOfRangeSeconds total kept (${totalBefore} s)`);

  console.log('\n-- 5. Door access: QR unlock, keypad PIN, lockout');
  mark = events.length;
  record((await action('unlockDoor', {}, VIEWER)).status === 403, 'viewer cannot unlock from the QR page (403)');
  record((await action('unlockDoor')).status === 200, 'supervisor unlocks (200)');
  const qr = await waitFor('ACCESS_GRANTED (qr) event', newEvent('ACCESS_GRANTED', mark), 10000);
  record(qr && qr.details.method === 'qr' && qr.details.user === undefined, 'public event stream has no user name');
  await wait(11000);                                    // 5 s open + 5 s rest for the solenoid
  mark = events.length;
  type(node, `key ${PIN}#`);
  const kp = await waitFor('ACCESS_GRANTED (keypad) event', newEvent('ACCESS_GRANTED', mark), 10000);
  record(kp?.details.method === 'keypad', 'unlock came from the keypad');
  mark = events.length;
  for (let i = 0; i < 3; i += 1) type(node, 'key 1111#');
  await waitFor('3 wrong PINs -> 3 ACCESS_DENIED, the last one locks the keypad 60 s',
    async () => eventsOf('ACCESS_DENIED').filter((e) => events.indexOf(e) >= mark).at(2)?.details.lockedOutS === 60, 15000);

  console.log('\n-- 6. Broker outage: the node keeps working and replays its queue');
  await stopBroker();
  console.log('      (broker stopped)');
  type(node, 'door open');
  await wait(20000);                                    // door limit is now 12 s: the alarm happens offline
  type(node, 'door close');
  await wait(2000);
  mark = events.length;
  await startBroker();
  console.log('      (broker restarted)');
  const closed = await waitFor('queued DOOR_CLOSED delivered after reconnect', newEvent('DOOR_CLOSED', mark), 60000);
  const tooLong = eventsOf('DOOR_OPEN_TOO_LONG').find((e) => events.indexOf(e) >= mark);
  record(tooLong && closed && events.indexOf(tooLong) < events.indexOf(closed),
    'DOOR_OPEN_TOO_LONG (raised while offline) arrived too, before DOOR_CLOSED');
  record(closed?.details.openSeconds >= 18 && closed?.details.alarmed, `door was open ${closed?.details.openSeconds} s (alarmed)`);

  console.log('\n-- 7. Power cut (demo profile: confirmed after 3 s)');
  mark = events.length;
  type(node, 'power off');
  await waitFor('POWER_LOST event', newEvent('POWER_LOST', mark), 15000);
  type(node, 'power on');
  await waitFor('POWER_RESTORED event', newEvent('POWER_RESTORED', mark), 15000);

  console.log('\n-- 8. Crash and restart');
  node.kill('SIGKILL');
  await waitFor('Last Will: status OFFLINE after the node is killed', async () => (await prop('status')) === 'OFFLINE', 20000);
  node = startNode();
  await waitFor('node back online after restart', async () => ['OK', 'WARNING', 'ALARM'].includes(await prop('status')), 30000);
  const totalAfter = await prop('outOfRangeSeconds');
  record(totalAfter >= totalBefore, `out-of-range total survived the crash (${totalBefore} s -> ${totalAfter} s)`);

  // ---- clean up
  sse.abort();
  node.kill();
  backend.kill();
  await wait(1000);
  await stopBroker();
  rmSync(tmp, { recursive: true, force: true });

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length} passed, ${failed.length} failed`);
  if (failed.length) {
    console.log('\nLast lines of the back end log:\n' + backendLog.join('').split('\n').slice(-15).join('\n'));
  }
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
