// Server-Sent Events hub for the WoT event affordances (GET /things/{id}/events[/{name}]).
// Each event is sent as:   id: <event id>\nevent: <type>\ndata: <JSON>\n\n
// A comment line is sent every 25 s so proxies (Railway) do not close idle connections.

export function createHub({ heartbeatMs = 25000 } = {}) {
  const clients = new Set();

  const heartbeat = setInterval(() => {
    for (const c of clients) c.res.write(': ping\n\n');
  }, heartbeatMs);
  heartbeat.unref?.();

  return {
    add(req, res, { unitId, eventName = null }) {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      });
      res.write(': connected\n\n');
      const client = { res, unitId, eventName };
      clients.add(client);
      req.on('close', () => clients.delete(client));
    },

    broadcast(unitId, event) {
      for (const c of clients) {
        if (c.unitId === unitId && (!c.eventName || c.eventName === event.type)) {
          c.res.write(`id: ${event.id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`);
        }
      }
    },

    count() {
      return clients.size;
    },

    close() {
      clearInterval(heartbeat);
      for (const c of clients) c.res.end();
      clients.clear();
    },
  };
}
