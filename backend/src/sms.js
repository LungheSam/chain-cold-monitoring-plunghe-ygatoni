// SMS alerts.
//
// Rules (from the project brief):
// - Alert on OUT_OF_RANGE_HIGH/LOW, DOOR_OPEN_TOO_LONG, POWER_LOST, SENSOR_FAULT, and on the unit
//   being offline for more than 2 minutes.
// - A follow-up when the problem clears, with how long it lasted (only if the alert was sent).
// - De-duplication: at most one alert SMS per event type per unit per 15 minutes.
// - An event that arrives late (buffered on the node while offline, > 5 min old) is marked
//   "(delayed)". It is held a few seconds first: if the "cleared" event arrives in the same batch,
//   neither SMS is sent (docs/decisions.md D12).
// Phone numbers come from the `contacts` collection, never from the code.
import { clockTime, duration } from './time.js';

export const ALERT_TYPES = ['OUT_OF_RANGE_HIGH', 'OUT_OF_RANGE_LOW', 'DOOR_OPEN_TOO_LONG', 'POWER_LOST', 'SENSOR_FAULT', 'OFFLINE'];
const DEDUP_MS = 15 * 60 * 1000;
const HOLD_DELAYED_MS = 5000;

// A "problem" is what an alert opens and a clear closes. Sensor faults are per sensor.
function problemKey(event) {
  const d = event.details || {};
  switch (event.type) {
    case 'SENSOR_FAULT':
    case 'SENSOR_RESTORED':
      return `SENSOR_FAULT:${d.sensor}`;
    case 'BACK_IN_RANGE':
      return d.confirmed ? `OUT_OF_RANGE_${d.direction}` : null; // short blips never alerted
    case 'DOOR_CLOSED':
      return d.alarmed ? 'DOOR_OPEN_TOO_LONG' : null;
    case 'POWER_RESTORED':
      return 'POWER_LOST';
    case 'ONLINE':
      return 'OFFLINE';
    default:
      return ALERT_TYPES.includes(event.type) ? event.type : null;
  }
}

const SENSOR_NAMES = { ds18b20: 'internal temperature probe', dht22: 'ambient sensor' };

export function alertText(unitId, event) {
  const d = event.details || {};
  switch (event.type) {
    case 'OUT_OF_RANGE_HIGH':
    case 'OUT_OF_RANGE_LOW': {
      const word = event.type.endsWith('HIGH') ? 'above' : 'below';
      return `Problem at ${unitId}: temp ${d.temp}C ${word} ${d.limit}C since ${clockTime(d.since ?? event.ts)}. ` +
        `Out of range total ${duration(d.outOfRangeSeconds ?? 0)}.`;
    }
    case 'DOOR_OPEN_TOO_LONG':
      return `Problem at ${unitId}: door open for ${duration(d.openSeconds ?? 0)} (limit ${duration(d.limitS ?? 0)}).`;
    case 'POWER_LOST':
      return `Problem at ${unitId}: mains power lost at ${clockTime(event.ts)}. Unit running on battery.`;
    case 'SENSOR_FAULT':
      return `Problem at ${unitId}: ${SENSOR_NAMES[d.sensor] || d.sensor} fault (${d.reason}). Check the sensor.`;
    case 'OFFLINE':
      return `Problem at ${unitId}: unit offline since ${clockTime(event.ts)} (no data for 2 min).`;
    default:
      return `Problem at ${unitId}: ${event.type}`;
  }
}

export function clearText(unitId, event, offlineMs) {
  const d = event.details || {};
  switch (event.type) {
    case 'BACK_IN_RANGE': {
      const peak = d.direction === 'HIGH' ? `max ${d.maxTemp}C` : `min ${d.minTemp}C`;
      return `OK ${unitId}: temp back in range at ${clockTime(event.ts)}. Excursion lasted ${duration(d.durationS ?? 0)} (${peak}).`;
    }
    case 'DOOR_CLOSED':
      return `OK ${unitId}: door closed after ${duration(d.openSeconds ?? 0)}.`;
    case 'POWER_RESTORED':
      return `OK ${unitId}: mains power restored after ${duration(d.durationS ?? 0)}.`;
    case 'SENSOR_RESTORED':
      return `OK ${unitId}: ${SENSOR_NAMES[d.sensor] || d.sensor} working again.`;
    case 'ONLINE':
      return `OK ${unitId}: unit back online after ${duration((offlineMs ?? 0) / 1000)}.`;
    default:
      return `OK ${unitId}: ${event.type}`;
  }
}

