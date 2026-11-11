// Web of Things HTTP interface. The routes match the forms in td.js:
//   GET  /things                              list of Thing Descriptions
//   GET  /things/:id                          Thing Description (application/td+json)
//   GET  /things/:id/properties               all properties            (public)
//   GET  /things/:id/properties/:name         one property               (public)
//   PUT  /things/:id/properties/thresholds    write thresholds           (supervisor)
//   POST /things/:id/actions/:name            invoke an action           (supervisor)
//   GET  /things/:id/events[/:name]           Server-Sent Events         (public)
import { Router } from 'express';
import { buildThingDescription, PROPERTY_FIELDS } from './td.js';
import { errorText, validateThresholds, validateUnlockInput } from './schemas.js';

const ACTIONS = ['acknowledgeAlarm', 'setThresholds', 'unlockDoor'];

export function createWotRouter({ config, ingest, bus, hub, auth }) {
  const router = Router();

  const knownUnit = (req, res, next) =>
    (config.unitIds.includes(req.params.id) ? next() : res.status(404).json({ error: 'unknown thing' }));

  function readProperty(unitId, name) {
    if (name === 'thresholds') return ingest.thresholds(unitId);
    const field = PROPERTY_FIELDS[name];
    return field ? ingest.live(unitId)[field] : undefined;
  }

  // Send a command to the node and answer with its result
  async function runCommand(res, unitId, action, params) {
    if (!ingest.isOnline(unitId)) return res.status(409).json({ ok: false, error: 'unit offline' });
    const result = await bus.send(unitId, action, params);
    if (result.ok) {
      if (action === 'setThresholds') await ingest.setThresholds(unitId, params);
      return res.status(200).json(result);
    }
    return res.status(result.error === 'timeout' ? 504 : 422).json(result);
  }

  router.get('/things', (req, res) => {
    res.type('application/json').send(config.unitIds.map((id) => buildThingDescription(id, config.publicBaseUrl)));
  });

  router.get('/things/:id', knownUnit, (req, res) => {
    res.type('application/td+json').send(JSON.stringify(buildThingDescription(req.params.id, config.publicBaseUrl)));
  });

  router.get('/things/:id/properties', knownUnit, (req, res) => {
    const all = {};
    for (const name of [...Object.keys(PROPERTY_FIELDS), 'thresholds']) all[name] = readProperty(req.params.id, name);
    res.json(all);
  });

  router.get('/things/:id/properties/:name', knownUnit, (req, res) => {
    const value = readProperty(req.params.id, req.params.name);
    if (value === undefined) return res.status(404).json({ error: 'unknown property' });
    res.json(value);
  });

  router.put('/things/:id/properties/:name', knownUnit, auth.requireSupervisor, async (req, res, next) => {
    try {
      if (req.params.name !== 'thresholds') {
        const status = readProperty(req.params.id, req.params.name) === undefined ? 404 : 405;
        return res.status(status).json({ error: status === 405 ? 'property is read-only' : 'unknown property' });
      }
      if (!validateThresholds(req.body)) return res.status(400).json({ error: errorText(validateThresholds) });
      if (!ingest.isOnline(req.params.id)) return res.status(409).json({ error: 'unit offline' });
      const result = await bus.send(req.params.id, 'setThresholds', req.body);
      if (!result.ok) return res.status(result.error === 'timeout' ? 504 : 422).json(result);
      await ingest.setThresholds(req.params.id, req.body);
      res.status(204).end();
    } catch (err) {
      next(err);
    }
  });

  router.post('/things/:id/actions/:name', knownUnit, auth.requireSupervisor, async (req, res, next) => {
    try {
      const { id, name } = req.params;
      if (!ACTIONS.includes(name)) return res.status(404).json({ error: 'unknown action' });
      const body = req.body && typeof req.body === 'object' ? req.body : {};
      const by = req.user.email || req.user.uid;

      if (name === 'acknowledgeAlarm') return await runCommand(res, id, name, { by });
      if (name === 'setThresholds') {
        if (!validateThresholds(body)) return res.status(400).json({ error: errorText(validateThresholds) });
        return await runCommand(res, id, name, body);
      }
      // unlockDoor
      if (!validateUnlockInput(body)) return res.status(400).json({ error: errorText(validateUnlockInput) });
      return await runCommand(res, id, name, { ...body, by, method: 'qr' });
    } catch (err) {
      next(err);
    }
  });

  router.get('/things/:id/events', knownUnit, (req, res) => hub.add(req, res, { unitId: req.params.id }));
  router.get('/things/:id/events/:name', knownUnit, (req, res) =>
    hub.add(req, res, { unitId: req.params.id, eventName: req.params.name }));

  return router;
}
