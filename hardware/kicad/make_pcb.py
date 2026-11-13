"""Builds carrier.kicad_pcb from the table in carrier.py: places the footprints, routes the tracks
with router.py, pours GND on both layers, and adds silkscreen labels.

Run with KiCad's own Python (it has the pcbnew module):
    "/c/Program Files/KiCad/10.0/bin/python.exe" make_pcb.py

Board: Raspberry Pi HAT size, 65 x 56.5 mm, 2 layers, 1.6 mm, 1 oz copper, M2.5 holes on 58 x 49 mm
(Raspberry Pi HAT mechanical spec, VERIFY with calipers on your Pi).
"""
import math
import os

import pcbnew

from carrier import PARTS, nets
from make_schematic import uid
from router import CLEARANCE, VIA_D, VIA_DRILL, Router

HERE = os.path.dirname(os.path.abspath(__file__))
FP_DIR = "C:/Program Files/KiCad/10.0/share/kicad/footprints/"

BOARD_W, BOARD_H, CORNER_R = 65.0, 56.5, 3.0
ORIGIN = (100.0, 100.0)          # where the board sits on KiCad's page
# Pi header pin 1, seen from the top: 3.5 mm in from the top edge (rows at 2.23 / 4.77 mm), centred
# between the mounting holes (pins from x = 8.37 to 56.63 mm). VERIFY against your Pi before soldering.
PI_PIN1 = (8.37, 4.77)
PITCH = 0.254                    # routing grid, lined up with the Pi header (a track fits between two pins)
GRID_X0, GRID_Y0 = PI_PIN1[0] % PITCH, PI_PIN1[1] % PITCH

# ---- track widths (mm). Lock current about 1 A (VERIFY by measuring the solenoid):
# IPC-2221 outer layer, 1 oz (35 um), 10 C rise: area = (I / (0.048 * 10^0.44))^(1/0.725) = 16.3 mil^2
# -> width 16.3 / 1.378 mil = 11.8 mil = 0.30 mm. We use 1.0 mm: 3x margin for the pull-in surge.
WIDTH = {"+5V_LOCK": 1.0, "LOCK_N": 1.0, "+5V": 0.4, "+3V3": 0.3, "GND": 0.3}
SIGNAL_WIDTH = 0.25
LOCK_RETURN = [("GND", 1.0, ["J10.2", "Q2.2"])]   # the lock current's way back, also 1.0 mm

# ---- placement: ref -> (x, y, direction of pad 1 -> pad 2) in board mm, top view, y down.
# For THT parts (x, y) is pad 1; for SOT-23 it is the centre (direction None = as in the library).
PLACE = {
    # Row of sensor/LCD/LED connectors under the header (cables go up from vertical JST-XH)
    "J2": (4.6, 11.5, "right"), "J3": (15.8, 11.5, "right"), "J4": (27.0, 11.5, "right"),
    "J7": (36.0, 11.5, "right"), "J5": (50.0, 11.5, "right"),
    # Keypad and spare headers along the right edge
    "J8": (61.8, 19.0, "down"), "J12": (61.8, 41.0, "down"),
    # Pull-ups, LED resistors, buzzer driver, level shifter
    "R1": (5.0, 27.4, "up"), "R2": (9.5, 27.4, "up"),
    "J6": (14.5, 22.0, "right"), "D2": (21.0, 31.5, "right"),
    "R6": (28.0, 27.4, "up"), "Q1": (31.5, 23.0, "right"),
    "R11": (38.0, 27.4, "up"), "R12": (42.0, 27.4, "up"),
    "Q3": (45.5, 19.5, None), "Q4": (45.5, 25.0, None),
    "R7": (49.5, 27.4, "up"), "R8": (53.5, 27.4, "up"),
    # 12 V sense (bottom left)
    "R3": (5.0, 41.0, "up"), "R4": (9.5, 41.0, "up"), "R5": (14.0, 41.0, "up"),
    "C1": (18.5, 39.0, "up"), "D1": (23.0, 37.0, None),
    "J9": (10.0, 50.7, "right"),
    # Lock (bottom right)
    "J10": (29.0, 50.7, "right"), "J11": (41.0, 50.7, "right"),
    "D3": (34.0, 40.0, "right"), "Q2": (49.0, 37.0, None),
    "R9": (53.0, 43.0, "up"), "R10": (57.0, 43.0, "up"),
    # Mounting holes: Pi HAT pattern, 3.5 mm from the edges
    "H1": (3.5, 3.5, None), "H2": (61.5, 3.5, None), "H3": (3.5, 52.5, None), "H4": (61.5, 52.5, None),
}

