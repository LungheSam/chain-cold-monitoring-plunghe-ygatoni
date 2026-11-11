// Give a Firebase Auth user a role (writes users/{uid} in Firestore).
// The person must first have an account (create it in the Firebase console: Authentication > Users).
//
//   npm run set-role -- someone@example.org supervisor
//   npm run set-role -- someone@example.org viewer
import { loadConfig } from '../src/config.js';
import { initFirebase } from '../src/store/firestoreStore.js';

const [email, role] = process.argv.slice(2);
if (!email || !['supervisor', 'viewer'].includes(role)) {
  console.error('usage: npm run set-role -- <email> <supervisor|viewer>');
  process.exit(1);
}

const { db, auth } = initFirebase(loadConfig());
const user = await auth.getUserByEmail(email);
await db.collection('users').doc(user.uid).set({ email, displayName: user.displayName || email, role }, { merge: true });
console.log(`users/${user.uid}: ${email} is now ${role}`);
process.exit(0);
