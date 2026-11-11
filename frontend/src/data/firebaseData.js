// Firebase data source: Authentication + Firestore real-time listeners for reading, and the back
// end (with the user's ID token) for actions. The dashboard never writes to Firestore itself.
import { initializeApp } from 'firebase/app';
import {
  connectAuthEmulator, getAuth, onAuthStateChanged, signInWithEmailAndPassword, signOut,
} from 'firebase/auth';
import {
  collection, connectFirestoreEmulator, doc, getDoc, getDocs, getFirestore, limit, onSnapshot,
  orderBy, query, Timestamp, where,
} from 'firebase/firestore';
import { BACKEND_URL, firebaseConfig, USE_EMULATORS } from '../config.js';

// Firestore Timestamps -> ms, at any depth
function plain(value) {
  if (value instanceof Timestamp) return value.toMillis();
  if (Array.isArray(value)) return value.map(plain);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, plain(v)]));
  }
  return value;
}
const docData = (snap) => ({ id: snap.id, ...plain(snap.data()) });
const at = (ms) => Timestamp.fromMillis(ms);

export function createFirebaseData() {
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);
  if (USE_EMULATORS) {
    connectAuthEmulator(auth, 'http://127.0.0.1:9099');
    connectFirestoreEmulator(db, '127.0.0.1', 8080);
  }
  const unitCol = (unitId, name) => collection(db, 'units', unitId, name);

  // Calls the back end with the signed-in user's Firebase ID token
  async function call(method, path, body) {
    const token = await auth.currentUser?.getIdToken();
    let res;
    try {
      res = await fetch(`${BACKEND_URL}${path}`, {
        method,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      return { ok: false, status: 0, data: { error: 'back end not reachable' } };
    }
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { error: text };
    }
    return { ok: res.ok, status: res.status, data };
  }

  return {
    demo: false,
    auth: {
      onChange: (cb) => onAuthStateChanged(auth, (u) => cb(u ? { uid: u.uid, email: u.email } : null)),
      signIn: (email, password) => signInWithEmailAndPassword(auth, email, password),
      signOut: () => signOut(auth),
    },

    async getRole(uid) {
      const snap = await getDoc(doc(db, 'users', uid));
      return snap.exists() ? snap.data().role || null : null;
    },

    subscribeUnit(unitId, cb) {
      return onSnapshot(doc(db, 'units', unitId), (snap) => cb(snap.exists() ? docData(snap) : null));
    },

    async getReadings(unitId, from, to) {
      const q = query(unitCol(unitId, 'readings'), where('ts', '>=', at(from)), where('ts', '<=', at(to)), orderBy('ts'));
      return (await getDocs(q)).docs.map(docData);
    },

    async getSummaries(unitId, kind, from, to) {
      const q = query(unitCol(unitId, kind), where('start', '>=', at(from)), where('start', '<=', at(to)), orderBy('start'));
      return (await getDocs(q)).docs.map((d) => ({ key: d.id, ...plain(d.data()) }));
    },

    async getEvents(unitId, from, to) {
      const q = query(unitCol(unitId, 'events'), where('ts', '>=', at(from)), where('ts', '<=', at(to)), orderBy('ts'));
      return (await getDocs(q)).docs.map(docData);
    },

    subscribeEvents(unitId, max, cb) {
      const q = query(unitCol(unitId, 'events'), orderBy('ts', 'desc'), limit(max));
      return onSnapshot(q, (snap) => cb(snap.docs.map(docData)));
    },

    subscribeExcursions(unitId, cb) {
      const q = query(unitCol(unitId, 'excursions'), orderBy('start', 'desc'), limit(500));
      return onSnapshot(q, (snap) => cb(snap.docs.map(docData)));
    },

    subscribeAccess(unitId, max, cb) {
      const q = query(unitCol(unitId, 'access'), orderBy('ts', 'desc'), limit(max));
      return onSnapshot(q, (snap) => cb(snap.docs.map(docData)));
    },

    api: {
      action: (unitId, name, body = {}) => call('POST', `/things/${unitId}/actions/${name}`, body),
      putThresholds: (unitId, body) => call('PUT', `/things/${unitId}/properties/thresholds`, body),
      listContacts: () => call('GET', '/api/contacts'),
      saveContact: (id, body) => (id ? call('PUT', `/api/contacts/${id}`, body) : call('POST', '/api/contacts', body)),
      deleteContact: (id) => call('DELETE', `/api/contacts/${id}`),
    },
  };
}
