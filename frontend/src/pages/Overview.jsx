import { useState } from 'react';
import { Link } from 'react-router';
import { useData, useNow, useSubscription, useUnit } from '../context.jsx';
import { UNIT_ID } from '../config.js';
import Card from '../components/Card.jsx';
import { eventDetails, eventLabel, formatDateTime, formatDuration, formatTemp } from '../lib/format.js';

const STATUS_TEXT = {
  OK: 'Everything is within limits.',
  WARNING: 'Something is not right yet (not confirmed as an alarm).',
  ALARM: 'Alarm: action needed.',
  OFFLINE: 'No data from the unit. The local alarm still works on the device.',
};

const ALARM_TEXT = {
  TEMP_HIGH: 'temperature too high', TEMP_LOW: 'temperature too low', DOOR_OPEN: 'door open too long',
  POWER_LOST: 'mains power lost', SENSOR_INTERNAL: 'temperature probe fault',
};


export default function Overview() {
  const { data, role } = useData();
  const unit = useUnit();
  const now = useNow();
  const events = useSubscription((cb) => data.subscribeEvents(UNIT_ID, 8, cb), [data]);
  const [ackState, setAckState] = useState(null);

  if (unit === undefined) return <p className="muted">Loading…</p>;
  if (unit === null) return <p>No data yet for {UNIT_ID}. Start the node (or seed the database).</p>;

  const status = unit.status || 'OFFLINE';
  const t = unit.thresholds || { minC: 2, maxC: 8 };
  const lastUpdate = unit.lastTelemetryTs || unit.lastSeen;
  const agoS = lastUpdate ? Math.max(0, Math.round((now - lastUpdate) / 1000)) : null;
  const tempBad = unit.internalTemp == null || unit.internalTemp > t.maxC || unit.internalTemp < t.minC;
  const alarms = unit.activeAlarms || [];

  async function acknowledge() {
    setAckState({ busy: true });
    const res = await data.api.action(UNIT_ID, 'acknowledgeAlarm');
    setAckState(res.ok ? { ok: 'Buzzer silenced.' } : { error: res.data?.error || `failed (${res.status})` });
  }

  return (
    <>
      <div className={`banner ${status}`}>
        <div className="status">{status}</div>
        <div className="detail">
          <div>{STATUS_TEXT[status]}</div>
          {alarms.length > 0 && <div><strong>Active: {alarms.map((a) => ALARM_TEXT[a] || a).join(', ')}</strong></div>}
          <div style={{ opacity: 0.9, fontSize: '0.9rem' }}>
            Last updated {agoS == null ? 'never' : `${formatDuration(agoS)} ago`}
          </div>
        </div>
        {role === 'supervisor' && status === 'ALARM' && (
          <button type="button" onClick={acknowledge} disabled={ackState?.busy}>
            {ackState?.busy ? 'Sending…' : 'Acknowledge alarm'}
          </button>
        )}
      </div>
      {ackState?.ok && <p className="success">{ackState.ok}</p>}
      {ackState?.error && <p className="error">Acknowledge failed: {ackState.error}</p>}

      <div className="cards">
        <Card label="Internal temperature" value={formatTemp(unit.internalTemp)} tone={tempBad ? 'bad' : 'good'}
          sub={`Safe range ${t.minC} to ${t.maxC} °C`} />
        <Card label="Ambient" value={formatTemp(unit.ambientTemp)}
          sub={unit.humidity == null ? 'humidity –' : `humidity ${unit.humidity.toFixed(0)} %`} />
        <Card label="Door" value={unit.doorOpen ? 'Open' : 'Closed'} tone={unit.doorOpen ? 'bad' : ''}
          sub={`alarm after ${formatDuration(t.doorLimitS)}`} />
        <Card label="Mains power" value={unit.mainsPower === false ? 'Lost' : 'On'} tone={unit.mainsPower === false ? 'bad' : ''}
          sub={unit.mainsPower === false ? 'running on battery' : '12 V supply present'} />
        <Card label="Time out of range" value={formatDuration(unit.outOfRangeSeconds || 0)}
          sub={<Link to="/excursions">cumulative · see excursions</Link>} />
      </div>

      <h2>Latest events</h2>
      <div className="panel">
        {!events && <p className="muted">Loading…</p>}
        {events?.length === 0 && <p className="muted">No events yet.</p>}
        <ul className="event-list">
          {(events || []).map((e) => (
            <li key={e.id}>
              <span className="time">{formatDateTime(e.ts)}</span>
              <strong>{eventLabel(e.type)}</strong>
              <span className="muted">{eventDetails(e)}</span>
            </li>
          ))}
        </ul>
        <p><Link to="/events">All events and access log →</Link></p>
      </div>
    </>
  );
}
