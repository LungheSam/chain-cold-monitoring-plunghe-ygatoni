// Dashboard API (everything needs a Firebase ID token). Live data is read by the dashboard
// straight from Firestore; this API is only for things clients may not write themselves.
//   GET    /api/me               who am I, and my role
//   GET    /api/contacts         SMS contacts               (supervisor)
//   POST   /api/contacts         add a contact              (supervisor)
//   PUT    /api/contacts/:id     change a contact           (supervisor)
//   DELETE /api/contacts/:id     remove a contact           (supervisor)
import { Router } from 'express';
import { errorText, validateContact } from './schemas.js';

export function createApiRouter({ config, store, auth }) {
  const router = Router();

  router.get('/api/me', auth.requireUser, (req, res) => res.json(req.user));

  router.get('/api/contacts', auth.requireSupervisor, async (req, res, next) => {
    try {
      res.json(await store.listContacts());
    } catch (err) {
      next(err);
    }
  });

  async function save(req, res, next, id) {
    try {
      const contact = { units: [...config.unitIds], active: true, ...req.body };
      if (!validateContact(contact)) return res.status(400).json({ error: errorText(validateContact) });
      const savedId = await store.saveContact(id, contact);
      res.status(id ? 200 : 201).json({ id: savedId, ...contact });
    } catch (err) {
      next(err);
    }
  }

  router.post('/api/contacts', auth.requireSupervisor, (req, res, next) => save(req, res, next, null));
  router.put('/api/contacts/:cid', auth.requireSupervisor, (req, res, next) => save(req, res, next, req.params.cid));

  router.delete('/api/contacts/:cid', auth.requireSupervisor, async (req, res, next) => {
    try {
      const deleted = await store.deleteContact(req.params.cid);
      res.status(deleted ? 204 : 404).end();
    } catch (err) {
      next(err);
    }
  });

  return router;
}