# Silkscreen label for each connector: reference + name, then the pins in order (pin 1 first)
LABELS = {
    "J2": "J2 DS18B20\n3V3 DQ GND", "J3": "J3 DHT22\n3V3 DAT GND", "J4": "J4 REED\nSW GND",
    "J7": "J7 LCD I2C\nGND 5V SDA SCL", "J5": "J5 LEDS\nRED GRN GND", "J6": "J6 BUZZER\n5V BUZ-",
    "J9": "J9 12V SENSE\n+12V GND", "J10": "J10 LOCK 5V IN\n+5V GND", "J11": "J11 SOLENOID\n+ -",
    "J8": "J8 KEYPAD R1-R4 C1-C4", "J12": "J12 IO26 GND",
}
LABEL_ABOVE = ("J9", "J10", "J11")       # screw terminals sit on the bottom edge
LABEL_LEFT = ("J8", "J12")              # vertical headers on the right edge


def mm(v):
    return pcbnew.FromMM(v)


def at(x, y):
    """Board mm -> KiCad position."""
    return pcbnew.VECTOR2I(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))


def snap(v, v0):
    return v0 + round((v - v0) / PITCH) * PITCH


def pad_xy(pad):
    p = pad.GetPosition()
    return pcbnew.ToMM(p.x) - ORIGIN[0], pcbnew.ToMM(p.y) - ORIGIN[1]


def load_footprint(ref):
    lib, name = PARTS[ref][2].split(":")
    fp = pcbnew.FootprintLoad(FP_DIR + lib + ".pretty", name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def orient(fp, direction):
    """Rotate so that pad 2 lies `direction` of pad 1."""
    want = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}[direction]
    for angle in (0, 90, 180, 270):
        fp.SetOrientationDegrees(angle)
        p1, p2 = [pad_xy(p) for p in sorted(fp.Pads(), key=lambda p: p.GetNumber()) if p.GetNumber() in ("1", "2")][:2]
        d = (p2[0] - p1[0], p2[1] - p1[1])
        if d[0] * want[0] + d[1] * want[1] > 0.9 * math.hypot(*d):
            return
    raise ValueError("cannot orient " + fp.GetReference())


def place_pi_socket(board):
    """J1 goes on the bottom side, so that pin n sits under the Pi's pin n."""
    fp = load_footprint("J1")
    board.Add(fp)
    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for angle in (0, 90, 180, 270):
        fp.SetOrientationDegrees(angle)
        fp.SetPosition(at(0, 0))
        pads = {p.GetNumber(): pad_xy(p) for p in fp.Pads()}
        shift = (PI_PIN1[0] - pads["1"][0], PI_PIN1[1] - pads["1"][1])
        fp.SetPosition(at(shift[0], shift[1]))
        pads = {p.GetNumber(): pad_xy(p) for p in fp.Pads()}
        pin2_out = abs(pads["2"][0] - PI_PIN1[0]) < 0.01 and abs(pads["2"][1] - (PI_PIN1[1] - 2.54)) < 0.01
        pin3_right = abs(pads["3"][0] - (PI_PIN1[0] + 2.54)) < 0.01
        if pin2_out and pin3_right:
            return fp
    raise ValueError("cannot place the Pi socket")


