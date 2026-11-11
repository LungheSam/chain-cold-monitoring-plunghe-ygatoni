// /unlock/:unitId: the page the QR code on the fridge opens. Made for a phone: sign in (once), see
// the unit, press one big button. The back end checks the token and role, sends `unlockDoor` to the
// node, and the node opens the lock for 5 s and logs ACCESS_GRANTED with the user's email.
// The QR code holds no secret: it is only this link. Security comes from the sign-in and the role.
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router';
import { useData, useSubscription, useUnit } from '../context.jsx';
import { formatDateTime, formatTemp } from '../lib/format.js';

const OPEN_S = 5;
const WAIT_S = 10;   // 5 s open + 5 s rest for the solenoid (coldchain/access.py)

const ERRORS = {
  403: 'Only supervisors can open the door from a phone. Use your keypad PIN.',
  404: 'This unit does not exist. Check the QR code.',
  409: 'The unit is offline, so it cannot be opened from here. Use the keypad.',
  504: 'The unit did not answer in time. Try again, or use the keypad.',
};

export default function Unlock() {
  const { unitId } = useParams();
  const { data, user, role } = useData();
  const unit = useUnit(unitId);
  const access = useSubscription((cb) => data.subscribeAccess(unitId, 5, cb), [data, unitId]);
  const [result, setResult] = useState(null);   // {ok, text}
  const [busy, setBusy] = useState(false);
  const [countdown, setCountdown] = useState(0);

  // Count down after an unlock so nobody presses again while the lock is open or resting
  useEffect(() => {
    if (countdown <= 0) return undefined;
    const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  async function unlock() {
    setBusy(true);
    setResult(null);
    const res = await data.api.action(unitId, 'unlockDoor', {});
    setBusy(false);
    if (res.ok) {
      setResult({ ok: true, text: `Unlocked. Pull the door open within ${OPEN_S} seconds.` });
      setCountdown(WAIT_S);
    } else {
      setResult({ ok: false, text: ERRORS[res.status] || res.data?.error || `Failed (${res.status}).` });
    }
  }

  const offline = !unit || unit.status === 'OFFLINE';
  const canUnlock = role === 'supervisor' && !offline && !busy && countdown === 0;

  return (
    <div className="unlock-page">
      <h1>❄ {unitId}</h1>

      {unit === undefined && <p className="muted">Loading…</p>}
      {unit === null && <p className="error">No unit called “{unitId}”. Check the QR code.</p>}
      {unit && (
        <div className={`banner ${unit.status || 'OFFLINE'}`}>
          <div className="status">{unit.status || 'OFFLINE'}</div>
          <div className="detail">
            Inside {formatTemp(unit.internalTemp)} · door {unit.doorOpen ? 'open' : 'closed'}
          </div>
        </div>
      )}

      {role !== 'supervisor' && <p className="pill warn">{ERRORS[403]}</p>}
      {unit && offline && <p className="pill warn">{ERRORS[409]}</p>}

      <button type="button" className="unlock-button" onClick={unlock} disabled={!canUnlock}>
        {busy ? 'Opening…' : countdown > 0 ? `Wait ${countdown} s` : '🔓 Unlock door'}
      </button>
      {result && <p className={result.ok ? 'success' : 'error'}><strong>{result.text}</strong></p>}
      <p className="muted small-print">
        Signed in as {user?.email}. Every unlock is logged with your name.
      </p>

      <h2>Last door access</h2>
      <ul className="event-list panel">
        {!access && <li className="muted">Loading…</li>}
        {access?.length === 0 && <li className="muted">None yet.</li>}
        {(access || []).map((a) => (
          <li key={a.id}>
            <span className="time">{formatDateTime(a.ts)}</span>
            <span className={`pill ${a.result === 'GRANTED' ? 'ok' : 'alarm'}`}>{a.result.toLowerCase()}</span>
            <span>{a.method === 'qr' ? 'QR' : a.method}{a.user ? `, ${a.user}` : ''}</span>
          </li>
        ))}
      </ul>

      <p><Link to="/">Open the dashboard</Link></p>
    </div>
  );
}
