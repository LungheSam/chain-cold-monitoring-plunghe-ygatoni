// In-memory store with the same functions as firestoreStore.js.
// Used by the tests, and with STORE=memory to run the back end before Firebase is set up.
// Everything is lost when the process stops.
import { randomUUID } from 'node:crypto';

export function createMemoryStore() {
  const db = {
    units: new Map(),       // unitId -> unit document
    readings: [],           // {unitId, ...reading}
    summaries: new Map(),   // `${unitId}/${kind}/${key}` -> summary
    events: new Map(),      // `${unitId}/${eventId}` -> event
    excursions: new Map(),  // `${unitId}/${excursionId}` -> excursion
    access: new Map(),      // `${unitId}/${id}` -> access entry
    contacts: new Map(),    // contactId -> contact
    users: new Map(),       // uid -> {email, role}
    smsState: new Map(),    // unitId -> state
    smsLog: [],
  };
  const copy = (x) => (x == null ? null : structuredClone(x));

  return {
    kind: 'memory',
    db,

    async getUnit(unitId) {
      return copy(db.units.get(unitId));
    },
    async updateUnit(unitId, fields) {
      db.units.set(unitId, { ...(db.units.get(unitId) || {}), ...copy(fields) });
    },
    async addReading(unitId, reading) {
      db.readings.push({ unitId, ...copy(reading) });
    },
    async getSummary(unitId, kind, key) {
      return copy(db.summaries.get(`${unitId}/${kind}/${key}`));
    },
    async setSummary(unitId, kind, key, data) {
      db.summaries.set(`${unitId}/${kind}/${key}`, copy(data));
    },
    // Returns false if an event with this id was already stored (duplicate delivery)
    async saveEventIfNew(unitId, event) {
      const key = `${unitId}/${event.id}`;
      if (db.events.has(key)) return false;
      db.events.set(key, copy(event));
      return true;
    },
    async upsertExcursion(unitId, excursionId, data) {
      const key = `${unitId}/${excursionId}`;
      db.excursions.set(key, { ...(db.excursions.get(key) || {}), ...copy(data) });
    },
    async addAccess(unitId, id, data) {
      db.access.set(`${unitId}/${id}`, copy(data));
    },

    async listContacts() {
      return [...db.contacts.entries()].map(([id, c]) => ({ id, ...copy(c) }));
    },
    async getContactsForUnit(unitId) {
      return (await this.listContacts()).filter((c) => c.active !== false && (c.units || []).includes(unitId));
    },
    async saveContact(id, data) {
      const contactId = id || randomUUID();
      db.contacts.set(contactId, copy(data));
      return contactId;
    },
    async deleteContact(id) {
      return db.contacts.delete(id);
    },

    async getUserRole(uid) {
      return db.users.get(uid)?.role || null;
    },
    async getSmsState(unitId) {
      return copy(db.smsState.get(unitId)) || { lastAlertAt: {}, open: {} };
    },
    async setSmsState(unitId, state) {
      db.smsState.set(unitId, copy(state));
    },
    async addSmsLog(entry) {
      db.smsLog.push(copy(entry));
    },
  };
}
