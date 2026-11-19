"""Small helper library that writes a Fritzing sketch (.fzz) from Python.

Fritzing stores a sketch as XML: one <instance> per part or wire, with its position in each
view and the list of connectors it touches. Wires must start and end exactly on a pin, so we
read every part's breadboard SVG and find the centre of each pin (svgelements does the maths).

Scene units are Fritzing's: 90 per inch, so the 0.1 in breadboard pitch is 9 units.
"""
import io
import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from html import escape

from svgelements import SVG

DPI = 90.0


# ---------------------------------------------------------------- SVG geometry

def svg_scale(svg_text):
    """Factor from svgelements pixels (ppi 90) to Fritzing units.

    Sizes in in/mm/cm are already right. Plain px sizes are 72 dpi when the file comes
    from Illustrator (Fritzing's own rule) and 90 dpi otherwise."""
    head = re.search(r"<svg[^>]*>", svg_text, re.S).group(0)
    m = re.search(r"""\swidth=["']\s*[\d.]+\s*([a-z%]*)""", head)
    unit = m.group(1) if m else ""
    if unit in ("in", "mm", "cm", "pt", "pc"):
        return 1.0
    if "Illustrator" in svg_text[:3000]:
        return DPI / 72.0
    return 1.0


class PartGeometry:
    """Pin centres, leg lines and size of one part's breadboard picture."""

    def __init__(self, svg_text, connectors):
        # connectors: list of dicts with id, name, svgId, legId
        k = svg_scale(svg_text)
        svg = SVG.parse(io.StringIO(svg_text), ppi=DPI)
        self.w = float(svg.width) * k
        self.h = float(svg.height) * k
        want = {c["svgId"] for c in connectors} | {c["legId"] for c in connectors if c["legId"]}
        boxes, lines = {}, {}
        for e in svg.elements():
            i = getattr(e, "id", None)
            if i not in want:
                continue
            if hasattr(e, "x1") and e.__class__.__name__ == "SimpleLine":
                lines[i] = ((e.x1 * k, e.y1 * k), (e.x2 * k, e.y2 * k))
            try:
                bb = e.bbox()
            except Exception:
                bb = None
            if bb and i not in boxes:
                boxes[i] = bb
        self.pins = {}   # connector id -> local centre
        self.legs = {}   # connector id -> (start, tip) local
        self.names = {}  # connector name -> connector id (first one wins)
        cx, cy = self.w / 2, self.h / 2
        for c in connectors:
            cid = c["id"]
            self.names.setdefault(c["name"], cid)
            if c["legId"] and c["legId"] in lines:
                a, b = lines[c["legId"]]
                # the leg starts at the end closer to the body (picture centre)
                da = math.hypot(a[0] - cx, a[1] - cy)
                db = math.hypot(b[0] - cx, b[1] - cy)
                start, tip = (a, b) if da < db else (b, a)
                self.legs[cid] = (start, tip)
                self.pins[cid] = tip
            elif c["svgId"] in boxes:
                x0, y0, x1, y1 = boxes[c["svgId"]]
                self.pins[cid] = ((x0 + x1) / 2 * k, (y0 + y1) / 2 * k)
        missing = [c["id"] for c in connectors if c["id"] not in self.pins]
        if missing:
            raise ValueError(f"no geometry for connectors {missing}")


def read_fzp(fzp_text):
    """Return (breadboard image path, connector list) from a .fzp file."""
    root = ET.fromstring(fzp_text)
    img = root.find("views/breadboardView/layers").get("image")
    conns = []
    for c in root.iter("connector"):
        p = c.find("views/breadboardView/p")
        if p is None:
            continue
        conns.append({"id": c.get("id"), "name": c.get("name"),
                      "svgId": p.get("svgId"), "legId": p.get("legId")})
    return img, conns


# ---------------------------------------------------------------- sketch model

