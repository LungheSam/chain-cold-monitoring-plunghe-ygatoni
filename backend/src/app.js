// The Express app: CORS, JSON bodies, health check, WoT routes, dashboard API.
import express from 'express';
import { createWotRouter } from './wot.js';
import { createApiRouter } from './api.js';

// Allow the dashboard origins (comma-separated CORS_ORIGIN) to call us from the browser
function cors(allowed) {
  return (req, res, next) => {
    const origin = req.get('origin');
    if (origin && (allowed.includes(origin) || allowed.includes('*'))) {
      res.set('Access-Control-Allow-Origin', origin);
      res.set('Vary', 'Origin');
      res.set('Access-Control-Allow-Headers', 'Authorization, Content-Type');
      res.set('Access-Control-Allow-Methods', 'GET, PUT, POST, DELETE, OPTIONS');
    }
    if (req.method === 'OPTIONS') return res.status(204).end();
    next();
  };
}

export function createApp({ config, store, ingest, bus, hub, auth, log = console }) {
  const app = express();
  app.disable('x-powered-by');
  app.use(cors(config.corsOrigins));
  app.use(express.json({ limit: '10kb' }));

  app.get('/health', (req, res) => {
    res.json({ ok: true, units: config.unitIds.map((id) => ({ id, online: ingest.isOnline(id), lastSeen: ingest.lastSeen(id) })) });
  });

  app.use(createWotRouter({ config, ingest, bus, hub, auth }));
  app.use(createApiRouter({ config, store, auth }));

  app.use((req, res) => res.status(404).json({ error: 'not found' }));
  // eslint-disable-next-line no-unused-vars
  app.use((err, req, res, next) => {
    if (err.type === 'entity.parse.failed') return res.status(400).json({ error: 'body is not valid JSON' });
    log.error(err.stack || err);
    res.status(500).json({ error: 'internal error' });
  });
  return app;
}
