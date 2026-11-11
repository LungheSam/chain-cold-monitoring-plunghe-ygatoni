// Firestore store (Firebase Admin SDK). Same functions as memoryStore.js.
// Data model: docs/data-model.md. Times are kept in ms in the code and stored as Firestore
// Timestamps for the fields listed in TIME_FIELDS, so the dashboard can query by date.
import { initializeApp, cert, applicationDefault } from 'firebase-admin/app';
import { getFirestore, Timestamp } from 'firebase-admin/firestore';
import { getAuth } from 'firebase-admin/auth';

const TIME_FIELDS = ['ts', 'start', 'end', 'since', 'lastSeen', 'lastTelemetryTs', 'receivedAt'];
const ALREADY_EXISTS = 6; // gRPC status code returned by create() when the document exists

// ms -> Timestamp for the known time fields (top level only)
function toFirestore(data) {
  const out = { ...data };
  for (const key of TIME_FIELDS) {
    if (typeof out[key] === 'number') out[key] = Timestamp.fromMillis(out[key]);
  }
  return out;
}

// Timestamp -> ms
function fromFirestore(data) {
  if (!data) return null;
  const out = { ...data };
  for (const [key, value] of Object.entries(out)) {
    if (value instanceof Timestamp) out[key] = value.toMillis();
  }
  return out;
}

// Starts the Firebase Admin SDK. Credentials, in order:
// FIREBASE_SERVICE_ACCOUNT (whole JSON, used on Railway), else GOOGLE_APPLICATION_CREDENTIALS
// (path to the JSON, used locally). With FIRESTORE_EMULATOR_HOST set, no credentials are needed.
export function initFirebase(config) {
  const options = { projectId: config.firebase.projectId || undefined };
  if (config.firebase.serviceAccountJson) {
    options.credential = cert(JSON.parse(config.firebase.serviceAccountJson));
  } else if (!process.env.FIRESTORE_EMULATOR_HOST) {
    options.credential = applicationDefault();
  }
  const app = initializeApp(options);
  return { db: getFirestore(app), auth: getAuth(app) };
}

export function createFirestoreStore(db) {
  const unit = (unitId) => db.collection('units').doc(unitId);

  return {
    kind: 'firestore',

    async getUnit(unitId) {
      const snap = await unit(unitId).get();
      return snap.exists ? fromFirestore(snap.data()) : null;
    },
    async updateUnit(unitId, fields) {
      await unit(unitId).set(toFirestore(fields), { merge: true });
    },
    async addReading(unitId, reading) {
      await unit(unitId).collection('readings').add(toFirestore(reading));
    },
    async getSummary(unitId, kind, key) {
      const snap = await unit(unitId).collection(kind).doc(key).get();
      return snap.exists ? fromFirestore(snap.data()) : null;
    },
    async setSummary(unitId, kind, key, data) {
      await unit(unitId).collection(kind).doc(key).set(toFirestore(data));
    },
    async saveEventIfNew(unitId, event) {
      try {
        await unit(unitId).collection('events').doc(event.id).create(toFirestore(event));
        return true;
      } catch (err) {
        if (err.code === ALREADY_EXISTS) return false;
        throw err;
      }
    },
    async upsertExcursion(unitId, excursionId, data) {
      await unit(unitId).collection('excursions').doc(excursionId).set(toFirestore(data), { merge: true });
    },
    async addAccess(unitId, id, data) {
      await unit(unitId).collection('access').doc(id).set(toFirestore(data));
    },

    async listContacts() {
      const snap = await db.collection('contacts').get();
      return snap.docs.map((d) => ({ id: d.id, ...d.data() }));
    },
    async getContactsForUnit(unitId) {
      // Few contacts, so filtering here is simpler than a composite index
      return (await this.listContacts()).filter((c) => c.active !== false && (c.units || []).includes(unitId));
    },
    async saveContact(id, data) {
      const ref = id ? db.collection('contacts').doc(id) : db.collection('contacts').doc();
      await ref.set(data);
      return ref.id;
    },
    async deleteContact(id) {
      const ref = db.collection('contacts').doc(id);
      if (!(await ref.get()).exists) return false;
      await ref.delete();
      return true;
    },

    async getUserRole(uid) {
      const snap = await db.collection('users').doc(uid).get();
      return snap.exists ? snap.data().role || null : null;
    },
    async getSmsState(unitId) {
      const snap = await db.collection('smsState').doc(unitId).get();
      return snap.exists ? snap.data() : { lastAlertAt: {}, open: {} };
    },
    async setSmsState(unitId, state) {
      await db.collection('smsState').doc(unitId).set(state);
    },
    async addSmsLog(entry) {
      await db.collection('smsLog').add(toFirestore(entry));
    },
  };
}