class Item:
    """A part placed in the sketch."""

    def __init__(self, sketch, index, module_id, path, title, geo, x, y, angle, props,
                 sch, pcb, kind):
        self.sketch, self.index, self.module_id, self.path = sketch, index, module_id, path
        self.title, self.geo, self.x, self.y, self.angle = title, geo, x, y, angle
        self.props, self.sch, self.pcb, self.kind = props, sch, pcb, kind
        self.connects = {}       # connector id -> list of (other index, other connector, layer)
        self.leg_targets = {}    # connector id -> scene point of the leg tip

    # scene position of a local point (rotation about the picture centre)
    def to_scene(self, p):
        a = math.radians(self.angle)
        cx, cy = self.geo.w / 2, self.geo.h / 2
        dx, dy = p[0] - cx, p[1] - cy
        rx = dx * math.cos(a) - dy * math.sin(a) + cx
        ry = dx * math.sin(a) + dy * math.cos(a) + cy
        return (self.x + rx, self.y + ry)

    def cid(self, pin):
        """Accept a connector id ('connector3') or a pin name ('VDD')."""
        if pin in self.geo.pins:
            return pin
        if pin in self.geo.names:
            return self.geo.names[pin]
        raise KeyError(f"{self.title}: no pin {pin}")

    def at(self, pin):
        cid = self.cid(pin)
        if cid in self.leg_targets:
            return self.leg_targets[cid]
        return self.to_scene(self.geo.pins[cid])

    @property
    def own_layer(self):
        return {"breadboard": "breadboardbreadboard", "part": "breadboard",
                "wire": "breadboardWire"}[self.kind]


