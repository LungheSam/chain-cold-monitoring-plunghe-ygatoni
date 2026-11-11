// Excursion records: what stock may be affected. CSV export for the pharmacist / report.
import { useState } from 'react';
import { useData, useSubscription } from '../context.jsx';
import { UNIT_ID } from '../config.js';
import { excursionStats, excursionsToCsv } from '../lib/analytics.js';
import { formatDateTime, formatDuration, formatTemp } from '../lib/format.js';

const CAUSE = { door: 'door open', power: 'power cut', unknown: 'unknown' };

function downloadCsv(rows) {
  const blob = new Blob([excursionsToCsv(rows)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${UNIT_ID}-excursions-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Excursions() {
  const { data } = useData();
  const excursions = useSubscription((cb) => data.subscribeExcursions(UNIT_ID, cb), [data]);
  const [showBlips, setShowBlips] = useState(false);

  if (!excursions) return <p className="muted">Loading…</p>;
  const rows = excursions.filter((e) => showBlips || e.confirmed);
  const stats = excursionStats(excursions, { confirmedOnly: !showBlips });

  return (
    <>
      <div className="toolbar">
        <h1 className="grow" style={{ margin: 0 }}>Excursions</h1>
        <label className="checkbox">
          <input type="checkbox" checked={showBlips} onChange={(e) => setShowBlips(e.target.checked)} />
          show short blips (not confirmed)
        </label>
        <button type="button" className="secondary" onClick={() => downloadCsv(rows)} disabled={!rows.length}>Export CSV</button>
      </div>
      <p className="muted">
        Each time the internal temperature left the safe range. Use start, end and the min/max to decide
        which vaccines need checking. {stats.count} excursion(s), {formatDuration(stats.totalOutOfRangeS)} out of range in total.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Start</th><th>End</th><th>Duration</th><th>Out of range</th><th>Type</th><th>Min</th><th>Max</th><th>Likely cause</th></tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan="8" className="muted">No excursions.</td></tr>}
            {rows.map((e) => (
              <tr key={e.id}>
                <td>{formatDateTime(e.start)}</td>
                <td>{e.end ? formatDateTime(e.end) : <span className="pill alarm">ongoing</span>}</td>
                <td>{e.end ? formatDuration(e.durationS) : '–'}</td>
                <td>
                  {formatDuration(e.outOfRangeSeconds)}
                  {e.offlineGapS > 0 && <span className="muted"> + {formatDuration(e.offlineGapS)} while off</span>}
                  {e.offlineGapUnknown && <span className="muted"> + unknown time while off</span>}
                </td>
                <td>
                  <span className={`pill ${e.confirmed ? 'alarm' : 'warn'}`}>{e.direction === 'HIGH' ? 'too warm' : 'too cold'}</span>
                  {!e.confirmed && <span className="muted"> blip</span>}
                </td>
                <td>{formatTemp(e.minTemp)}</td>
                <td>{formatTemp(e.maxTemp)}</td>
                <td>{CAUSE[e.causeGuess] || '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
