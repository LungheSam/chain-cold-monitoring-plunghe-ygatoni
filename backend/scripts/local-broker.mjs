// A small MQTT broker for testing on the laptop when Docker/Mosquitto is not available.
//   cd backend && npm run broker          -> mqtt://localhost:1883
// Plain MQTT (no TLS, no passwords) and only on this computer (127.0.0.1): for development only.
// The real system uses HiveMQ Cloud with TLS and passwords (docs/decisions.md D3, D11).
import { createServer } from 'node:net';
import { Aedes } from 'aedes';

const PORT = Number(process.env.BROKER_PORT || 1883);

const broker = await Aedes.createBroker();
broker.on('client', (c) => console.log(`connected    ${c.id}`));
broker.on('clientDisconnect', (c) => console.log(`disconnected ${c.id}`));
broker.on('publish', (packet, client) => {
  if (client) console.log(`${packet.topic.padEnd(36)} ${String(packet.payload).slice(0, 90)}`);
});

const server = createServer(broker.handle);
server.listen(PORT, '127.0.0.1', () => console.log(`Local MQTT broker on mqtt://localhost:${PORT} (Ctrl+C to stop)`));
