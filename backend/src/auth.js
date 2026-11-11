// Authentication with Firebase ID tokens ("Authorization: Bearer <token>").
// Roles come from Firestore users/{uid}.role: "supervisor" or "viewer". A signed-in user without a
// users/{uid} document has no access.
//
// DEV_AUTH (only allowed with STORE=memory, for trying the API before Firebase is set up):
// the tokens "dev-supervisor" and "dev-viewer" are accepted.

export function createAuth({ verifyIdToken, getUserRole, devAuth = false, log = console }) {
  if (devAuth) log.warn('DEV_AUTH is on: the tokens dev-supervisor and dev-viewer are accepted. Never use this in production.');

  async function identify(req) {
    const header = req.get('authorization') || '';
    const match = header.match(/^Bearer (.+)$/i);
    if (!match) return { status: 401, error: 'missing Bearer token' };
    const token = match[1].trim();

    if (devAuth && (token === 'dev-supervisor' || token === 'dev-viewer')) {
      return { user: { uid: token, email: `${token}@local`, role: token.slice(4) } };
    }
    let decoded;
    try {
      decoded = await verifyIdToken(token);
    } catch {
      return { status: 401, error: 'invalid or expired token' };
    }
    const role = await getUserRole(decoded.uid);
    if (role !== 'supervisor' && role !== 'viewer') return { status: 403, error: 'no role for this user' };
    return { user: { uid: decoded.uid, email: decoded.email || null, role } };
  }

  const requireUser = async (req, res, next) => {
    try {
      const result = await identify(req);
      if (!result.user) return res.status(result.status).json({ error: result.error });
      req.user = result.user;
      next();
    } catch (err) {
      next(err);
    }
  };

  const requireSupervisor = [
    requireUser,
    (req, res, next) => (req.user.role === 'supervisor' ? next() : res.status(403).json({ error: 'supervisor role required' })),
  ];

  return { requireUser, requireSupervisor };
}
