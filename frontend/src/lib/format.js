// Formatting helpers. All times are shown in Kigali time (Africa/Kigali, UTC+2).
const TZ = 'Africa/Kigali';

const timeFmt = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
const dateTimeFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: TZ, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
});
const dayFmt = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'short', day: '2-digit', month: 'short' });
const csvFmt = new Intl.DateTimeFormat('sv-SE', {
  timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
});

export const formatTime = (ms) => (ms == null ? '–' : timeFmt.format(ms));
export const formatDateTime = (ms) => (ms == null ? '–' : dateTimeFmt.format(ms));
export const formatDay = (ms) => (ms == null ? '–' : dayFmt.format(ms));
// "2026-11-15 14:02:00" (sorts and opens well in Excel)
export const formatCsvTime = (ms) => (ms == null ? '' : csvFmt.format(ms));

// 45 -> "45 s", 750 -> "12 min 30 s", 3900 -> "1 h 05 min", 200000 -> "2 d 07 h"
export function formatDuration(seconds) {
  if (seconds == null) return '–';
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  if (s < 3600) {
    const rest = s % 60;
    return rest ? `${Math.floor(s / 60)} min ${rest} s` : `${s / 60} min`;
  }
  const pad = (n) => String(n).padStart(2, '0');
  if (s < 86400) return `${Math.floor(s / 3600)} h ${pad(Math.floor((s % 3600) / 60))} min`;
  return `${Math.floor(s / 86400)} d ${pad(Math.floor((s % 86400) / 3600))} h`;
}

// (values that round to 0.0 are shown as "0.0", not "-0.0")
export const formatTemp = (t) => (t == null ? '–' : `${(Math.abs(t) < 0.05 ? 0 : t).toFixed(1)} °C`);
export const formatPercent = (p) => (p == null ? '–' : `${p.toFixed(1)} %`);

// "OUT_OF_RANGE_HIGH" -> "Out of range high"
export function eventLabel(type) {
  const text = type.toLowerCase().replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// One-line summary of an event's details for the tables
export function eventDetails(e) {
  const d = e.details || {};
  switch (e.type) {
    case 'OUT_OF_RANGE_HIGH':
    case 'OUT_OF_RANGE_LOW':
      return `${d.temp} °C (limit ${d.limit} °C) since ${formatTime(d.since)}`;
    case 'BACK_IN_RANGE':
      return `${d.confirmed ? '' : 'short blip, '}lasted ${formatDuration(d.durationS)}, min ${d.minTemp} / max ${d.maxTemp} °C`;
    case 'DOOR_OPEN_TOO_LONG':
      return `open ${formatDuration(d.openSeconds)} (limit ${formatDuration(d.limitS)})`;
    case 'DOOR_CLOSED':
      return `was open ${formatDuration(d.openSeconds)}${d.alarmed ? ' (alarm)' : ''}`;
    case 'POWER_RESTORED':
      return `cut lasted ${formatDuration(d.durationS)}`;
    case 'SENSOR_FAULT':
      return `${d.sensor}: ${d.reason}`;
    case 'SENSOR_RESTORED':
      return d.sensor;
    case 'ALARM_ACKNOWLEDGED':
      return `by ${d.by} (${(d.alarms || []).join(', ')})`;
    case 'ACCESS_GRANTED':
    case 'ACCESS_DENIED':
      return accessDetails(d);
    default:
      return '';
  }
}

// "QR page, sup@example.org, open 5 s" or "keypad, wrong PIN (3/3), keypad locked 60 s"
export function accessDetails(d = {}) {
  const parts = [d.method === 'qr' ? 'QR page' : d.method];
  if (d.user) parts.push(d.user);
  if (d.seconds) parts.push(`open ${d.seconds} s`);
  if (d.reason) parts.push(d.attempt ? `${d.reason} (${d.attempt}/3)` : d.reason);
  if (d.purpose === 'acknowledge') parts.push('to acknowledge');
  if (d.lockedOutS) parts.push(`keypad locked ${d.lockedOutS} s`);
  return parts.filter(Boolean).join(', ');
}