def outline(board):
    """Rounded-rectangle board edge on Edge.Cuts."""
    r, w, h = CORNER_R, BOARD_W, BOARD_H
    lines = [((r, 0), (w - r, 0)), ((w, r), (w, h - r)), ((w - r, h), (r, h)), ((0, h - r), (0, r))]
    for a, b in lines:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(at(*a))
        s.SetEnd(at(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)
    for cx, cy, a0 in ((w - r, r, -90), (w - r, h - r, 0), (r, h - r, 90), (r, r, 180)):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        pts = [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in (a0, a0 + 45, a0 + 90)]
        s.SetArcGeometry(at(*pts[0]), at(*pts[1]), at(*pts[2]))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)


def silk_text(board, text, x, y, size=0.8, angle=0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(at(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(0.15 if size >= 1 else 0.12))
    t.SetTextAngleDegrees(angle)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def gnd_zone(board, net, layer):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    poly = z.Outline()
    poly.NewOutline()
    for x, y in ((0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)):
        poly.Append(mm(ORIGIN[0] + x), mm(ORIGIN[1] + y))
    z.SetLocalClearance(mm(0.3))
    z.SetMinThickness(mm(0.25))
    z.SetThermalReliefGap(mm(0.4))
    z.SetThermalReliefSpokeWidth(mm(0.5))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)


def main():
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    tb = board.GetTitleBlock()
    tb.SetTitle("Cold chain carrier board (Raspberry Pi HAT)")
    tb.SetRevision("1")
    tb.SetCompany("CMU Africa 04-645 IoT, Fall 2026")
    outline(board)
    # Origin for the pick-and-place file: bottom-left corner of the board (what assembly houses expect)
    board.GetDesignSettings().SetAuxOrigin(at(0, BOARD_H))

    # Nets
    # Local labels on the root sheet make nets called "/NAME" in KiCad, so the board uses that too
    net_items = {}
    for name in nets():
        net_items[name] = pcbnew.NETINFO_ITEM(board, "/" + name)
        board.Add(net_items[name])

    # Footprints
    footprints = {"J1": place_pi_socket(board)}
    for ref, (x, y, direction) in PLACE.items():
        fp = load_footprint(ref)
        board.Add(fp)
        if direction:
            orient(fp, direction)
        if ref.startswith("H"):
            fp.SetPosition(at(x, y))                 # holes stay exactly on the HAT pattern
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        else:
            fp.SetPosition(at(snap(x, GRID_X0), snap(y, GRID_Y0)))
        footprints[ref] = fp

    for ref, fp in footprints.items():
        _, value, _, pin_nets, _, note = PARTS[ref]
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetPath(pcbnew.KIID_PATH("/" + uid("sym " + ref)))   # links it to the schematic symbol
        for field in fp.GetFields():
            if field.GetName() == "Description":
                field.SetText(note)                  # same text as the schematic symbol
        for pad in fp.Pads():
            if pad.GetNumber() in pin_nets:
                pad.SetNet(net_items[pin_nets[pad.GetNumber()]])
            elif ref == "J1":                        # unused Pi pins: same name KiCad gives them
                name = "unconnected-(J1-Pin_%s-Pad%s)" % (pad.GetNumber(), pad.GetNumber())
                net_items[name] = pcbnew.NETINFO_ITEM(board, name)
                board.Add(net_items[name])
                pad.SetNet(net_items[name])
        if ref in LABELS or ref.startswith("H"):
            fp.Reference().SetLayer(pcbnew.F_Fab)  # connector labels say it instead; holes need none
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))   # small: the board is crowded
        fp.Reference().SetTextThickness(mm(0.12))

    # ---- routing
    router = Router(BOARD_W, BOARD_H, CORNER_R, PITCH, GRID_X0, GRID_Y0)
    pad_index = {}
    shapes = {pcbnew.PAD_SHAPE_CIRCLE: "circle", pcbnew.PAD_SHAPE_OVAL: "oval"}
    for ref, fp in footprints.items():
        for pad in fp.Pads():
            x, y = pad_xy(pad)
            size = pad.GetSize(pcbnew.F_Cu) if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH else pad.GetDrillSize()
            w, h = pcbnew.ToMM(size.x), pcbnew.ToMM(size.y)
            if round(pad.GetOrientationDegrees()) % 180 == 90:
                w, h = h, w
            smd = pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
            layers = ((0,) if fp.GetLayer() == pcbnew.F_Cu else (1,)) if smd else (0, 1)
            net = pad.GetNetname().lstrip("/") or "(none)%s" % ref
            router.add_pad(net, layers, x, y, w, h, shapes.get(pad.GetShape(pcbnew.F_Cu), "rect"))
            pad_index["%s.%s" % (ref, pad.GetNumber())] = len(router.items) - 1

    all_nets = nets()
    order = [("+5V_LOCK", None), ("LOCK_N", None)] + [(n, w, pads) for n, w, pads in LOCK_RETURN]
    order += [("+3V3", None), ("+5V", None)]
    signals = [n for n in all_nets if n not in WIDTH]
    signals.sort(key=lambda n: len(all_nets[n]))
    order += [(n, None) for n in signals] + [("GND", None)]

    report = []
    for item in order:
        name = item[0]
        width = item[1] or WIDTH.get(name, SIGNAL_WIDTH)
        pads = item[2] if len(item) > 2 else ["%s.%s" % p for p in all_nets[name]]
        failed = router.connect(name, width, [pad_index[p] for p in pads])
        report.append("%-10s %d pads, width %.2f mm%s" % (name, len(pads), width,
                                                         "" if not failed else ", %d NOT ROUTED" % failed))
    print("\n".join(report))

    print("Adding tracks and vias...")
    for net, layer, corners, width in router.tracks:
        for a, b in zip(corners, corners[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(at(*a))
            t.SetEnd(at(*b))
            t.SetWidth(mm(width))
            t.SetLayer(pcbnew.F_Cu if layer == 0 else pcbnew.B_Cu)
            t.SetNet(net_items[net])
            board.Add(t)
    for net, x, y in router.vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(at(x, y))
        v.SetDrill(mm(VIA_DRILL))
        v.SetWidth(mm(VIA_D))
        v.SetNet(net_items[net])
        board.Add(v)

    print("Pouring GND...")
    # ---- GND pour on both layers
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        gnd_zone(board, net_items["GND"], layer)
    # (the zones are filled by `kicad-cli pcb drc --refill-zones --save-board` in build.sh: the
    #  zone filler crashes when called from a stand-alone script in KiCad 10.0.3)

    print("Silkscreen...")
    # ---- silkscreen help
    for ref, text in LABELS.items():
        box = footprints[ref].GetCourtyard(pcbnew.F_CrtYd).BBox()
        left, right = pcbnew.ToMM(box.GetLeft()) - ORIGIN[0], pcbnew.ToMM(box.GetRight()) - ORIGIN[0]
        top, bottom = pcbnew.ToMM(box.GetTop()) - ORIGIN[1], pcbnew.ToMM(box.GetBottom()) - ORIGIN[1]
        if ref in LABEL_LEFT:
            silk_text(board, text, left - 0.8, (top + bottom) / 2, angle=90)
        elif ref in LABEL_ABOVE:
            silk_text(board, text, (left + right) / 2, top - 1.4)
        else:
            silk_text(board, text, (left + right) / 2, bottom + 1.4)
    silk_text(board, "COLD CHAIN CARRIER v1", 36.5, 34.0, size=1.2)
    silk_text(board, "CMU Africa IoT 2026", 36.5, 36.0, size=0.9)
    silk_text(board, "Pi socket underneath: pin 1 here", PI_PIN1[0] + 2.0, 7.2, size=0.8, layer=pcbnew.B_SilkS)

    path = os.path.join(HERE, "carrier.kicad_pcb")
    pcbnew.SaveBoard(path, board)
    print("Wrote", path)


if __name__ == "__main__":
    main()
