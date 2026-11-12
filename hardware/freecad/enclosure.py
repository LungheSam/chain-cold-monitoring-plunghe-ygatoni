"""Parametric 3D-printed enclosure for the cold chain node (FreeCAD 1.x, Part workbench, headless).

Run from this folder:
    "/c/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" enclosure.py

It writes into exports/:
    <part>.step and <part>.stl   one per printed part, already in its print orientation
    enclosure.FCStd              all parts, placed as assembled (open it in FreeCAD to look around)
    png/*.png                    rendered views (made with matplotlib, no GUI needed)
    report.txt                   size, volume and validity of every part, and the VERIFY list

Every dimension is a constant below: change it and run again. Dimensions that do not come from a
datasheet we trust are marked VERIFY: measure the real part with calipers before printing.

Parts:
    box             main box: Pi 4 + carrier, LCD side, cable glands, grommet, vents, wall tabs
    lid             LCD window, 2 LED holes, buzzer grille + holder, keypad ribbon slot, keypad outline
    dht22_pod       vented pod that holds the DHT22 outside the fridge (ambient air)
    reed_holder     cradle for the reed switch (on the fridge body)
    magnet_holder   cradle for the magnet (on the door)
    solenoid_plate  mounting plate for the solenoid lock, slotted holes to adjust its position
    strike          L-bracket with the window the lock bolt goes into

Print rules used everywhere: wall 2.4 mm, clearance 0.3 mm (per side) for fits, smallest
feature 1.2 mm. Suggested material PETG (copes better than PLA with condensation near a fridge and
with the Pi's heat), 0.2 mm layers, 4 perimeters. No supports needed in the print orientations.
"""
import math
import os

import FreeCAD as App
import Part
from FreeCAD import Vector as V

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:                       # some freecadcmd versions do not set __file__
    HERE = os.getcwd()
OUT = os.path.join(HERE, "exports")

# ======================================================================== parameters (mm)

# ---- print rules
WALL = 2.4            # walls, floor and lid
CLEAR = 0.3           # clearance per side for parts that fit into the print
MIN_FEATURE = 1.2     # nothing thinner or narrower than this
BED = (220, 220, 250)  # printer build volume (Ender-3 class). VERIFY for the printer you use.

# ---- main box (inside dimensions)
IN_X, IN_Y, IN_Z = 185.0, 90.0, 40.0
CORNER_R = 3.0        # rounded outside vertical edges
BOSS_D = 8.0          # lid screw bosses in the 4 inside corners
BOSS_AT = 5.0         # boss centre, from both inside walls
SCREW_PILOT = 2.5     # M3 self-tapping screw into plastic. VERIFY with your screws (2.5-2.6 mm)
SCREW_CLEAR = 3.4     # M3 clearance hole
SCREW_DEPTH = 12.0    # pilot hole depth in the bosses
LIP_W, LIP_H = 1.2, 3.0   # lid lip that locates the lid inside the box opening

# ---- Raspberry Pi 4 (official Raspberry Pi 4 Model B mechanical drawing). VERIFY with calipers.
PI_BOARD = (85.0, 56.0, 1.4)
PI_HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]   # 58 x 49 pattern, M2.5
PI_AT = (10.0, 1.5)   # board corner from the left and front inside walls (ports face the front)
STANDOFF_H, STANDOFF_D = 6.0, 6.0
STANDOFF_PILOT = 2.2  # M2.5 self-tapping. VERIFY with your screws
USBC_FROM_LEFT = 11.2  # USB-C centre from the board's left edge (3.5 + 7.7 on the drawing). VERIFY
USBC_ABOVE_BOARD = 1.6  # USB-C centre above the board top (receptacle about 3.2 mm high). VERIFY
USBC_CUT = (13.0, 8.0)  # opening for the plug's moulding. VERIFY with your power cable's plug

