"""A small grid maze router (A* search) for the 2-layer carrier board.

KiCad has no built-in autorouter and Freerouting needs Java, so make_pcb.py uses this instead.
The idea is the classic Lee/A* maze router:

- The board is a grid of points (pitch 0.254 mm) on two layers (0 = F.Cu, 1 = B.Cu).
- Every piece of copper (pad, track, via) is stored with its exact distance to each nearby grid
  point. A track of net N may use a grid point only if all copper of *other* nets is far enough
  away: half the track width + clearance + a small safety margin.
- A* finds the cheapest path from a new pad to the copper already connected for that net, moving
  in 8 directions on a layer, or changing layer through a via (which costs more).
- Multi-pin nets are connected one pad at a time, nearest pad first.

All lengths are in mm, in board coordinates (0, 0 = top-left corner of the board, y down).
"""
import heapq
import math

import numpy as np

CLEARANCE = 0.2        # copper to copper (KiCad's default rule)
EDGE_CLEARANCE = 0.5   # copper to board edge
MARGIN = 0.05          # extra, because only grid points are checked
VIA_D, VIA_DRILL = 0.6, 0.3
VIA_COST = 12          # in grid steps: vias are allowed but not free
PATCH = 2.0            # how far around each copper item distances are stored


class Copper:
    """One copper item: its net, its layers and a patch of distances to the grid points around it."""

    def __init__(self, net, layers, rows, cols, dist, kind):
        self.net, self.layers, self.rows, self.cols, self.dist, self.kind = net, layers, rows, cols, dist, kind


