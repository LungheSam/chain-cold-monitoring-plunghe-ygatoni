// High-level analytics from the daily summaries and the excursion records:
// % time in range per day, excursions, door openings, power cuts, min/max/mean and MKT.
import { useEffect, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { useData, useSubscription } from '../context.jsx';
import { UNIT_ID } from '../config.js';
import Card from '../components/Card.jsx';
import { COLORS } from '../components/charts.js';
import { combineSummaries, excursionStats, percentInRange } from '../lib/analytics.js';
import { formatDay, formatDuration, formatPercent, formatTemp } from '../lib/format.js';

const PERIODS = { 7: 'Last 7 days', 30: 'Last 30 days' };


const barOptions = (unit, max) => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (i) => `${i.parsed.y}${unit}` } } },
  scales: { y: { beginAtZero: true, max, ticks: { callback: (v) => `${v}${unit}` } } },
});

export default function Analytics() {
  const { data } = useData();
  const [days, setDays] = useState(7);
  const [daily, setDaily] = useState(null);
  const [error, setError] = useState('');
  const excursions = useSubscription((cb) => data.subscribeExcursions(UNIT_ID, cb), [data]);

  useEffect(() => {
    let cancelled = false;
    const to = Date.now();
    data.getSummaries(UNIT_ID, 'daily', to - days * 86400000, to)
      .then((rows) => !cancelled && setDaily(rows))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [data, days]);

  if (error) return <p className="error">Could not load: {error}</p>;
  if (!daily) return <p className="muted">Loading…</p>;

  const from = Date.now() - days * 86400000;
  const total = combineSummaries(daily);
  const exc = excursionStats(excursions || [], { from });
  const labels = daily.map((s) => formatDay(s.start));

  const inRangeChart = {
    labels,
    datasets: [{
      data: daily.map((s) => Number((percentInRange(s) ?? 0).toFixed(1))),
      backgroundColor: daily.map((s) => ((percentInRange(s) ?? 100) >= 99.9 ? COLORS.ok : COLORS.bad)),
    }],
  };
  const doorChart = { labels, datasets: [{ data: daily.map((s) => s.doorOpenings || 0), backgroundColor: COLORS.internal }] };

  return (
    <>
      <div className="toolbar">
        <h1 className="grow" style={{ margin: 0 }}>Analytics</h1>
        <div className="segmented">
          {Object.entries(PERIODS).map(([d, label]) => (
            <button type="button" key={d} className={Number(d) === days ? 'active' : ''} onClick={() => setDays(Number(d))}>{label}</button>
          ))}
        </div>
      </div>

      {daily.length === 0 && <p className="muted">No data in this period yet.</p>}

      <div className="cards">
        <Card label="Time in range" value={formatPercent(total.percentInRange)}
          tone={total.percentInRange != null && total.percentInRange < 99.9 ? 'bad' : 'good'}
          sub={`out of range ${formatDuration(total.secondsOutOfRange)}`} />
        <Card label="Excursions" value={exc.count} tone={exc.count ? 'bad' : 'good'}
          sub={`total ${formatDuration(exc.totalDurationS)}, longest ${formatDuration(exc.longestS)}`} />
        <Card label="Internal min / max" value={`${formatTemp(total.minTemp)}`} sub={`max ${formatTemp(total.maxTemp)}`} />
        <Card label="Mean / MKT" value={formatTemp(total.meanTemp)}
          sub={<>MKT {formatTemp(total.mkt)} <span title="Mean kinetic temperature: one temperature with the same total effect on vaccine stability as the real, varying temperatures. Warm periods weigh more than in a plain average.">ⓘ</span></>} />
        <Card label="Door openings" value={total.doorOpenings} sub={`longest ${formatDuration(total.longestDoorOpenS)}`} />
        <Card label="Power cuts" value={total.powerCuts} tone={total.powerCuts ? 'bad' : ''}
          sub={`total ${formatDuration(total.powerCutSeconds)}`} />
      </div>

      <div className="grid-2" style={{ marginTop: 16 }}>
        <div className="panel">
          <h2 style={{ marginTop: 0 }}>% time in range per day</h2>
          <div className="chart-box small"><Bar data={inRangeChart} options={barOptions(' %', 100)} /></div>
        </div>
        <div className="panel">
          <h2 style={{ marginTop: 0 }}>Door openings per day</h2>
          <div className="chart-box small"><Bar data={doorChart} options={barOptions('', undefined)} /></div>
        </div>
      </div>

      <h2>Per day</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Day</th><th>In range</th><th>Min</th><th>Mean</th><th>Max</th><th>MKT</th><th>Door openings</th><th>Longest</th><th>Power cuts</th></tr>
          </thead>
          <tbody>
            {[...daily].reverse().map((s) => {
              const day = combineSummaries([s]);
              return (
                <tr key={s.key}>
                  <td>{formatDay(s.start)}</td>
                  <td>{formatPercent(day.percentInRange)}</td>
                  <td>{formatTemp(day.minTemp)}</td>
                  <td>{formatTemp(day.meanTemp)}</td>
                  <td>{formatTemp(day.maxTemp)}</td>
                  <td>{formatTemp(day.mkt)}</td>
                  <td>{day.doorOpenings}</td>
                  <td>{formatDuration(day.longestDoorOpenS)}</td>
                  <td>{day.powerCuts ? `${day.powerCuts} (${formatDuration(day.powerCutSeconds)})` : 0}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