# ---- 16x2 LCD module with PCF8574 backpack (typical 1602 datasheet). VERIFY all of these.
LCD_PCB = (80.0, 36.0)
LCD_HOLES = (75.0, 31.0)  # M3 hole pattern
LCD_BEZEL = (71.2, 24.2)  # metal frame around the glass; the lid window is this + clearance
LCD_BEZEL_H = 7.0         # frame height above the PCB = standoff length under the lid
LCD_CENTER = (142.5, 47.0)  # from the inside front-left corner of the box
LCD_DEPTH = 21.0          # lid to the bottom of the backpack and its pins. VERIFY

# ---- space the electronics need (used only for the fit check, not printed)
PI_STACK_H = 30.0     # Pi board + carrier on 12.5 mm header spacers + its tallest part (screw terminals). VERIFY
PI_PORT_OVERHANG = 3.0  # Ethernet/USB stick out past the board's right edge. VERIFY

# ---- LEDs and buzzer on the lid
LED_D = 5.0                     # 5 mm LEDs. VERIFY
LEDS = [(115.0, 13.0), (130.0, 13.0)]   # red, green (inside coordinates)
BUZZER_D, BUZZER_H = 12.0, 8.5  # small passive buzzer. VERIFY
BUZZER_AT = (165.0, 14.0)
GRILLE_HOLE_D, GRILLE_PITCH, GRILLE_R = 1.6, 3.0, 5.0
RING_WALL, RING_H = 1.6, 4.0    # holder ring under the lid

# ---- 4x4 membrane keypad, stuck on the lid with its own adhesive. VERIFY outline and ribbon.
KEYPAD = (69.0, 77.0)
KEYPAD_CENTER = (54.0, 45.0)    # above the Pi (only the thin ribbon goes inside here)
RIBBON_SLOT = (22.0, 4.0)       # must pass the 8-pin connector on the ribbon's end. VERIFY
RIBBON_SLOT_INSET = 6.0         # slot centre from the keypad's back edge (ribbon side). VERIFY which edge
GROOVE_W, GROOVE_D = 1.2, 0.4   # outline groove on the lid's outer face to place the keypad

# ---- cable entries
GLAND_HOLE_D = 12.5   # PG7 gland thread is 12.5 mm. VERIFY with the gland's datasheet
GLAND_X = [105.0, 125.0, 145.0, 165.0]   # back wall, inside x coordinates
GLAND_USE = ["DS18B20 probe", "reed switch", "12 V sense", "DHT22 pod"]
GLAND_Z = 18.0        # centre above the floor (the gland nut needs about 9 mm around the hole)
GROMMET_HOLE_D = 10.0  # rubber grommet for the lock adapter and solenoid wires. VERIFY with your grommet
GROMMET_AT = (65.0, 18.0)  # right wall: y, z above the floor
VENT_W, VENT_H, VENT_PITCH = 1.6, 16.0, 5.0
VENTS_LEFT = (25.0, 65.0)   # y range on the left wall
VENTS_RIGHT = (12.0, 40.0)  # y range on the right wall
TAB = (20.0, 12.0, 4.0)     # wall/shelf fixing tabs on the back, x, y, thickness
TAB_HOLE_D = 4.5
TAB_X = [25.0, 150.0]       # inside x of the tab centres

# ---- DHT22 pod. Bare DHT22 body is 15.1 x 25 x 7.7 mm (Aosong datasheet). A DHT22 on a small
#      PCB module is bigger: VERIFY which one you have and adjust POD_IN.
POD_IN = (20.0, 34.0, 10.0)   # inside width, height, depth. VERIFY (bare sensor or module?)
POD_SLOT_W = 1.6
POD_FLANGE = 10.0             # fixing flange beyond each end
POD_CABLE_D = 5.0

# ---- reed switch and magnet: surface-mount door contact (MC-38 style). VERIFY both bodies.
REED_BODY = (27.0, 14.0, 10.0)
MAGNET_BODY = (27.0, 14.0, 10.0)
REED_SPACER = 0.0      # extra base thickness to line the reed up with the magnet. VERIFY on the fridge
MAGNET_SPACER = 0.0