class Router:
    def __init__(self, width, height, corner_r, pitch, x0, y0):
        self.w, self.h, self.r = width, height, corner_r
        self.pitch, self.x0, self.y0 = pitch, x0, y0
        self.nx = int((width - x0) / pitch) + 1
        self.ny = int((height - y0) / pitch) + 1
        self.xs = x0 + np.arange(self.nx) * pitch
        self.ys = y0 + np.arange(self.ny) * pitch
        self.items = []
        self.edge_dist = self._edge_distance()
        self.tracks = []    # (net, layer, [(x, y), ...], width) for make_pcb.py
        self.vias = []      # (net, x, y)

    # ------------------------------------------------------------ geometry

    def _edge_distance(self):
        """Distance from each grid point to the board outline (rounded rectangle), inside > 0."""
        X, Y = np.meshgrid(self.xs, self.ys)
        r = self.r
        # distance to a rounded rectangle = distance to the inner rectangle minus r
        dx = np.maximum(np.abs(X - self.w / 2) - (self.w / 2 - r), 0)
        dy = np.maximum(np.abs(Y - self.h / 2) - (self.h / 2 - r), 0)
        outside_inner = np.hypot(dx, dy)
        inside_inner = np.minimum(self.w / 2 - r - np.abs(X - self.w / 2), self.h / 2 - r - np.abs(Y - self.h / 2))
        return np.where(outside_inner > 0, r - outside_inner, r + np.maximum(inside_inner, 0))

    def _window(self, xmin, ymin, xmax, ymax):
        c0 = max(0, int(math.floor((xmin - PATCH - self.x0) / self.pitch)))
        c1 = min(self.nx, int(math.ceil((xmax + PATCH - self.x0) / self.pitch)) + 1)
        r0 = max(0, int(math.floor((ymin - PATCH - self.y0) / self.pitch)))
        r1 = min(self.ny, int(math.ceil((ymax + PATCH - self.y0) / self.pitch)) + 1)
        X, Y = np.meshgrid(self.xs[c0:c1], self.ys[r0:r1])
        return slice(r0, r1), slice(c0, c1), X, Y

    def add_pad(self, net, layers, cx, cy, w, h, shape):
        """shape: 'circle', 'oval' or 'rect' (rounded rectangles are treated as rectangles)."""
        rows, cols, X, Y = self._window(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        if shape == "circle":
            d = np.hypot(X - cx, Y - cy) - w / 2
        elif shape == "oval":
            if w >= h:
                d = np.hypot(np.maximum(np.abs(X - cx) - (w - h) / 2, 0), Y - cy) - h / 2
            else:
                d = np.hypot(X - cx, np.maximum(np.abs(Y - cy) - (h - w) / 2, 0)) - w / 2
        else:   # signed distance to a rectangle: positive outside, negative inside
            qx, qy = np.abs(X - cx) - w / 2, np.abs(Y - cy) - h / 2
            d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)
        self.items.append(Copper(net, layers, rows, cols, d, "pad"))

    def add_segment(self, net, layer, a, b, width):
        rows, cols, X, Y = self._window(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        ax, ay = a
        bx, by = b
        L2 = (bx - ax) ** 2 + (by - ay) ** 2
        t = np.clip(((X - ax) * (bx - ax) + (Y - ay) * (by - ay)) / L2, 0, 1) if L2 > 0 else 0
        d = np.hypot(X - (ax + t * (bx - ax)), Y - (ay + t * (by - ay))) - width / 2
        self.items.append(Copper(net, (layer,), rows, cols, d, "track"))

    def add_via(self, net, x, y):
        rows, cols, X, Y = self._window(x, y, x, y)
        self.items.append(Copper(net, (0, 1), rows, cols, np.hypot(X - x, Y - y) - VIA_D / 2, "via"))
        self.vias.append((net, x, y))

    # ------------------------------------------------------------ masks

    def free_mask(self, net, layer, half_width):
        """True where a track of this net and half width may have its centre line."""
        limit = half_width + CLEARANCE + MARGIN
        free = self.edge_dist >= half_width + EDGE_CLEARANCE + MARGIN
        for it in self.items:
            if layer in it.layers and it.net != net:
                free[it.rows, it.cols] &= it.dist >= limit
        return free

    def via_mask(self, net):
        """True where a via of this net may go: away from other copper, and not inside any pad."""
        limit = VIA_D / 2 + CLEARANCE + MARGIN
        ok = self.edge_dist >= VIA_D / 2 + EDGE_CLEARANCE + MARGIN
        for it in self.items:
            if it.net != net or it.kind == "pad":
                ok[it.rows, it.cols] &= it.dist >= limit
        return ok

    def inside_mask(self, pad_index):
        it = self.items[pad_index]
        m = np.zeros((self.ny, self.nx), bool)
        m[it.rows, it.cols] = it.dist <= -0.05
        return m

    # ------------------------------------------------------------ search

    def route(self, net, width, start_pad, target):
        """Route from the pad `start_pad` (index in self.items) to the target masks [F, B].
        Returns the list of (layer, x, y) points, or None."""
        h = width / 2
        free = [self.free_mask(net, l, h) for l in (0, 1)]
        via_ok = self.via_mask(net) & free[0] & free[1]
        start = self.inside_mask(start_pad)
        nx, n = self.nx, self.nx * self.ny
        flat_free = [bytes(f.ravel()) for f in free]
        flat_via = bytes(via_ok.ravel())
        flat_target = [bytes((t & f).ravel()) for t, f in zip(target, free)]
        tj, ti = np.nonzero(target[0] | target[1])
        if len(tj) == 0:
            return None
        tbox = (ti.min(), ti.max(), tj.min(), tj.max())

        def heuristic(i, j):          # octile distance to the target's bounding box
            dx = max(tbox[0] - i, 0, i - tbox[1])
            dy = max(tbox[2] - j, 0, j - tbox[3])
            return max(dx, dy) + 0.414 * min(dx, dy)

        best, came, heap = {}, {}, []
        for layer in self.items[start_pad].layers:
            for idx in np.flatnonzero((start & free[layer]).ravel()):
                state = layer * n + int(idx)
                best[state] = 0.0
                came[state] = None
                heapq.heappush(heap, (heuristic(idx % nx, idx // nx), 0.0, state))
        steps = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        while heap:
            _, cost, state = heapq.heappop(heap)
            if cost > best.get(state, 1e18):
                continue
            layer, idx = divmod(state, n)
            if flat_target[layer][idx]:
                return self._path(came, state, n)
            j, i = divmod(idx, nx)
            fl = flat_free[layer]
            for di, dj, c in steps:
                ii, jj = i + di, j + dj
                if not (0 <= ii < nx and 0 <= jj < self.ny):
                    continue
                nidx = jj * nx + ii
                if not fl[nidx]:
                    continue
                if di and dj and not (fl[j * nx + ii] and fl[jj * nx + i]):
                    continue                         # no corner cutting on diagonals
                self._push(heap, best, came, layer * n + nidx, cost + c, state, heuristic(ii, jj))
            if flat_via[idx]:
                self._push(heap, best, came, (1 - layer) * n + idx, cost + VIA_COST, state, heuristic(i, j))
        return None

    @staticmethod
    def _push(heap, best, came, state, cost, parent, h):
        if cost < best.get(state, 1e18):
            best[state] = cost
            came[state] = parent
            heapq.heappush(heap, (cost + h, cost, state))

    def _path(self, came, state, n):
        points = []
        while state is not None:
            layer, idx = divmod(state, n)
            j, i = divmod(idx, self.nx)
            points.append((layer, float(self.xs[i]), float(self.ys[j])))
            state = came[state]
        return points[::-1]

    # ------------------------------------------------------------ nets

    def connect(self, net, width, pad_indices):
        """Connect all pads of a net (nearest first). A net can be connected in several calls (for
        example a wide piece first): what is already connected is remembered. Returns the number of
        pads that could not be routed."""
        if not hasattr(self, "joined"):
            self.joined = {}
        if net not in self.joined:
            self.joined[net] = ([np.zeros((self.ny, self.nx), bool), np.zeros((self.ny, self.nx), bool)], [])
        target, connected = self.joined[net]

        def add_to_target(pad):
            m = self.inside_mask(pad)
            for layer in self.items[pad].layers:
                target[layer] |= m

        centre = lambda p: (self.xs[self.items[p].cols].mean(), self.ys[self.items[p].rows].mean())
        todo = [p for p in pad_indices if p not in connected]
        if not connected:
            connected.append(todo.pop(0))
            add_to_target(connected[0])
        failed = 0
        while todo:
            # nearest unconnected pad to any connected pad
            todo.sort(key=lambda p: min(math.dist(centre(p), centre(q)) for q in connected))
            pad = todo.pop(0)
            path = self.route(net, width, pad, target)
            add_to_target(pad)
            connected.append(pad)
            if path is None:
                failed += 1
                continue
            self._store(net, width, path, target)
        return failed

    def _store(self, net, width, path, target):
        """Turn a grid path into straight track pieces and vias; add them to the copper and target."""
        run = [path[0]]
        for p in path[1:]:
            if p[0] != run[-1][0]:                    # layer change: a via at this point
                self._add_run(net, width, run, target)
                self.add_via(net, p[1], p[2])
                run = [p]
            else:
                run.append(p)
        self._add_run(net, width, run, target)

    def _add_run(self, net, width, run, target):
        layer = run[0][0]
        pts = [(x, y) for _, x, y in run]
        for x, y in pts:
            j = int(round((y - self.y0) / self.pitch))
            i = int(round((x - self.x0) / self.pitch))
            target[layer][j, i] = True
        # keep only the corners
        corners = [pts[0]]
        for k in range(1, len(pts) - 1):
            d1 = (round((pts[k][0] - pts[k - 1][0]) / self.pitch), round((pts[k][1] - pts[k - 1][1]) / self.pitch))
            d2 = (round((pts[k + 1][0] - pts[k][0]) / self.pitch), round((pts[k + 1][1] - pts[k][1]) / self.pitch))
            if d1 != d2:
                corners.append(pts[k])
        if len(pts) > 1:
            corners.append(pts[-1])
        for a, b in zip(corners, corners[1:]):
            self.add_segment(net, layer, a, b, width)
        if len(corners) > 1:
            self.tracks.append((net, layer, corners, width))
