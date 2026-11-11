import { describe, expect, test } from 'vitest';
import {
  combineSummaries, excursionStats, excursionsToCsv, hourlyPoints, meanKineticTemperature,
  percentInRange, periodsFromEvents,
} from './analytics.js';
import { eventDetails, formatDuration, formatTime } from './format.js';

const arrhenius = (t) => Math.exp(-10000 / (t + 273.15));

describe('mean kinetic temperature', () => {
  test('equals the temperature when it is constant', () => {
    expect(meanKineticTemperature(arrhenius(5) * 10, 10)).toBeCloseTo(5, 6);
  });
  test('is above the plain mean when the temperature varies', () => {
    const sum = arrhenius(2) + arrhenius(12);
    const mkt = meanKineticTemperature(sum, 2);
    expect(mkt).toBeGreaterThan(7);
    expect(mkt).toBeLessThan(12);
  });
  test('no data -> null', () => {
    expect(meanKineticTemperature(0, 0)).toBeNull();
  });
});

describe('summaries', () => {
  const day1 = { count: 2, sumTemp: 10, sumArrhenius: 2 * arrhenius(5), minTemp: 4, maxTemp: 6, secondsInRange: 3000,
    secondsOutOfRange: 600, doorOpenings: 3, doorOpenSeconds: 100, longestDoorOpenS: 60, powerCuts: 1, powerCutSeconds: 300 };
  const day2 = { count: 2, sumTemp: 12, sumArrhenius: 2 * arrhenius(6), minTemp: 3, maxTemp: 9, secondsInRange: 3600,
    secondsOutOfRange: 0, doorOpenings: 1, doorOpenSeconds: 20, longestDoorOpenS: 20, powerCuts: 0, powerCutSeconds: 0 };

  test('percent in range', () => {
    expect(percentInRange(day1)).toBeCloseTo(83.33, 2);
    expect(percentInRange({ secondsInRange: 0, secondsOutOfRange: 0 })).toBeNull();
  });

  test('combining days', () => {
    const t = combineSummaries([day1, day2]);
    expect(t.count).toBe(4);
    expect(t.minTemp).toBe(3);
    expect(t.maxTemp).toBe(9);
    expect(t.meanTemp).toBe(5.5);
    expect(t.doorOpenings).toBe(4);
    expect(t.longestDoorOpenS).toBe(60);
    expect(t.powerCuts).toBe(1);
    expect(t.percentInRange).toBeCloseTo((6600 / 7200) * 100, 6);
    expect(t.mkt).toBeGreaterThan(5.5);
  });

  test('hourly points use the middle of the hour and skip empty hours', () => {
    const points = hourlyPoints([
      { start: 0, count: 60, sumTemp: 300, countAmbient: 60, sumAmbient: 1440, minTemp: 4, maxTemp: 6 },
      { start: 3600000, count: 0 },
    ]);
    expect(points).toEqual([{ x: 1800000, internal: 5, ambient: 24, min: 4, max: 6 }]);
  });
});

describe('excursions', () => {
  const list = [
    { id: 'a', start: 1000, end: 61000, durationS: 600, outOfRangeSeconds: 550, confirmed: true, direction: 'HIGH', minTemp: 7.5, maxTemp: 9.2, causeGuess: 'door' },
    { id: 'b', start: 5000, end: 6000, durationS: 60, outOfRangeSeconds: 60, confirmed: false, direction: 'HIGH' },
    { id: 'c', start: 9000, end: null, durationS: 0, outOfRangeSeconds: 0, offlineGapS: 120, confirmed: true, direction: 'LOW' },
  ];

  test('stats count confirmed excursions by default', () => {
    expect(excursionStats(list)).toEqual({ count: 2, totalDurationS: 600, totalOutOfRangeS: 670, longestS: 600 });
    expect(excursionStats(list, { confirmedOnly: false }).count).toBe(3);
    expect(excursionStats(list, { from: 2000 }).count).toBe(1);
  });

  test('CSV export has a header, one row each, ongoing marked, cells escaped', () => {
    const csv = excursionsToCsv([...list, { id: 'x,"y"', start: 0, confirmed: true, direction: 'LOW' }]);
    const lines = csv.trim().split('\r\n');
    expect(lines[0]).toBe('start,end,duration_s,out_of_range_s,offline_gap_s,direction,min_temp_c,max_temp_c,confirmed,cause_guess,excursion_id');
    expect(lines).toHaveLength(5);
    expect(lines[1]).toMatch(/^1970-01-01 02:00:01,1970-01-01 02:01:01,600,550,0,HIGH,7.5,9.2,yes,door,a$/);
    expect(lines[3]).toContain(',ongoing,');
    expect(lines[4].endsWith('"x,""y"""')).toBe(true);
  });
});

describe('door and power periods', () => {
  const events = [
    { type: 'DOOR_CLOSED', ts: 100000, details: { openSeconds: 30 } },
    { type: 'POWER_LOST', ts: 200000, details: {} },
    { type: 'POWER_RESTORED', ts: 260000, details: { durationS: 60 } },
    { type: 'POWER_LOST', ts: 400000, details: {} },
  ];

  test('closed periods, an ongoing power cut, clipped to the window', () => {
    const p = periodsFromEvents(events, 0, 500000);
    expect(p.door).toEqual([{ from: 70000, to: 100000 }]);
    expect(p.power).toEqual([{ from: 200000, to: 260000 }, { from: 400000, to: 500000 }]);
    expect(periodsFromEvents(events, 80000, 210000).door).toEqual([{ from: 80000, to: 100000 }]);
  });

  test('restored without a lost event in the window uses the duration', () => {
    const p = periodsFromEvents([events[2]], 0, 500000);
    expect(p.power).toEqual([{ from: 200000, to: 260000 }]);
  });
});

describe('formatting', () => {
  test('durations', () => {
    expect(formatDuration(45)).toBe('45 s');
    expect(formatDuration(750)).toBe('12 min 30 s');
    expect(formatDuration(720)).toBe('12 min');
    expect(formatDuration(3900)).toBe('1 h 05 min');
    expect(formatDuration(200000)).toBe('2 d 07 h');
  });
  test('times are in Kigali time (UTC+2)', () => {
    expect(formatTime(Date.UTC(2026, 10, 15, 12, 2))).toBe('14:02');
  });
  test('event details', () => {
    expect(eventDetails({ type: 'DOOR_CLOSED', details: { openSeconds: 150, alarmed: true } })).toBe('was open 2 min 30 s (alarm)');
  });
});
