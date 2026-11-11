// Back end entry point. Phase 0 only checks the configuration; MQTT, Firestore,
// the Web Thing routes and SMS are added in Phase 3.
import { loadConfig } from './config.js';

const config = loadConfig();
console.log(`coldchain-backend: units=${config.unitIds.join(',')} mqtt=${config.mqtt.url} (Phase 0 skeleton)`);