export function createSmsNotifier({ store, sender, now = Date.now, log = console, holdMs = HOLD_DELAYED_MS }) {
  const held = new Map(); // `${unitId}|${problem}` -> timer of a delayed alert waiting to be sent

  async function send(unitId, type, kind, message) {
    const contacts = await store.getContactsForUnit(unitId);
    const to = contacts.map((c) => c.phone);
    if (to.length === 0) {
      log.warn(`SMS not sent (no active contacts for ${unitId}): ${message}`);
      return;
    }
    let providerStatus;
    try {
      providerStatus = await sender.send(to, message);
      // providerStatus is Africa's Talking's answer per phone, e.g. "+2507...:Success".
      // Phone numbers are masked in the log (last 3 digits kept).
      const shown = String(providerStatus).replace(/\+?\d{6,}(\d{3})/g, '***$1');
      log.info(`SMS ${kind} ${type} to ${to.length} contact(s) [${shown}]: ${message}`);
    } catch (err) {
      providerStatus = `error: ${err.message}`;
      log.error(`SMS failed: ${err.message}`);
    }
    await store.addSmsLog({ ts: now(), unitId, type, kind, to, message, providerStatus: String(providerStatus) });
  }

  async function sendAlert(unitId, event, delayed) {
    const state = await store.getSmsState(unitId);
    const last = state.lastAlertAt[event.type];
    if (last && now() - last < DEDUP_MS) {
      log.info(`SMS ${event.type} for ${unitId} suppressed (one per 15 min)`);
      return;
    }
    const text = (delayed ? '(delayed) ' : '') + alertText(unitId, event);
    await send(unitId, event.type, 'alert', text);
    state.lastAlertAt[event.type] = now();
    state.open[problemKey(event)] = { sentAt: now(), ts: event.ts };
    await store.setSmsState(unitId, state);
  }

  async function sendClear(unitId, event, offlineMs) {
    const key = problemKey(event);
    if (!key) return;
    const heldId = `${unitId}|${key}`;
    if (held.has(heldId)) {
      // The alert was still waiting (delayed batch) and the problem is already over: send nothing
      clearTimeout(held.get(heldId));
      held.delete(heldId);
      log.info(`SMS ${key} for ${unitId} skipped: problem already cleared`);
      return;
    }
    const state = await store.getSmsState(unitId);
    if (!state.open[key]) return; // no alert was sent for this problem, so no follow-up
    delete state.open[key];
    await store.setSmsState(unitId, state);
    await send(unitId, event.type, 'clear', clearText(unitId, event, offlineMs));
  }

  return {
    // Called for every new event from the node. `delayed` = the event is more than 5 min old.
    async onEvent(unitId, event, { delayed = false } = {}) {
      if (ALERT_TYPES.includes(event.type)) {
        if (!delayed) return sendAlert(unitId, event, false);
        const heldId = `${unitId}|${problemKey(event)}`;
        const timer = setTimeout(() => {
          held.delete(heldId);
          sendAlert(unitId, event, true).catch((err) => log.error(`SMS failed: ${err.message}`));
        }, holdMs);
        timer.unref?.();
        held.set(heldId, timer);
        return;
      }
      return sendClear(unitId, event);
    },

    async onUnitOffline(unitId, sinceMs) {
      return sendAlert(unitId, { type: 'OFFLINE', ts: sinceMs, details: {} }, false);
    },

    async onUnitOnline(unitId, offlineMs) {
      return sendClear(unitId, { type: 'ONLINE', ts: now(), details: {} }, offlineMs);
    },
  };
}

// Africa's Talking SMS through their REST API (one HTTP POST; no SDK needed).
// Sandbox: username "sandbox", messages appear in the simulator at africastalking.com.
export function createAfricasTalkingSender({ username, apiKey, senderId = '', fetchFn = fetch }) {
  const url = username === 'sandbox'
    ? 'https://api.sandbox.africastalking.com/version1/messaging'
    : 'https://api.africastalking.com/version1/messaging';
  return {
    async send(to, message) {
      const body = new URLSearchParams({ username, to: to.join(','), message });
      if (senderId) body.set('from', senderId); // empty = Africa's Talking default sender ID
      const res = await fetchFn(url, {
        method: 'POST',
        headers: { apiKey, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      const text = await res.text();
      if (!res.ok) throw new Error(`Africa's Talking HTTP ${res.status}: ${text.slice(0, 200)}`);
      const data = JSON.parse(text);
      const recipients = data.SMSMessageData?.Recipients || [];
      return recipients.map((r) => `${r.number}:${r.status}`).join(', ') || data.SMSMessageData?.Message || 'sent';
    },
  };
}

// Used when no Africa's Talking API key is set: the SMS is only printed.
export function createConsoleSender(log = console) {
  return {
    async send(to, message) {
      log.info(`[console SMS to ${to.join(', ')}] ${message}`);
      return 'console';
    },
  };
}