# ---- solenoid cabinet lock. No reliable datasheet: VERIFY every value on the real lock.
SOL_PLATE = (70.0, 50.0, 4.0)
SOL_HOLES = (34.0, 32.0)     # lock's mounting-hole pattern (slots allow +-3 mm)
SOL_BOLT = (10.0, 8.0)       # bolt width x height
SOL_BOLT_Z = 12.0            # bolt centre height above the surface the strike is screwed to
FIX_HOLE_D = 4.5             # screws into the fridge body / door

# ======================================================================== derived sizes

OUT_X = IN_X + 2 * WALL
OUT_Y = IN_Y + 2 * WALL
OUT_Z = IN_Z + WALL            # box height (floor + inside height); the lid sits on top
LID_T = WALL

FEATURES = {                   # checked against MIN_FEATURE
    "wall": WALL, "lid lip": LIP_W, "grille hole": GRILLE_HOLE_D, "buzzer ring wall": RING_WALL,
    "vent slot": VENT_W, "keypad groove": GROOVE_W, "pod slot": POD_SLOT_W,
    "grille web": GRILLE_PITCH - GRILLE_HOLE_D,
}


def ix(x):
    """Inside x coordinate -> box coordinate."""
    return WALL + x


def iy(y):
    return WALL + y


# ======================================================================== small helpers

def box(x, y, z, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x, y, z))


def cyl(x, y, z, d, h, direction=V(0, 0, 1)):
    return Part.makeCylinder(d / 2, h, V(x, y, z), direction)


def cut_all(shape, tools):
    for tool in tools:
        shape = shape.cut(tool)
    return shape


def fuse_all(shape, parts):
    for part in parts:
        shape = shape.fuse(part)
    return shape


def stadium(cx, cy, z, length, width, h):
    """Rounded slot along x (for adjustable screw holes)."""
    straight = length - width
    s = box(cx - straight / 2, cy - width / 2, z, straight, width, h)
    s = s.fuse(cyl(cx - straight / 2, cy, z, width, h))
    return s.fuse(cyl(cx + straight / 2, cy, z, width, h))


