"""Check a Fritzing breadboard export against the sketch: every connection must touch.

Fritzing's SVG export (Fritzing.exe -svg <folder>) draws each part inside <g partID="...">.
We find each connector's centre in the export (where Fritzing really drew it) and, for every
pair of connectors that the sketch says are connected, check that the two centres coincide.

Usage: python check_export.py coldchain.fzz exported_breadboard.svg
"""
import io
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

from svgelements import SVG

SVGNS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVGNS)


def export_geometry(svg_path):
    """Read the export: connector centres and line end points of every part.

    Returns (centres, ends): centres[(modelIndex, connectorId)] = (x, y) and
    ends[modelIndex] = list of (x, y) line end points (wires and bent legs are lines).
    Units: Fritzing units (90 per inch)."""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    centres, ends = {}, {}
    for g in list(root.iter(f"{{{SVGNS}}}g")):
        pid = g.get("partID")
        if pid is None:
            continue
        model_index = int(pid) // 10
        wrapper = ET.Element(f"{{{SVGNS}}}svg", {"viewBox": root.get("viewBox"),
                                                   "width": root.get("width"), "height": root.get("height")})
        wrapper.append(g)
        svg = SVG.parse(io.StringIO(ET.tostring(wrapper, encoding="unicode")), ppi=90)
        pts = ends.setdefault(model_index, [])
        for e in svg.elements():
            if e.__class__.__name__ == "SimpleLine":
                pts.append((e.implicit_x1, e.implicit_y1))
                pts.append((e.implicit_x2, e.implicit_y2))
            elif e.__class__.__name__ == "Path" and not getattr(e, "id", None):
                # bent legs are drawn as id-less paths "M start L end"
                segs = list(e)
                if segs:
                    pts.append((segs[0].end.x, segs[0].end.y))
                    pts.append((segs[-1].end.x, segs[-1].end.y))
            i = getattr(e, "id", None)
            if not i:
                continue
            m = re.fullmatch(r"(connector\d+)(pin|leg)?|(pin\d+[A-Z])", i)
            if not m:
                continue
            try:
                bb = e.bbox()
            except Exception:
                continue
            if bb:
                cid = m.group(1) or m.group(3)
                centres.setdefault((model_index, cid), ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2))
    # bent legs are drawn as separate round-capped "M x,y L x,y" paths outside the part groups
    vb = [float(v) for v in root.get("viewBox").split()]
    width_in = float(re.match(r"[\d.]+", root.get("width")).group(0))
    k = width_in * 90.0 / vb[2]
    legs = []
    for e in root.iter(f"{{{SVGNS}}}path"):
        m = re.fullmatch(r"M([-\d.]+),([-\d.]+)L([-\d.]+),([-\d.]+)", (e.get("d") or "").strip())
        if m and e.get("stroke-linecap") == "round" and e.get("id") is None:
            x1, y1, x2, y2 = (float(v) * k for v in m.groups())
            legs.append(((x1, y1), (x2, y2)))
    return centres, ends, legs


def links(fzz_path):
    """Connected pairs, item titles, and which items have bent legs / are wires."""
    with zipfile.ZipFile(fzz_path) as z:
        name = [n for n in z.namelist() if n.endswith(".fz")][0]
        root = ET.fromstring(z.read(name))
    pairs, titles, legged, wires = set(), {}, set(), set()
    for inst in root.iter("instance"):
        idx = int(inst.get("modelIndex"))
        titles[idx] = inst.findtext("title") or ""
        if inst.get("moduleIdRef") == "WireModuleID":
            wires.add(idx)
        bbv = inst.find("views/breadboardView")
        if bbv is None:
            continue
        for c in bbv.iter("connector"):
            if c.find("leg") is not None:
                legged.add((idx, c.get("connectorId")))
            for cn in c.iter("connect"):
                a = (idx, c.get("connectorId"))
                b = (int(cn.get("modelIndex")), cn.get("connectorId"))
                pairs.add(tuple(sorted([a, b])))
    return pairs, titles, legged, wires


def main(fzz, svg_path, tol=2.0):
    centres, ends, legs = export_geometry(svg_path)
    leg_tips = [p for leg in legs for p in leg]
    pairs, titles, legged, wires = links(fzz)

    def points(item):
        """Where a connector can be: a wire end, a bent leg end, or the connector centre."""
        idx, cid = item
        if idx in wires:
            e = ends.get(idx, [])
            # each wire is drawn twice (shadow + colour); connector0 is the first end
            return e[0:1] if cid == "connector0" else e[1:2]
        if item in legged:
            return leg_tips
        c = centres.get(item)
        return [c] if c else []

    bad = 0
    for a, b in sorted(pairs):
        if a[0] in wires and b[0] in wires:
            continue          # bends inside one wire: built to coincide
        pa, pb = points(a), points(b)
        if not pa or not pb:
            print("NOT FOUND", titles.get(a[0]), a[1], "<->", titles.get(b[0]), b[1])
            bad += 1
            continue
        d = min(math.hypot(p[0] - q[0], p[1] - q[1]) for p in pa for q in pb)
        if d > tol:
            bad += 1
            print(f"OFF {d:6.1f}  {titles.get(a[0])} {a[1]}  <->  {titles.get(b[0])} {b[1]}")
    print(f"{len(pairs)} connections checked, {bad} problems")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1], sys.argv[2]) else 0)
