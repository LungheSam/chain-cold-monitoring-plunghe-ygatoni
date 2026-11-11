// Chart.js setup shared by all charts.
import {
  BarElement, CategoryScale, Chart, Filler, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js';

Chart.register(LinearScale, CategoryScale, PointElement, LineElement, BarElement, Filler, Tooltip, Legend);

export const COLORS = {
  internal: '#0b5394',
  ambient: '#e69138',
  band: 'rgba(52, 168, 83, 0.12)',
  bandEdge: 'rgba(52, 168, 83, 0.6)',
  door: 'rgba(66, 133, 244, 0.18)',
  power: 'rgba(217, 48, 37, 0.16)',
  ok: '#1e8e3e',
  bad: '#d93025',
  grey: '#80868b',
};

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