def rounded_block(dx, dy, dz, r):
    """Block with its 4 vertical edges rounded."""
    b = box(0, 0, 0, dx, dy, dz)
    vertical = [e for e in b.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
    return b.makeFillet(r, vertical)


def boss_centers():
    """Lid screw positions (box coordinates)."""
    return [(ix(x), iy(y)) for x in (BOSS_AT, IN_X - BOSS_AT) for y in (BOSS_AT, IN_Y - BOSS_AT)]


# ======================================================================== main box

def make_box():
    shell = rounded_block(OUT_X, OUT_Y, OUT_Z, CORNER_R)
    shell = shell.cut(box(WALL, WALL, WALL, IN_X, IN_Y, IN_Z + 1))

    # Corner bosses for the lid screws: a cylinder plus a block joining it to both walls
    adds = []
    for cx, cy in boss_centers():
        adds.append(cyl(cx, cy, WALL, BOSS_D, IN_Z))
        x0 = WALL if cx < OUT_X / 2 else cx
        y0 = WALL if cy < OUT_Y / 2 else cy
        adds.append(box(x0, y0, WALL, BOSS_AT, BOSS_AT, IN_Z))

    # Pi standoffs
    for hx, hy in PI_HOLES:
        adds.append(cyl(ix(PI_AT[0] + hx), iy(PI_AT[1] + hy), WALL, STANDOFF_D, STANDOFF_H))

    # Fixing tabs on the back, flush with the bottom
    for tx in TAB_X:
        adds.append(box(ix(tx) - TAB[0] / 2, OUT_Y - 0.01, 0, TAB[0], TAB[1], TAB[2]))
    shell = fuse_all(shell, adds)

    holes = []
    for cx, cy in boss_centers():
        holes.append(cyl(cx, cy, OUT_Z - SCREW_DEPTH, SCREW_PILOT, SCREW_DEPTH + 1))
    for hx, hy in PI_HOLES:
        holes.append(cyl(ix(PI_AT[0] + hx), iy(PI_AT[1] + hy), WALL + 0.6, STANDOFF_PILOT, STANDOFF_H))
    for tx in TAB_X:
        holes.append(cyl(ix(tx), OUT_Y + TAB[1] / 2, -1, TAB_HOLE_D, TAB[2] + 2))

    # USB-C power opening in the front wall, in line with the Pi's port
    ux = ix(PI_AT[0] + USBC_FROM_LEFT)
    uz = WALL + STANDOFF_H + PI_BOARD[2] + USBC_ABOVE_BOARD
    holes.append(box(ux - USBC_CUT[0] / 2, -1, uz - USBC_CUT[1] / 2, USBC_CUT[0], WALL + 2, USBC_CUT[1]))

    # PG7 cable glands in the back wall
    for gx in GLAND_X:
        holes.append(cyl(ix(gx), OUT_Y + 1, WALL + GLAND_Z, GLAND_HOLE_D, WALL + 2, V(0, -1, 0)))

    # Grommet in the right wall
    holes.append(cyl(OUT_X + 1, iy(GROMMET_AT[0]), WALL + GROMMET_AT[1], GROMMET_HOLE_D, WALL + 2, V(-1, 0, 0)))

    # Vent slots in both short walls
    vent_z = WALL + (IN_Z - VENT_H) / 2 - 4
    for wall_x, (y0, y1) in ((-1, VENTS_LEFT), (OUT_X - WALL - 1, VENTS_RIGHT)):
        y = y0
        while y + VENT_W <= y1:
            holes.append(box(wall_x, iy(y), vent_z, WALL + 2, VENT_W, VENT_H))
            y += VENT_PITCH
    return cut_all(shell, holes)


# ======================================================================== lid (built as assembled: top face up)

def make_lid():
    plate = rounded_block(OUT_X, OUT_Y, LID_T, CORNER_R)

    # Lip that drops into the box opening, notched around the corner bosses
    lip = box(WALL + CLEAR, WALL + CLEAR, -LIP_H, IN_X - 2 * CLEAR, IN_Y - 2 * CLEAR, LIP_H)
    lip = lip.cut(box(WALL + CLEAR + LIP_W, WALL + CLEAR + LIP_W, -LIP_H - 1,
                      IN_X - 2 * (CLEAR + LIP_W), IN_Y - 2 * (CLEAR + LIP_W), LIP_H + 2))
    notch = BOSS_AT + BOSS_D / 2 + CLEAR       # square notch in each corner, clear of the boss
    for cx, cy in boss_centers():
        nx = WALL if cx < OUT_X / 2 else OUT_X - WALL - notch
        ny = WALL if cy < OUT_Y / 2 else OUT_Y - WALL - notch
        lip = lip.cut(box(nx, ny, -LIP_H - 1, notch, notch, LIP_H + 2))
    adds = [lip]

    # LCD standoffs (the bezel then touches the lid's inside face)
    lcx, lcy = ix(LCD_CENTER[0]), iy(LCD_CENTER[1])
    lcd_holes = [(lcx + sx * LCD_HOLES[0] / 2, lcy + sy * LCD_HOLES[1] / 2) for sx in (-1, 1) for sy in (-1, 1)]
    for hx, hy in lcd_holes:
        adds.append(cyl(hx, hy, -LCD_BEZEL_H, STANDOFF_D, LCD_BEZEL_H + 0.01))

    # Buzzer holder ring
    bx, by = ix(BUZZER_AT[0]), iy(BUZZER_AT[1])
    ring_in = BUZZER_D + 2 * CLEAR
    ring = cyl(bx, by, -RING_H, ring_in + 2 * RING_WALL, RING_H + 0.01).cut(cyl(bx, by, -RING_H - 1, ring_in, RING_H + 1))
    adds.append(ring)
    lid = fuse_all(plate, adds)

    holes = []
    for cx, cy in boss_centers():
        holes.append(cyl(cx, cy, -1, SCREW_CLEAR, LID_T + 2))
    for hx, hy in lcd_holes:
        holes.append(cyl(hx, hy, -LCD_BEZEL_H - 1, SCREW_PILOT, LCD_BEZEL_H + 0.5))
    # LCD window
    wx, wy = LCD_BEZEL[0] + 2 * CLEAR, LCD_BEZEL[1] + 2 * CLEAR
    holes.append(box(lcx - wx / 2, lcy - wy / 2, -1, wx, wy, LID_T + 2))
    # LEDs
    for lx, ly in LEDS:
        holes.append(cyl(ix(lx), iy(ly), -1, LED_D + CLEAR, LID_T + 2))
    # Buzzer grille: holes on a square grid inside a circle
    n = int(GRILLE_R // GRILLE_PITCH)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            if math.hypot(i * GRILLE_PITCH, j * GRILLE_PITCH) <= GRILLE_R:
                holes.append(cyl(bx + i * GRILLE_PITCH, by + j * GRILLE_PITCH, -1, GRILLE_HOLE_D, LID_T + 2))
    # Keypad ribbon slot, under the keypad near its back edge
    kx, ky = ix(KEYPAD_CENTER[0]), iy(KEYPAD_CENTER[1])
    sy = ky + KEYPAD[1] / 2 - RIBBON_SLOT_INSET
    holes.append(box(kx - RIBBON_SLOT[0] / 2, sy - RIBBON_SLOT[1] / 2, -1, RIBBON_SLOT[0], RIBBON_SLOT[1], LID_T + 2))
    # Keypad outline groove on the outer face
    outer = box(kx - KEYPAD[0] / 2 - CLEAR - GROOVE_W, ky - KEYPAD[1] / 2 - CLEAR - GROOVE_W, LID_T - GROOVE_D,
                KEYPAD[0] + 2 * (CLEAR + GROOVE_W), KEYPAD[1] + 2 * (CLEAR + GROOVE_W), GROOVE_D + 1)
    inner = box(kx - KEYPAD[0] / 2 - CLEAR, ky - KEYPAD[1] / 2 - CLEAR, LID_T - GROOVE_D - 1,
                KEYPAD[0] + 2 * CLEAR, KEYPAD[1] + 2 * CLEAR, GROOVE_D + 3)
    holes.append(outer.cut(inner))
    return cut_all(lid, holes)


# ======================================================================== DHT22 pod (print: open back on the bed)

def make_pod():
    ox, oy, oz = POD_IN[0] + 2 * WALL, POD_IN[1] + 2 * WALL, POD_IN[2] + WALL
    pod = box(0, 0, 0, ox, oy, oz).cut(box(WALL, WALL, -1, POD_IN[0], POD_IN[1], POD_IN[2] + 1))
    # Fixing flanges at both ends, flat on the wall
    pod = pod.fuse(box(0, -POD_FLANGE, 0, ox, oy + 2 * POD_FLANGE, WALL))
    holes = [cyl(ox / 2, -POD_FLANGE / 2, -1, SCREW_CLEAR, WALL + 2),
             cyl(ox / 2, oy + POD_FLANGE / 2, -1, SCREW_CLEAR, WALL + 2)]
    # Louvre slots across the front face and down both sides, so air moves through
    n_slots = 5
    pitch = POD_IN[1] / (n_slots + 1)
    for k in range(1, n_slots + 1):
        y = WALL + k * pitch - POD_SLOT_W / 2
        holes.append(box(WALL + 2, y, POD_IN[2] - 1, POD_IN[0] - 4, POD_SLOT_W, WALL + 2))
        holes.append(box(-1, y, WALL + 1.0, ox + 2, POD_SLOT_W, POD_IN[2] - 3.0))
    # Cable notch in the bottom end, open towards the wall
    holes.append(box(ox / 2 - POD_CABLE_D / 2, -1, -1, POD_CABLE_D, WALL + 2, POD_CABLE_D + 1))
    return cut_all(pod, holes)


# ======================================================================== reed switch / magnet cradles

def make_cradle(body, spacer):
    """Base with two side rails that hold the body, zip-tie slots and two screw holes."""
    length, width, height = body
    channel = width + 2 * CLEAR
    rail = WALL
    tie_gap = 1.0            # rail -> zip-tie slot
    base_w = channel + 2 * (rail + tie_gap + POD_SLOT_W + MIN_FEATURE)
    base_l = length + 2 * CLEAR + 2 * 12.0      # 12 mm screw tab at each end
    base_t = 3.0 + spacer
    cy = base_w / 2
    part = box(0, 0, 0, base_l, base_w, base_t)
    rail_h = height * 0.6
    rail_l = length + 2 * CLEAR
    x0 = (base_l - rail_l) / 2
    part = part.fuse(box(x0, cy - channel / 2 - rail, base_t - 0.01, rail_l, rail, rail_h))
    part = part.fuse(box(x0, cy + channel / 2, base_t - 0.01, rail_l, rail, rail_h))
    holes = [cyl(6.0, cy, -1, SCREW_CLEAR, base_t + 2), cyl(base_l - 6.0, cy, -1, SCREW_CLEAR, base_t + 2)]
    tie_y = channel / 2 + rail + tie_gap
    for side in (-1, 1):
        y = cy + side * (tie_y + POD_SLOT_W / 2) - POD_SLOT_W / 2
        holes.append(box(base_l / 2 - 2.0, y, -1, 4.0, POD_SLOT_W, base_t + 2))
    return cut_all(part, holes)


# ======================================================================== solenoid lock plate and strike

def make_solenoid_plate():
    px, py, pt = SOL_PLATE
    plate = rounded_block(px, py, pt, 3.0)
    holes = []
    for sx in (-1, 1):
        for sy in (-1, 1):   # slotted holes: the lock can slide +-3 mm to line up with the strike
            holes.append(stadium(px / 2 + sx * SOL_HOLES[0] / 2, py / 2 + sy * SOL_HOLES[1] / 2, -1,
                                 SCREW_CLEAR + 6.0, SCREW_CLEAR, pt + 2))
        holes.append(cyl(px / 2 + sx * (px / 2 - 6.0), py / 2, -1, FIX_HOLE_D, pt + 2))
    return cut_all(plate, holes)


def make_strike():
    width, base_d, t = 34.0, 18.0, 4.0
    upright_h = SOL_BOLT_Z + SOL_BOLT[1] / 2 + 6.0
    part = box(0, 0, 0, width, base_d, t).fuse(box(0, base_d - t, 0, width, t, upright_h))
    wx, wz = SOL_BOLT[0] + 2 * CLEAR, SOL_BOLT[1] + 2 * CLEAR
    holes = [box(width / 2 - wx / 2, base_d - t - 1, SOL_BOLT_Z - wz / 2, wx, t + 2, wz)]
    for x in (7.0, width - 7.0):
        holes.append(cyl(x, (base_d - t) / 2, -1, FIX_HOLE_D, t + 2))
    return cut_all(part, holes)


# ======================================================================== checks, export, render

def to_print_orientation(name, shape):
    s = shape.copy()
    if name == "lid":                      # outer face on the bed: smooth top, no supports
        s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    bb = s.BoundBox
    s.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    return s


def check(parts):
    """Returns report lines; raises an error if a rule is broken."""
    for feature, size in FEATURES.items():
        if size < MIN_FEATURE - 1e-9:
            raise ValueError("%s is %.2f mm, below the %.1f mm minimum" % (feature, size, MIN_FEATURE))
    lines = ["All checked features >= %.1f mm: %s" % (MIN_FEATURE, ", ".join(
        "%s %.1f" % kv for kv in FEATURES.items())), ""]
    lines.append("%-15s %22s %10s %6s %7s %s" % ("part", "print size (mm)", "vol (cm3)", "valid", "solids", "fits bed"))
    for name, shape in parts.items():
        bb = shape.BoundBox
        size = (bb.XLength, bb.YLength, bb.ZLength)
        # fits the bed if the footprint fits (either way round) and the height fits
        fits = all(a <= b for a, b in zip(sorted(size[:2]), sorted(BED[:2]))) and size[2] <= BED[2]
        valid = shape.isValid()
        if not valid or len(shape.Solids) != 1 or not fits:
            raise ValueError("part %s: valid=%s solids=%d fits=%s" % (name, valid, len(shape.Solids), fits))
        lines.append("%-15s %22s %10.1f %6s %7d %s" % (name, "%.1f x %.1f x %.1f" % size,
                                                      shape.Volume / 1000, valid, len(shape.Solids), fits))
    return lines


def fit_check(box_shape, lid_on_box):
    """Stand-in blocks for the Pi stack, LCD module and buzzer must not hit the box, the lid or
    each other. Returns report lines; raises an error on a collision."""
    lcx, lcy = ix(LCD_CENTER[0]), iy(LCD_CENTER[1])
    blocks = {
        "Pi + carrier": box(ix(PI_AT[0]), iy(PI_AT[1]), WALL + STANDOFF_H,
                            PI_BOARD[0] + PI_PORT_OVERHANG, PI_BOARD[1], PI_STACK_H),
        "LCD module": box(lcx - LCD_PCB[0] / 2, lcy - LCD_PCB[1] / 2, OUT_Z - LCD_DEPTH,
                          LCD_PCB[0], LCD_PCB[1], LCD_DEPTH - LCD_BEZEL_H),
        "buzzer": cyl(ix(BUZZER_AT[0]), iy(BUZZER_AT[1]), OUT_Z - BUZZER_H, BUZZER_D, BUZZER_H),
    }
    solids = dict(blocks, box=box_shape, lid=lid_on_box)
    names = list(solids)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a in blocks or b in blocks:
                overlap = solids[a].common(solids[b]).Volume
                if overlap > 0.01:
                    raise ValueError("fit check: %s hits %s (%.1f mm3)" % (a, b, overlap))
    pi_top = WALL + STANDOFF_H + PI_STACK_H
    return ["Fit check passed: Pi + carrier, LCD module and buzzer clear the box, the lid and each other.",
            "Space left above the Pi stack: %.1f mm. Below the LCD module: %.1f mm."
            % (OUT_Z - pi_top, OUT_Z - LCD_DEPTH - WALL)]


def export(parts, assembled):
    import MeshPart
    os.makedirs(os.path.join(OUT, "png"), exist_ok=True)
    for name, shape in parts.items():
        shape.exportStep(os.path.join(OUT, name + ".step"))
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05, AngularDeflection=0.25, Relative=False)
        mesh.write(os.path.join(OUT, name + ".stl"))
    doc = App.newDocument("Enclosure")
    for name, shape in assembled.items():
        doc.addObject("Part::Feature", name).Shape = shape
    doc.recompute()
    path = os.path.join(OUT, "enclosure.FCStd")
    if os.path.exists(path):
        os.remove(path)          # otherwise FreeCAD keeps a .FCBak backup of the old file
    doc.saveAs(path)
    App.closeDocument(doc.Name)


COLORS = {"box": (0.80, 0.84, 0.90), "lid": (0.55, 0.70, 0.88), "dht22_pod": (0.95, 0.85, 0.55),
          "reed_holder": (0.70, 0.88, 0.70), "magnet_holder": (0.95, 0.70, 0.70),
          "solenoid_plate": (0.80, 0.75, 0.95), "strike": (0.85, 0.85, 0.85)}


def render(shapes, path, title, elev=28, azim=-60):
    """Draw shapes with simple light shading (matplotlib, no FreeCAD GUI needed)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    light = np.array([-0.35, -0.5, 1.0])
    light /= np.linalg.norm(light)
    fig = plt.figure(figsize=(9, 6.5), dpi=110)
    ax = fig.add_subplot(projection="3d")
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for name, shape in shapes:
        points, facets = shape.tessellate(0.25)
        pts = np.array([[p.x, p.y, p.z] for p in points])
        tris = pts[np.array(facets)]
        normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12
        shade = 0.35 + 0.65 * np.abs(normals @ light)
        colors = np.clip(np.outer(shade, COLORS.get(name, (0.8, 0.8, 0.8))), 0, 1)
        ax.add_collection3d(Poly3DCollection(tris, facecolors=colors, edgecolors="none"))
        lo, hi = np.minimum(lo, pts.min(axis=0)), np.maximum(hi, pts.max(axis=0))
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(hi - lo)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def verify_list():
    """The parameters to measure, read from this file: every parameter whose comment says VERIFY,
    and every parameter in a section whose heading says VERIFY."""
    with open(os.path.join(HERE, "enclosure.py"), encoding="utf-8") as f:
        lines = f.read().split("# ======")[1].splitlines()   # the parameters block only
    result, section_verify = [], False
    for line in lines:
        if line.startswith("# ----"):
            section_verify = "VERIFY" in line
            result.append(line[7:].strip())
        elif "=" in line and not line.startswith((" ", "#")) and (section_verify or "VERIFY" in line):
            result.append("    " + line.strip())
    # keep only headings that have parameters under them
    return [l for i, l in enumerate(result) if l.startswith("    ") or
            (i + 1 < len(result) and result[i + 1].startswith("    "))]


def moved(shape, x, y, z):
    s = shape.copy()
    s.translate(V(x, y, z))
    return s


def main():
    print("Building parts...")
    built = {
        "box": make_box(),
        "lid": make_lid(),
        "dht22_pod": make_pod(),
        "reed_holder": make_cradle(REED_BODY, REED_SPACER),
        "magnet_holder": make_cradle(MAGNET_BODY, MAGNET_SPACER),
        "solenoid_plate": make_solenoid_plate(),
        "strike": make_strike(),
    }
    printed = {name: to_print_orientation(name, s) for name, s in built.items()}
    report = check(printed)
    report += [""] + fit_check(built["box"], moved(built["lid"], 0, 0, OUT_Z))

    # Positions for the FCStd and the overview picture: lid on the box, small parts beside it
    assembled = {
        "box": built["box"],
        "lid": moved(built["lid"], 0, 0, OUT_Z),
        "dht22_pod": moved(built["dht22_pod"], OUT_X + 25, 20, 0),
        "reed_holder": moved(built["reed_holder"], 0, -45, 0),
        "magnet_holder": moved(built["magnet_holder"], 60, -45, 0),
        "solenoid_plate": moved(built["solenoid_plate"], 120, -70, 0),
        "strike": moved(built["strike"], OUT_X + 10, -60, 0),
    }
    print("Exporting STEP, STL and FCStd to", OUT)
    export(printed, assembled)

    print("Rendering PNG views...")
    png = os.path.join(OUT, "png")
    exploded = dict(assembled, lid=moved(built["lid"], 0, 0, OUT_Z + 35))
    render(list(exploded.items()), os.path.join(png, "overview.png"), "All parts (lid lifted)")
    render([("box", built["box"])], os.path.join(png, "box_front.png"), "Box: front (USB-C) and left vents", azim=-120)
    render([("box", built["box"])], os.path.join(png, "box_back.png"), "Box: back (glands, tabs) and right wall", azim=60)
    render([("lid", built["lid"])], os.path.join(png, "lid_top.png"), "Lid: outer face", elev=70, azim=-90)
    render([("lid", printed["lid"])], os.path.join(png, "lid_inside.png"), "Lid: inside (as printed)", elev=55, azim=-60)
    small = [(n, moved(printed[n], x, 0, 0)) for n, x in
             (("dht22_pod", 0), ("reed_holder", 40), ("magnet_holder", 100), ("solenoid_plate", 160), ("strike", 245))]
    render(small, os.path.join(png, "small_parts.png"), "Pod, reed + magnet holders, lock plate, strike (as printed)")

    verify = verify_list()
    with open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8") as f:
        f.write("Enclosure report (generated by enclosure.py, FreeCAD %s)\n\n" % ".".join(App.Version()[:3]))
        f.write("\n".join(report) + "\n\nCable glands (back wall, left to right seen from the front): %s\n"
                % ", ".join(GLAND_USE))
        f.write("\nParameters to VERIFY before printing:\n" + "\n".join("  " + v for v in verify) + "\n")
    print("\n".join(report))
    print("Done.")


main()