class Sketch:
    def __init__(self, parts_root):
        self.parts_root = parts_root
        self.items = []
        self.wires = []
        self.notes = []
        self.custom = {}          # module id -> custom part dict (bundled into the .fzz)
        self.next_index = 1000

    def _index(self):
        self.next_index += 7
        return self.next_index

    # ---- parts
    def core_part(self, fzp_rel, module_id, title, x, y, angle=0, props=None, sch=(0, 0), pcb=(0, 0),
                  kind="part"):
        fzp_path = os.path.join(self.parts_root, fzp_rel)
        with open(fzp_path, encoding="utf-8") as f:
            img, conns = read_fzp(f.read())
        svg_path = os.path.join(self.parts_root, "svg", "core", img)
        with open(svg_path, encoding="utf-8", errors="ignore") as f:
            geo = PartGeometry(f.read(), conns)
        item = Item(self, self._index(), module_id, fzp_path.replace("\\", "/"), title, geo,
                    x, y, angle, props or {}, sch, pcb, kind)
        self.items.append(item)
        return item

    def custom_part(self, part, title, x, y, angle=0, sch=(0, 0), pcb=(0, 0)):
        self.custom[part["module_id"]] = part
        img, conns = read_fzp(part["fzp"])
        geo = PartGeometry(part["breadboard"], conns)
        item = Item(self, self._index(), part["module_id"], f"{part['file']}.fzp", title, geo,
                    x, y, angle, {}, sch, pcb, "part")
        self.items.append(item)
        return item

    # ---- connections
    def _link(self, a, a_cid, b, b_cid):
        a.connects.setdefault(a_cid, []).append((b.index, b_cid, b.own_layer))
        b.connects.setdefault(b_cid, []).append((a.index, a_cid, a.own_layer))

    def leg(self, item, pin, target, target_pin):
        """Bend a part's leg so its tip sits in target's pin (a breadboard hole)."""
        cid = item.cid(pin)
        if item.angle:
            raise ValueError("legs are only supported on parts that are not rotated")
        item.leg_targets[cid] = target.at(target_pin)
        self._link(item, cid, target, target.cid(target_pin))

    def leg_free(self, item, pin, point):
        """Bend a leg to a free point (a wire will connect there)."""
        item.leg_targets[item.cid(pin)] = tuple(point)

    def center_on(self, item, pin_a, p, pin_b, q, lift=0.0):
        """Move a two-leg part so its leg starts sit midway over p and q (scene points),
        raised by 'lift'. Call before bending the legs."""
        sa = item.geo.legs[item.cid(pin_a)][0]
        sb = item.geo.legs[item.cid(pin_b)][0]
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        item.x = mx - (sa[0] + sb[0]) / 2
        item.y = my - (sa[1] + sb[1]) / 2 - lift

    def plug(self, item, pin, target, target_pin, tol=1.5):
        """A fixed pin sitting in a breadboard hole: check that they line up."""
        p, q = item.at(pin), target.at(target_pin)
        if math.hypot(p[0] - q[0], p[1] - q[1]) > tol:
            raise ValueError(f"{item.title}.{pin} at {p} is not on {target.title}.{target_pin} at {q}")
        self._link(item, item.cid(pin), target, target.cid(target_pin))

    def wire(self, a, a_pin, b, b_pin, color, via=()):
        """Wire from a.a_pin to b.b_pin, through the bend points in via (scene units)."""
        pts = [a.at(a_pin)] + [tuple(v) for v in via] + [b.at(b_pin)]
        segs = []
        for p, q in zip(pts, pts[1:]):
            w = WireSeg(self._index(), p, q, color)
            segs.append(w)
        for s1, s2 in zip(segs, segs[1:]):
            s1.connects.setdefault("connector1", []).append((s2.index, "connector0", "breadboardWire"))
            s2.connects.setdefault("connector0", []).append((s1.index, "connector1", "breadboardWire"))
        a_cid, b_cid = a.cid(a_pin), b.cid(b_pin)
        segs[0].connects.setdefault("connector0", []).append((a.index, a_cid, a.own_layer))
        a.connects.setdefault(a_cid, []).append((segs[0].index, "connector0", "breadboardWire"))
        segs[-1].connects.setdefault("connector1", []).append((b.index, b_cid, b.own_layer))
        b.connects.setdefault(b_cid, []).append((segs[-1].index, "connector1", "breadboardWire"))
        self.wires.extend(segs)
        return segs

    def note(self, x, y, w, h, lines):
        self.notes.append((self._index(), x, y, w, h, lines))

    # ---- output
    def to_xml(self):
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<module fritzingVersion="0.9.3b" icon=".png">',
               '    <views>',
               '        <view name="breadboardView" backgroundColor="#ffffff" gridSize="0.1in" showGrid="1" alignToGrid="1" viewFromBelow="0"/>',
               '        <view name="schematicView" backgroundColor="#ffffff" gridSize="0.1in" showGrid="1" alignToGrid="1" viewFromBelow="0"/>',
               '        <view name="pcbView" backgroundColor="#333333" gridSize="0.05in" showGrid="1" alignToGrid="1" viewFromBelow="0"/>',
               '    </views>',
               '    <instances>']
        z = 2.5
        for it in self.items:
            z += 0.001
            out.append(self._part_xml(it, 1.5 if it.kind == "breadboard" else z))
        zw = 3.5
        for w in self.wires:
            zw += 0.001
            out.append(w.to_xml(zw))
        for (idx, x, y, w, h, lines) in self.notes:
            out.append(note_xml(idx, x, y, w, h, lines))
        out += ['    </instances>', '</module>', '']
        return "\n".join(out)

    def _part_xml(self, it, z):
        props = "".join(f'            <property name="{k}" value="{escape(v)}"/>\n'
                        for k, v in it.props.items())
        transform = ""
        if it.angle:
            a = math.radians(it.angle)
            c, s = math.cos(a), math.sin(a)
            cx, cy = it.geo.w / 2, it.geo.h / 2
            # Qt row-vector form: p' = p * [[c, s], [-s, c]] + (m31, m32)
            m31 = cx - (cx * c - cy * s)
            m32 = cy - (cx * s + cy * c)
            transform = (f'\n                        <transform m11="{c:.6f}" m12="{s:.6f}" m13="0" '
                         f'm21="{-s:.6f}" m22="{c:.6f}" m23="0" m31="{m31:.4f}" m32="{m32:.4f}" m33="1"/>\n'
                         f'                    ')
        conns = []
        for cid, links in it.connects.items():
            leg = ""
            geom = '<geometry x="0" y="0"/>'
            if cid in it.leg_targets:
                start, _ = it.geo.legs[cid]
                tx, ty = it.leg_targets[cid]
                dx, dy = tx - it.x - start[0], ty - it.y - start[1]
                geom = f'<geometry x="{start[0]:.4f}" y="{start[1]:.4f}"/>'
                leg = (f'\n                            <leg><point x="0" y="0"/><bezier/>'
                       f'<point x="{dx:.4f}" y="{dy:.4f}"/><bezier/></leg>')
            cl = "".join(f'<connect connectorId="{oc}" modelIndex="{oi}" layer="{ol}"/>'
                         for (oi, oc, ol) in links)
            conns.append(f'                        <connector connectorId="{cid}" layer="{it.own_layer}">\n'
                         f'                            {geom}{leg}\n'
                         f'                            <connects>{cl}</connects>\n'
                         f'                        </connector>')
        # legs that are bent but have nothing listed still need their geometry
        connectors = "\n".join(conns)
        bb_layer = "breadboardbreadboard" if it.kind == "breadboard" else "breadboard"
        views = (f'                <breadboardView layer="{bb_layer}">\n'
                 f'                    <geometry z="{z:.4f}" x="{it.x:.4f}" y="{it.y:.4f}">{transform}</geometry>\n'
                 f'                    <connectors>\n{connectors}\n                    </connectors>\n'
                 f'                </breadboardView>\n')
        if it.kind != "breadboard":
            views += (f'                <schematicView layer="schematic">\n'
                      f'                    <geometry z="{z:.4f}" x="{it.sch[0]:.4f}" y="{it.sch[1]:.4f}"/>\n'
                      f'                </schematicView>\n'
                      f'                <pcbView layer="copper0">\n'
                      f'                    <geometry z="{z:.4f}" x="{it.pcb[0]:.4f}" y="{it.pcb[1]:.4f}"/>\n'
                      f'                </pcbView>\n')
        return (f'        <instance moduleIdRef="{it.module_id}" modelIndex="{it.index}" path="{escape(it.path)}">\n'
                f'{props}            <title>{escape(it.title)}</title>\n'
                f'            <views>\n{views}            </views>\n'
                f'        </instance>')

    def save(self, fzz_path, name):
        with zipfile.ZipFile(fzz_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{name}.fz", self.to_xml())
            for p in self.custom.values():
                z.writestr(f"part.{p['file']}.fzp", p["fzp"])
                z.writestr(f"svg.breadboard.{p['file']}.svg", p["breadboard"])
                z.writestr(f"svg.schematic.{p['file']}.svg", p["schematic"])
                z.writestr(f"svg.pcb.{p['file']}.svg", p["pcb"])


class WireSeg:
    kind = "wire"
    own_layer = "breadboardWire"

    def __init__(self, index, p, q, color):
        self.index, self.p, self.q, self.color = index, p, q, color
        self.connects = {}

    def to_xml(self, z):
        conns = []
        for cid in ("connector0", "connector1"):
            cl = "".join(f'<connect connectorId="{oc}" modelIndex="{oi}" layer="{ol}"/>'
                         for (oi, oc, ol) in self.connects.get(cid, []))
            conns.append(f'                        <connector connectorId="{cid}" layer="breadboardWire">\n'
                         f'                            <geometry x="0" y="0"/>\n'
                         f'                            <connects>{cl}</connects>\n'
                         f'                        </connector>')
        dx, dy = self.q[0] - self.p[0], self.q[1] - self.p[1]
        return (f'        <instance moduleIdRef="WireModuleID" modelIndex="{self.index}" path=":/resources/parts/core/wire.fzp">\n'
                f'            <title>Wire{self.index}</title>\n'
                f'            <views>\n'
                f'                <breadboardView layer="breadboardWire">\n'
                f'                    <geometry z="{z:.4f}" x="{self.p[0]:.4f}" y="{self.p[1]:.4f}" x1="0" y1="0" x2="{dx:.4f}" y2="{dy:.4f}" wireFlags="64"/>\n'
                f'                    <wireExtras mils="22.2222" color="{self.color}" opacity="1" banded="0"/>\n'
                f'                    <connectors>\n' + "\n".join(conns) + '\n'
                f'                    </connectors>\n'
                f'                </breadboardView>\n'
                f'            </views>\n'
                f'        </instance>')


def note_xml(idx, x, y, w, h, lines):
    body = "".join(f"<p style=\"margin:0px;\">{escape(l)}</p>" for l in lines)
    html = ('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">'
            '<html><head><meta name="qrichtext" content="1" /><style type="text/css">p, li { white-space: pre-wrap; }</style></head>'
            f'<body style=" font-family:\'Arial\'; font-size:8pt;">{body}</body></html>')
    return (f'        <instance moduleIdRef="NoteModuleID" modelIndex="{idx}" path=":/resources/parts/core/note.fzp">\n'
            f'            <title>Note{idx}</title>\n'
            f'            <text>{escape(html)}</text>\n'
            f'            <views>\n'
            f'                <breadboardView layer="breadboardNote">\n'
            f'                    <geometry z="6.5" x="{x}" y="{y}" width="{w}" height="{h}"/>\n'
            f'                </breadboardView>\n'
            f'            </views>\n'
            f'        </instance>')
