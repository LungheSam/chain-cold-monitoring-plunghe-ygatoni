// Generates a realistic week of MQTT messages (telemetry every 60 s + events) for one unit,
// as the node would have sent them. Used by scripts/seed.js. Deterministic: the same seed gives
// the same week (only the end time moves).
//
// The fridge model, per minute:
//   internal = compressor cycle (4.8 C +/- 0.9 C, 40 min period) + offset + noise
//   offset   rises while the door is open (0.45 C per minute open) or the power is cut
//            (0.05 C per minute), and decays back (time constant 8 min) when the compressor runs.
//   Kigali ambient: about 17 C at 03:00 to 25 C mid-afternoon; humidity the other way round.
// Planned incidents (local time, day 0 = 7 days ago):
//   every clinic day 08:00-17:00: 8-15 short door openings (10-90 s), each after a keypad ACCESS_GRANTED
//   day 1 10:30  door left open 10 min       -> DOOR_OPEN_TOO_LONG, excursion HIGH (cause: door)
//   day 3 13:00  power cut 75 min            -> POWER_LOST/RESTORED, excursion HIGH (cause: power)
//   day 4 19:00  power cut 25 min            -> no excursion
//   day 5 02:00  thermostat fault 40 min     -> excursion LOW (freezing risk)
//   day 6 11:00  door open 4 min             -> door alarm only (temperature stays in range)
//   two ACCESS_DENIED (wrong PIN) during the week
// Alarm rules = the node's "real" profile: confirm 300 s, door limit 120 s, power confirm 5 s.
import { KIGALI_OFFSET_MS } from '../../src/time.js';

const MIN = 60000;
const DAY = 86400000;
const THRESHOLDS = { minC: 2.0, maxC: 8.0, confirmDelayS: 300, doorLimitS: 120 };
const USERS = ['Samuel', 'Yves', 'Nurse Aline', 'Nurse Eric'];

