// All events from the node, and the access log (keypad PIN and QR unlocks).
import { useState } from 'react';
import { useData, useSubscription } from '../context.jsx';
import { UNIT_ID } from '../config.js';
import { accessDetails, eventDetails, eventLabel, formatDateTime } from '../lib/format.js';

const GROUPS = {
  all: null,
  temperature: ['OUT_OF_RANGE_HIGH', 'OUT_OF_RANGE_LOW', 'BACK_IN_RANGE'],
  door: ['DOOR_OPEN_TOO_LONG', 'DOOR_CLOSED'],
  power: ['POWER_LOST', 'POWER_RESTORED'],
  sensor: ['SENSOR_FAULT', 'SENSOR_RESTORED'],
  alarms: ['ALARM_ACKNOWLEDGED'],
  access: ['ACCESS_GRANTED', 'ACCESS_DENIED'],
};
const BAD = ['OUT_OF_RANGE_HIGH', 'OUT_OF_RANGE_LOW', 'DOOR_OPEN_TOO_LONG', 'POWER_LOST', 'SENSOR_FAULT', 'ACCESS_DENIED'];

export default function EventsLog() {
  const { data } = useData();
  const events = useSubscription((cb) => data.subscribeEvents(UNIT_ID, 300, cb), [data]);
  const access = useSubscription((cb) => data.subscribeAccess(UNIT_ID, 100, cb), [data]);
  const [group, setGroup] = useState('all');

  const shown = (events || []).filter((e) => !GROUPS[group] || GROUPS[group].includes(e.type));

  return (
    <>
      <div className="toolbar">
        <h1 className="grow" style={{ margin: 0 }}>Events</h1>
        <label style={{ margin: 0, minWidth: 180 }}>
          <select value={group} onChange={(e) => setGroup(e.target.value)} aria-label="Event type">
            {Object.keys(GROUPS).map((g) => <option key={g} value={g}>{g === 'all' ? 'All events' : g}</option>)}
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Event</th><th>Details</th></tr></thead>
          <tbody>
            {!events && <tr><td colSpan="3" className="muted">Loading…</td></tr>}
            {events && shown.length === 0 && <tr><td colSpan="3" className="muted">No events.</td></tr>}
            {shown.map((e) => (
              <tr key={e.id}>
                <td>{formatDateTime(e.ts)}</td>
                <td><span className={`pill ${BAD.includes(e.type) ? 'alarm' : 'ok'}`}>{eventLabel(e.type)}</span></td>
                <td className="wrap">{eventDetails(e)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Access log</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Result</th><th>Method</th><th>Who</th><th>Details</th></tr></thead>
          <tbody>
            {!access && <tr><td colSpan="5" className="muted">Loading…</td></tr>}
            {access?.length === 0 && <tr><td colSpan="5" className="muted">No door unlocks yet.</td></tr>}
            {(access || []).map((a) => (
              <tr key={a.id}>
                <td>{formatDateTime(a.ts)}</td>
                <td><span className={`pill ${a.result === 'GRANTED' ? 'ok' : 'alarm'}`}>{a.result.toLowerCase()}</span></td>
                <td>{a.method === 'qr' ? 'QR page' : a.method}</td>
                <td>{a.user || <span className="muted">–</span>}</td>
                <td className="wrap">{a.details?.reason ? accessDetails({ ...a.details, method: null, user: null }) : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
