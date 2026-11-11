// Time helpers. Rwanda (Africa/Kigali) is UTC+2 all year (no daylight saving), so a fixed offset
// is enough and avoids time-zone libraries. Hourly/daily summaries and SMS times use local time.

export const KIGALI_OFFSET_MS = 2 * 3600 * 1000;

function local(ms) {
  return new Date(ms + KIGALI_OFFSET_MS); // read it with the getUTC* methods
}

const pad = (n) => String(n).padStart(2, '0');

// "2026111514" for 15 Nov 2026, 14:xx local time
export function hourKey(ms) {
  const d = local(ms);
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}${pad(d.getUTCHours())}`;
}

// "20261115"
export function dayKey(ms) {
  return hourKey(ms).slice(0, 8);
}

// Start of the local hour / day, in ms since the epoch
export function hourStart(ms) {
  return Math.floor((ms + KIGALI_OFFSET_MS) / 3600000) * 3600000 - KIGALI_OFFSET_MS;
}

export function dayStart(ms) {
  return Math.floor((ms + KIGALI_OFFSET_MS) / 86400000) * 86400000 - KIGALI_OFFSET_MS;
}

// "14:02"
export function clockTime(ms) {
  const d = local(ms);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

// 45 -> "45 s", 750 -> "12 min", 3900 -> "1 h 05 min"
export function duration(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const minutes = Math.round(s / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${pad(minutes % 60)} min`;
}