// Small seeded random number generator (mulberry32)
function makeRandom(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const round = (x, digits) => Number(x.toFixed(digits));

export function generateWeek({ end, days = 7, seed = 42 }) {
  const rand = makeRandom(seed);
  const endMinute = Math.floor(end / MIN) * MIN;
  const start = endMinute - days * DAY;
  // Local midnight of day 0
  const day0 = Math.floor((start + KIGALI_OFFSET_MS) / DAY) * DAY - KIGALI_OFFSET_MS + DAY;
  const at = (day, hour, minute = 0) => day0 + day * DAY + hour * 3600000 + minute * MIN;

  // ---------------------------------------------------------------- plan the incidents
  const doors = []; // {open, seconds}
  for (let d = 0; d < days; d += 1) {
    const count = 8 + Math.floor(rand() * 8);
    for (let i = 0; i < count; i += 1) {
      const open = at(d, 8) + Math.floor(rand() * 9 * 3600) * 1000;
      doors.push({ open, seconds: 10 + Math.floor(rand() * 80) });
    }
  }
  doors.push({ open: at(1, 10, 30), seconds: 10 * 60 });
  doors.push({ open: at(6, 11, 0), seconds: 4 * 60 });
  doors.sort((a, b) => a.open - b.open);
  // drop openings that overlap the previous one
  const doorList = doors.filter((d, i) => i === 0 || d.open > doors[i - 1].open + doors[i - 1].seconds * 1000 + MIN);

  const powerCuts = [
    { from: at(3, 13, 0), to: at(3, 14, 15) },
    { from: at(4, 19, 0), to: at(4, 19, 25) },
  ];
  const thermostatFault = { from: at(5, 2, 0), to: at(5, 2, 40) };
  const denied = [at(2, 9, 12), at(4, 16, 47)];

  // ---------------------------------------------------------------- simulate
  const messages = [];
  let n = 0;
  const event = (ts, type, details) => {
    n += 1;
    messages.push({ kind: 'event', ts, msg: { id: `seed-${seed}-${n}`, ts, type, details, timeSynced: true } });
  };

  // Door, power and access events are fixed in time
  for (const d of doorList) {
    if (d.open < start || d.open > endMinute) continue;
    const closed = d.open + d.seconds * 1000;
    event(d.open - 5000, 'ACCESS_GRANTED', { user: USERS[Math.floor(rand() * USERS.length)], method: 'keypad' });
    if (d.seconds > THRESHOLDS.doorLimitS) {
      event(d.open + THRESHOLDS.doorLimitS * 1000, 'DOOR_OPEN_TOO_LONG', { openSeconds: THRESHOLDS.doorLimitS, limitS: THRESHOLDS.doorLimitS });
      event(d.open + THRESHOLDS.doorLimitS * 1000 + 40000, 'ALARM_ACKNOWLEDGED', { by: 'keypad', alarms: ['DOOR_OPEN'] });
    }
    if (closed <= endMinute) event(closed, 'DOOR_CLOSED', { openSeconds: d.seconds, alarmed: d.seconds > THRESHOLDS.doorLimitS });
  }
  for (const p of powerCuts) {
    event(p.from + 5000, 'POWER_LOST', {});
    event(p.to + 5000, 'POWER_RESTORED', { durationS: (p.to - p.from) / 1000 });
  }
  for (const ts of denied) event(ts, 'ACCESS_DENIED', { user: null, method: 'keypad', reason: 'wrong PIN x3' });

  // Minute by minute: temperature, excursions and telemetry
  let offset = 0;
  let total = 0;          // cumulative out-of-range seconds
  let exc = null;         // open excursion
  let excursionNo = 0;
  for (let t = start; t <= endMinute; t += MIN) {
    const doorOpenSeconds = doorList.reduce((sum, d) => {
      const from = Math.max(d.open, t - MIN);
      const to = Math.min(d.open + d.seconds * 1000, t);
      return sum + Math.max(0, to - from) / 1000;
    }, 0);
    const powerOff = powerCuts.some((p) => t > p.from && t <= p.to);
    const fault = t > thermostatFault.from && t <= thermostatFault.to;

    offset += 0.6 * (doorOpenSeconds / 60);
    if (powerOff) offset += 0.05;
    else if (fault) offset += (-3.9 - offset) * 0.25;  // cools far too much
    else if (doorOpenSeconds < 30) offset *= Math.exp(-1 / 8);  // compressor brings it back (not while the door is open)

    const cycle = 4.8 + 0.9 * Math.sin((2 * Math.PI * (t / MIN)) / 40);
    const temp = round(cycle + offset + (rand() - 0.5) * 0.1, 2);
    const hour = ((t + KIGALI_OFFSET_MS) % DAY) / 3600000;
    const ambient = round(21 + 4 * Math.sin((2 * Math.PI * (hour - 9)) / 24) + (rand() - 0.5) * 0.4, 1);
    const humidity = round(68 - 10 * Math.sin((2 * Math.PI * (hour - 9)) / 24) + (rand() - 0.5) * 2, 1);

    // Excursion state machine (raw limits for the timer, hysteresis to close)
    const direction = temp > THRESHOLDS.maxC ? 'HIGH' : temp < THRESHOLDS.minC ? 'LOW' : null;
    if (exc && direction) {
      exc.outOfRangeSeconds += 60;
      total += 60;
    }
    if (direction && !exc) {
      excursionNo += 1;
      exc = { id: `seed-exc-${seed}-${excursionNo}`, direction, start: t, minTemp: temp, maxTemp: temp,
        outOfRangeSeconds: 0, confirmed: false };
    }
    if (exc) {
      exc.minTemp = Math.min(exc.minTemp, temp);
      exc.maxTemp = Math.max(exc.maxTemp, temp);
      if (!exc.confirmed && direction && t - exc.start >= THRESHOLDS.confirmDelayS * 1000) {
        exc.confirmed = true;
        event(t, `OUT_OF_RANGE_${exc.direction}`, { temp, limit: exc.direction === 'HIGH' ? 8 : 2, since: exc.start,
          excursionId: exc.id, outOfRangeSeconds: total });
        event(t + 3 * MIN, 'ALARM_ACKNOWLEDGED', { by: 'samuel@dashboard', alarms: [`TEMP_${exc.direction}`] });
      } else if (temp >= THRESHOLDS.minC + 0.3 && temp <= THRESHOLDS.maxC - 0.3) {
        event(t, 'BACK_IN_RANGE', { excursionId: exc.id, id: exc.id, direction: exc.direction, start: exc.start, end: t,
          durationS: (t - exc.start) / 1000, outOfRangeSeconds: exc.outOfRangeSeconds, offlineGapS: 0,
          offlineGapUnknown: false, minTemp: exc.minTemp, maxTemp: exc.maxTemp, confirmed: exc.confirmed });
        exc = null;
      }
    }

    const doorNow = doorList.some((d) => t >= d.open && t < d.open + d.seconds * 1000);
    const doorAlarm = doorList.some((d) => t >= d.open + THRESHOLDS.doorLimitS * 1000 && t < d.open + d.seconds * 1000);
    const activeAlarms = [];
    if (exc?.confirmed) activeAlarms.push(`TEMP_${exc.direction}`);
    if (doorAlarm) activeAlarms.push('DOOR_OPEN');
    if (powerOff) activeAlarms.push('POWER_LOST');
    const status = activeAlarms.length ? 'ALARM' : (exc || doorNow ? 'WARNING' : 'OK');

    messages.push({ kind: 'telemetry', ts: t, msg: {
      ts: t, internalTemp: temp, ambientTemp: ambient, humidity, doorOpen: doorNow, mainsPower: !powerOff,
      status, outOfRangeSeconds: total, activeAlarms, thresholds: THRESHOLDS, timeSynced: true,
    } });
  }

  messages.sort((a, b) => a.ts - b.ts || (a.kind === 'telemetry' ? -1 : 1));
  return { start, end: endMinute, thresholds: THRESHOLDS, messages: messages.filter((m) => m.ts >= start && m.ts <= endMinute) };
}
