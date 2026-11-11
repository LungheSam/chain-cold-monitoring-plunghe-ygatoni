// Hourly and daily summary documents (units/{id}/hourly/{YYYYMMDDHH}, units/{id}/daily/{YYYYMMDD}).
// They keep the 7-day chart and the analytics page cheap in Firestore reads (docs/data-model.md).
//
// Each stored reading stands for one minute (readings are kept at most once per 60 s).
// Buckets are kept in memory and written by flush() (every few minutes and at shutdown). After a
// restart, a bucket is first read back from the store, so totals are continued, not overwritten.
//
// Mean kinetic temperature (MKT), the usual cold-chain summary figure, can be computed from
// sumArrhenius:  MKT = (dH/R) / -ln(sumArrhenius / count) - 273.15, with dH/R = 10 000 K
// (activation energy 83.144 kJ/mol, the standard value). MKT weights warm periods more than a
// plain mean, because degradation speeds up with temperature.
import { dayKey, dayStart, hourKey, hourStart } from './time.js';

export const DH_OVER_R = 10000; // kelvin
export const SECONDS_PER_READING = 60;

export function emptySummary(start) {
  return {
    start, count: 0, minTemp: null, maxTemp: null, sumTemp: 0, sumArrhenius: 0,
    countAmbient: 0, sumAmbient: 0,
    secondsInRange: 0, secondsOutOfRange: 0,
    doorOpenings: 0, doorOpenSeconds: 0, longestDoorOpenS: 0,
    powerCuts: 0, powerCutSeconds: 0,
  };
}

export function meanKineticTemperature(summary) {
  if (!summary.count) return null;
  return DH_OVER_R / -Math.log(summary.sumArrhenius / summary.count) - 273.15;
}

export function createSummaries({ store, log = console }) {
  const buckets = new Map(); // `${unitId}|${kind}|${key}` -> {unitId, kind, key, data, dirty}

  async function bucket(unitId, kind, ms) {
    const key = kind === 'hourly' ? hourKey(ms) : dayKey(ms);
    const id = `${unitId}|${kind}|${key}`;
    let b = buckets.get(id);
    if (!b) {
      const start = kind === 'hourly' ? hourStart(ms) : dayStart(ms);
      const saved = await store.getSummary(unitId, kind, key);
      b = { unitId, kind, key, data: saved || emptySummary(start), dirty: false };
      buckets.set(id, b);
    }
    return b;
  }

  // Apply a change to both the hourly and the daily bucket of time ms
  async function update(unitId, ms, change) {
    for (const kind of ['hourly', 'daily']) {
      const b = await bucket(unitId, kind, ms);
      change(b.data);
      b.dirty = true;
    }
  }

  return {
    async addReading(unitId, ms, temp, minC, maxC, ambient = null) {
      if (temp == null) return; // probe fault: nothing to add
      await update(unitId, ms, (s) => {
        if (ambient != null) {
          s.countAmbient = (s.countAmbient || 0) + 1;
          s.sumAmbient = (s.sumAmbient || 0) + ambient;
        }
        s.count += 1;
        s.minTemp = s.minTemp == null ? temp : Math.min(s.minTemp, temp);
        s.maxTemp = s.maxTemp == null ? temp : Math.max(s.maxTemp, temp);
        s.sumTemp += temp;
        s.sumArrhenius += Math.exp(-DH_OVER_R / (temp + 273.15));
        if (temp >= minC && temp <= maxC) s.secondsInRange += SECONDS_PER_READING;
        else s.secondsOutOfRange += SECONDS_PER_READING;
      });
    },

    async addDoorOpening(unitId, openedAtMs, openSeconds) {
      await update(unitId, openedAtMs, (s) => {
        s.doorOpenings += 1;
        s.doorOpenSeconds += openSeconds;
        s.longestDoorOpenS = Math.max(s.longestDoorOpenS, openSeconds);
      });
    },

    async addPowerCut(unitId, lostAtMs, seconds) {
      await update(unitId, lostAtMs, (s) => {
        s.powerCuts += 1;
        s.powerCutSeconds += seconds;
      });
    },

    // Write changed buckets. Buckets older than the current hour/day are then forgotten.
    async flush(nowMs = Date.now()) {
      for (const [id, b] of buckets) {
        if (b.dirty) {
          try {
            await store.setSummary(b.unitId, b.kind, b.key, b.data);
            b.dirty = false;
          } catch (err) {
            log.error(`summary ${id} not saved: ${err.message}`);
            continue;
          }
        }
        const current = b.kind === 'hourly' ? hourKey(nowMs) : dayKey(nowMs);
        if (b.key < current) buckets.delete(id);
      }
    },

    _buckets: buckets, // for tests
  };
}
