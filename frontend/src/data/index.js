// Picks the data source: Firebase (normal) or the offline demo. Both give the same functions:
//
//   auth.onChange(cb) -> unsubscribe        cb(user | null), user = {uid, email}
//   auth.signIn(email, password), auth.signOut()
//   getRole(uid) -> "supervisor" | "viewer" | null
//   subscribeUnit(unitId, cb) -> unsubscribe            live unit document
//   getReadings(unitId, from, to)                       raw readings (1 per minute)
//   getSummaries(unitId, "hourly" | "daily", from, to)
//   getEvents(unitId, from, to)                         oldest first
//   subscribeEvents(unitId, max, cb) -> unsubscribe     newest first
//   subscribeExcursions(unitId, cb) -> unsubscribe      newest first
//   subscribeAccess(unitId, max, cb) -> unsubscribe     newest first
//   api.action(unitId, name, body)  api.putThresholds(unitId, body)
//   api.listContacts()  api.saveContact(id, body)  api.deleteContact(id)
//     -> {ok, status, data} ; all times are ms since the epoch
//
// Each one is loaded only when used, so the demo data never ends up in the production build.
import { DEMO } from '../config.js';

export async function loadData() {
  if (DEMO) {
    const { createDemoData } = await import('./demoData.js');
    return createDemoData();
  }
  const { createFirebaseData } = await import('./firebaseData.js');
  return createFirebaseData();
}
