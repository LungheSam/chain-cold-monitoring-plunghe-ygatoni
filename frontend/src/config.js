// Settings from the Vite environment (frontend/.env.local, see .env.example).
const env = import.meta.env;

// Demo mode: no Firebase, no back end. Uses a generated week of data and a simulated live unit.
// Start it with `npm run demo`.
export const DEMO = env.MODE === 'demo' || env.VITE_DEMO === '1';

export const UNIT_ID = env.VITE_UNIT_ID || 'cold-unit-01';
export const BACKEND_URL = (env.VITE_BACKEND_URL || 'http://localhost:3000').replace(/\/$/, '');

export const firebaseConfig = {
  apiKey: env.VITE_FIREBASE_API_KEY,
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: env.VITE_FIREBASE_PROJECT_ID,
  appId: env.VITE_FIREBASE_APP_ID,
};
export const USE_EMULATORS = env.VITE_USE_EMULATORS === '1';
