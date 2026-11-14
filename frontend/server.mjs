// Serves the built dashboard (frontend/dist) on Railway. No dependencies: only Node's own modules.
//   npm run build && npm start        -> http://localhost:4173 (or $PORT, which Railway sets)
//
// - Files from dist/ (JS, CSS, fonts) are sent with their content type. Their names contain a hash,
//   so browsers may keep them for a year; index.html is never cached, so a new deploy shows at once.
// - Any other path (/history, /unlock/cold-unit-01, ...) gets index.html: React Router shows the page.
// - /health answers "ok" for Railway's health check.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';

const DIST = path.join(import.meta.dirname, 'dist');
const PORT = Number(process.env.PORT || 4173);

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.txt': 'text/plain; charset=utf-8',
};

// Basic protection headers for every answer
const SECURITY = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Frame-Options': 'DENY',
};

async function sendFile(res, file, cache) {
  const body = await readFile(file);
  res.writeHead(200, {
    ...SECURITY,
    'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream',
    'Cache-Control': cache,
  });
  res.end(body);
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/health') {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      return res.end('ok');
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      res.writeHead(405, SECURITY);
      return res.end();
    }

    // Never serve anything outside dist/ (blocks paths like /../../secret)
    const file = path.join(DIST, path.normalize(decodeURIComponent(url.pathname)));
    if (file.startsWith(DIST + path.sep) && (await stat(file).catch(() => null))?.isFile()) {
      const hashed = url.pathname.startsWith('/assets/');
      return await sendFile(res, file, hashed ? 'public, max-age=31536000, immutable' : 'no-cache');
    }
    if (url.pathname.startsWith('/assets/')) {     // a missing asset is a real 404, not the app
      res.writeHead(404, SECURITY);
      return res.end('not found');
    }
    return await sendFile(res, path.join(DIST, 'index.html'), 'no-cache');
  } catch (err) {
    console.error(err);
    res.writeHead(500, SECURITY);
    res.end('server error');
  }
});

server.listen(PORT, '0.0.0.0', (err) => {
  if (err) {
    console.error(`Cannot listen on port ${PORT}: ${err.code || err.message}`);
    process.exit(1);
  }
  console.log(`Dashboard on port ${PORT} (serving ${DIST})`);
});
process.on('SIGTERM', () => server.close(() => process.exit(0)));
