// Pure calculations for the History, Analytics and Excursions pages (unit-tested, no React).
import { formatCsvTime } from './format.js';

// ---------------------------------------------------------------- summaries

export function percentInRange(s) {
  const total = (s.secondsInRange || 0) + (s.secondsOutOfRange || 0);
  return total ? (100 * s.secondsInRange) / total : null;
}

// Mean kinetic temperature (MKT): the single temperature that would cause the same total
// degradation as the varying temperatures actually seen. Each reading T (kelvin) adds
// exp(-dH/(R*T)) to sumArrhenius; then MKT = (dH/R) / -ln(sumArrhenius / n) - 273.15 (in C).
// dH/R = 10 000 K, from the standard activation energy dH = 83.144 kJ/mol (R = 8.3144 J/mol/K).
// Warm periods weigh more than in a plain mean, because degradation speeds up with temperature.
export const DH_OVER_R = 10000;

export function meanKineticTemperature(sumArrhenius, count) {
  if (!count) return null;
  return DH_OVER_R / -Math.log(sumArrhenius / count) - 273.15;
}

// Add several hourly/daily summaries together (for "the last 7 days" figures)
export function combineSummaries(list) {
  const total = {
    count: 0, sumTemp: 0, sumArrhenius: 0, minTemp: null, maxTemp: null,
    secondsInRange: 0, secondsOutOfRange: 0, doorOpenings: 0, doorOpenSeconds: 0,
    longestDoorOpenS: 0, powerCuts: 0, powerCutSeconds: 0,
  };
  for (const s of list) {
    for (const k of ['count', 'sumTemp', 'sumArrhenius', 'secondsInRange', 'secondsOutOfRange',
      'doorOpenings', 'doorOpenSeconds', 'powerCuts', 'powerCutSeconds']) total[k] += s[k] || 0;
    if (s.minTemp != null) total.minTemp = total.minTemp == null ? s.minTemp : Math.min(total.minTemp, s.minTemp);
    if (s.maxTemp != null) total.maxTemp = total.maxTemp == null ? s.maxTemp : Math.max(total.maxTemp, s.maxTemp);
    total.longestDoorOpenS = Math.max(total.longestDoorOpenS, s.longestDoorOpenS || 0);
  }
  total.meanTemp = total.count ? total.sumTemp / total.count : null;
  total.mkt = meanKineticTemperature(total.sumArrhenius, total.count);
  total.percentInRange = percentInRange(total);
  return total;
}

// Hourly summaries -> chart points {x: ms, internal, ambient, min, max}
export function hourlyPoints(hourly) {
  return hourly
    .filter((s) => s.count > 0)
    .map((s) => ({
      x: s.start + 30 * 60000, // middle of the hour
      internal: s.sumTemp / s.count,
      ambient: s.countAmbient ? s.sumAmbient / s.countAmbient : null,
      min: s.minTemp,
      max: s.maxTemp,
    }));
}

// ---------------------------------------------------------------- excursions

export function excursionStats(excursions, { from = -Infinity, to = Infinity, confirmedOnly = true } = {}) {
  const list = excursions.filter((e) => e.start >= from && e.start <= to && (!confirmedOnly || e.confirmed));
  return {
    count: list.length,
    totalDurationS: list.reduce((sum, e) => sum + (e.durationS || 0), 0),
    totalOutOfRangeS: list.reduce((sum, e) => sum + (e.outOfRangeSeconds || 0) + (e.offlineGapS || 0), 0),
    longestS: list.reduce((max, e) => Math.max(max, e.durationS || 0), 0),
  };
}

function csvCell(value) {
  const text = value == null ? '' : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

// CSV for identifying affected stock. Times in Kigali local time.
export function excursionsToCsv(excursions) {
  const header = ['start', 'end', 'duration_s', 'out_of_range_s', 'offline_gap_s', 'direction', 'min_temp_c',
    'max_temp_c', 'confirmed', 'cause_guess', 'excursion_id'];
  const rows = excursions.map((e) => [
    formatCsvTime(e.start), e.end ? formatCsvTime(e.end) : 'ongoing', e.durationS ?? '', e.outOfRangeSeconds ?? '',
    e.offlineGapUnknown ? 'unknown' : (e.offlineGapS ?? 0), e.direction, e.minTemp ?? '', e.maxTemp ?? '',
    e.confirmed ? 'yes' : 'no', e.causeGuess ?? '', e.id,
  ]);
  return [header, ...rows].map((r) => r.map(csvCell).join(',')).join('\r\n') + '\r\n';
}

// ---------------------------------------------------------------- door and power periods

// Door-open and power-cut periods [{from, to}] inside [from, to], from the events
// (DOOR_CLOSED carries openSeconds; POWER_LOST / POWER_RESTORED pairs) and the live state for
// a period that is still going on.
export function periodsFromEvents(events, from, to, live = {}) {
  const door = [];
  const power = [];
  let lostAt = null;
  for (const e of [...events].sort((a, b) => a.ts - b.ts)) {
    if (e.type === 'DOOR_CLOSED') {
      door.push({ from: e.ts - (e.details?.openSeconds || 0) * 1000, to: e.ts });
    } else if (e.type === 'POWER_LOST') {
      lostAt = e.ts;
    } else if (e.type === 'POWER_RESTORED') {
      power.push({ from: lostAt ?? e.ts - (e.details?.durationS || 0) * 1000, to: e.ts });
      lostAt = null;
    }
  }
  if (lostAt != null || live.mainsPower === false) power.push({ from: lostAt ?? to, to });
  const clip = (list) => list
    .filter((p) => p.to >= from && p.from <= to)
    .map((p) => ({ from: Math.max(p.from, from), to: Math.min(p.to, to) }));
  return { door: clip(door), power: clip(power) };
}

// Door openings per day, from the daily summaries: [{key, start, count, longestS}]
export function doorOpeningsByDay(daily) {
  return daily.map((s) => ({ key: s.key, start: s.start, count: s.doorOpenings || 0, longestS: s.longestDoorOpenS || 0 }));
}
