// Chart.js setup shared by all charts.
import {
  BarElement, CategoryScale, Chart, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js';

Chart.register(LinearScale, CategoryScale, PointElement, LineElement, BarElement, Filler, Tooltip, Legend);

// Colours for each theme. The charts read COLORS when they draw; applyChartTheme() swaps them and
// the pages redraw their charts (they use the theme as a React key).
const PALETTES = {
  light: {
    internal: '#0b5394', internalFill: 'rgba(11, 83, 148, 0.16)', ambient: '#e8890c',
    band: 'rgba(22, 163, 74, 0.10)', bandEdge: 'rgba(22, 163, 74, 0.55)',
    door: 'rgba(59, 130, 246, 0.16)', power: 'rgba(220, 38, 38, 0.14)',
    ok: '#16a34a', bad: '#dc2626', grey: '#64748b',
    text: '#475569', grid: 'rgba(148, 163, 184, 0.25)', tooltip: '#0f172a',
  },
  dark: {
    internal: '#38bdf8', internalFill: 'rgba(56, 189, 248, 0.18)', ambient: '#fbbf24',
    band: 'rgba(34, 197, 94, 0.12)', bandEdge: 'rgba(74, 222, 128, 0.6)',
    door: 'rgba(96, 165, 250, 0.20)', power: 'rgba(248, 113, 113, 0.20)',
    ok: '#22c55e', bad: '#f87171', grey: '#94a3b8',
    text: '#94a3b8', grid: 'rgba(148, 163, 184, 0.14)', tooltip: '#020617',
  },
};

export const COLORS = { ...PALETTES.light };

export function applyChartTheme(theme) {
  Object.assign(COLORS, PALETTES[theme] || PALETTES.light);
  Chart.defaults.font.family = "'Montserrat', system-ui, sans-serif";
  Chart.defaults.color = COLORS.text;
  Chart.defaults.borderColor = COLORS.grid;
  Chart.defaults.plugins.tooltip.backgroundColor = COLORS.tooltip;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.titleFont = { weight: '600' };
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.elements.bar.borderRadius = 6;
}

// Plugin that draws, behind the lines:
//  - the safe band (options.plugins.shading.band = {min, max}) in green
//  - time periods (options.plugins.shading.periods = [{from, to, color}]) as full-height stripes
export const shadingPlugin = {
  id: 'shading',
  beforeDatasetsDraw(chart, args, options) {
    const { ctx, chartArea: area, scales } = chart;
    if (!area || !scales.x || !scales.y) return;
    ctx.save();
    ctx.beginPath();
    ctx.rect(area.left, area.top, area.right - area.left, area.bottom - area.top);
    ctx.clip();

    for (const p of options.periods || []) {
      const x1 = scales.x.getPixelForValue(p.from);
      const x2 = scales.x.getPixelForValue(p.to);
      ctx.fillStyle = p.color;
      ctx.fillRect(x1, area.top, Math.max(2, x2 - x1), area.bottom - area.top);
    }

    if (options.band) {
      const yTop = scales.y.getPixelForValue(options.band.max);
      const yBottom = scales.y.getPixelForValue(options.band.min);
      ctx.fillStyle = COLORS.band;
      ctx.fillRect(area.left, yTop, area.right - area.left, yBottom - yTop);
      ctx.strokeStyle = COLORS.bandEdge;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(area.left, yTop);
      ctx.lineTo(area.right, yTop);
      ctx.moveTo(area.left, yBottom);
      ctx.lineTo(area.right, yBottom);
      ctx.stroke();
    }
    ctx.restore();
  },
};
