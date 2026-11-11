// Temperature history: internal and ambient lines, the safe band shaded green, door-open periods
// (blue) and power cuts (red) as stripes. 1 h and 24 h use raw readings (1 per minute); 7 days
// uses hourly summaries to keep Firestore reads low (168 instead of 10 080).
import { useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { useData, useUnit } from '../context.jsx';
import { UNIT_ID } from '../config.js';
import { COLORS, shadingPlugin } from '../components/charts.js';
import { hourlyPoints, periodsFromEvents } from '../lib/analytics.js';
import { formatDateTime, formatDay, formatTime } from '../lib/format.js';

const RANGES = { '1h': 3600000, '24h': 86400000, '7d': 7 * 86400000 };

export default function History() {
  const { data } = useData();
  const unit = useUnit();
  const [range, setRange] = useState('24h');
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setState((s) => ({ ...s, loading: true }));
      const to = Date.now();
      const from = to - RANGES[range];
      try {
        const [rows, events] = await Promise.all([
          range === '7d' ? data.getSummaries(UNIT_ID, 'hourly', from - 3600000, to) : data.getReadings(UNIT_ID, from, to),
          data.getEvents(UNIT_ID, from - 2 * 3600000, to),
        ]);
        const points = range === '7d'
          ? hourlyPoints(rows)
          : rows.map((r) => ({ x: r.ts, internal: r.internalTemp, ambient: r.ambientTemp }));
        if (!cancelled) setState({ loading: false, from, to, points, events });
      } catch (err) {
        if (!cancelled) setState({ loading: false, error: err.message });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [data, range]);

  const t = unit?.thresholds || { minC: 2, maxC: 8 };
  const periods = state.points
    ? periodsFromEvents(state.events, state.from, state.to, unit || {})
    : { door: [], power: [] };
  const tickLabel = range === '7d' ? formatDay : formatTime;

  const points = state.points || [];
  const datasets = [
    {
      label: 'Internal (°C)', data: points.map((p) => ({ x: p.x, y: p.internal })), yAxisID: 'y',
      borderColor: COLORS.internal, backgroundColor: COLORS.internal, borderWidth: 2, pointRadius: 0, tension: 0.2, spanGaps: false,
    },
    {
      label: 'Ambient (°C, right axis)', data: points.map((p) => ({ x: p.x, y: p.ambient })), yAxisID: 'y2',
      borderColor: COLORS.ambient, backgroundColor: COLORS.ambient, borderWidth: 1.5, pointRadius: 0, tension: 0.2,
    },
  ];
  if (range === '7d') {
    // Hourly averages hide short peaks: also show each hour's min-max as a shaded area
    datasets.push(
      {
        label: 'Internal hourly min–max', data: points.map((p) => ({ x: p.x, y: p.max })), yAxisID: 'y',
        borderWidth: 0, pointRadius: 0, backgroundColor: 'rgba(11, 83, 148, 0.18)', fill: '+1',
      },
      { label: 'min', data: points.map((p) => ({ x: p.x, y: p.min })), yAxisID: 'y', borderWidth: 0, pointRadius: 0 },
    );
  }
  const chartData = { datasets };
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    parsing: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: { type: 'linear', min: state.from, max: state.to, ticks: { maxTicksLimit: 8, callback: (v) => tickLabel(v) } },
      y: { title: { display: true, text: 'internal °C' }, suggestedMin: 0, suggestedMax: 12 },
      y2: { position: 'right', title: { display: true, text: 'ambient °C' }, suggestedMin: 10, suggestedMax: 35, grid: { drawOnChartArea: false } },
    },
    plugins: {
      legend: { position: 'bottom', labels: { filter: (item) => item.text !== 'min' } },
      tooltip: {
        filter: (item) => item.dataset.label !== 'min',
        callbacks: {
          title: (items) => formatDateTime(items[0].parsed.x),
          label: (item) => `${item.dataset.label}: ${item.parsed.y?.toFixed(2)}`,
        },
      },
      shading: {
        band: { min: t.minC, max: t.maxC },
        periods: [
          ...periods.door.map((p) => ({ ...p, color: COLORS.door })),
          ...periods.power.map((p) => ({ ...p, color: COLORS.power })),
        ],
      },
    },
  };

  return (
    <>
      <div className="toolbar">
        <h1 className="grow" style={{ margin: 0 }}>Temperature history</h1>
        <div className="segmented">
          {Object.keys(RANGES).map((r) => (
            <button type="button" key={r} className={r === range ? 'active' : ''} onClick={() => setRange(r)}>
              {r === '1h' ? '1 hour' : r === '24h' ? '24 hours' : '7 days'}
            </button>
          ))}
        </div>
      </div>
      <div className="panel">
        {state.error && <p className="error">Could not load: {state.error}</p>}
        {state.loading && <p className="muted">Loading…</p>}
        {!state.loading && state.points?.length === 0 && <p className="muted">No data in this period.</p>}
        <div className="chart-box">
          {state.points && <Line data={chartData} options={options} plugins={[shadingPlugin]} />}
        </div>
        <div className="legend-note">
          <span><span className="swatch" style={{ background: COLORS.band, border: `1px dashed ${COLORS.bandEdge}` }} />safe range {t.minC}–{t.maxC} °C</span>
          <span><span className="swatch" style={{ background: COLORS.door }} />door open ({periods.door.length})</span>
          <span><span className="swatch" style={{ background: COLORS.power }} />power cut ({periods.power.length})</span>
          {range === '7d' && <span>7 days: hourly averages</span>}
        </div>
      </div>
    </>
  );
}
