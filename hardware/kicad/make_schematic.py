"""Writes carrier.kicad_sch from the table in carrier.py.

Run with KiCad's own Python (it has nothing special to import, any Python 3 works):
    "/c/Program Files/KiCad/10.0/bin/python.exe" make_schematic.py

Every pin gets a net label at its connection point (that is how the nets are joined, no wires),
unused Pi pins get a no-connect flag, and the parts are laid out in labelled functional blocks.
The symbols are copied from KiCad's installed libraries into the file, as KiCad itself does.
"""
import os
import re
import uuid
from datetime import date

from carrier import GROUP_TITLES, PARTS

SYMBOL_DIR = "C:/Program Files/KiCad/10.0/share/kicad/symbols/"
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = "carrier"
NS = uuid.UUID("6f1c2a3e-0000-4000-8000-00000000c0de")   # fixed, so the UUIDs stay the same every run


def uid(name):
    return str(uuid.uuid5(NS, name))


ROOT_UUID = uid("root")


# ---------------------------------------------------------------- reading symbols from the library

def find_block(text, start):
    """Text of the s-expression that starts at `start` (an opening bracket)."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("unbalanced brackets")


def library_symbol(lib, name, _cache={}):
    if lib not in _cache:
        with open(SYMBOL_DIR + lib + ".kicad_sym", encoding="utf-8") as f:
            _cache[lib] = f.read()
    text = _cache[lib]
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(name), text)
    if not m:
        raise KeyError("%s:%s not in the library" % (lib, name))
    return find_block(text, m.start() + 2)


def properties(block):
    return [find_block(block, m.start()) for m in re.finditer(r"\(property ", block)]


def flat_symbol(lib_id):
    """The symbol as it must appear in the schematic's lib_symbols: named 'Lib:Name', with a derived
    symbol ('extends') merged into its parent's drawing and pins."""
    lib, name = lib_id.split(":")
    block = library_symbol(lib, name)
    parent = re.search(r'\(extends "([^"]+)"\)', block)
    if parent:
        base = library_symbol(lib, parent.group(1))
        child_keys = {re.match(r'\(property "([^"]*)"', p).group(1) for p in properties(block)}
        for prop in properties(base):            # the child's fields replace the parent's; others stay
            if re.match(r'\(property "([^"]*)"', prop).group(1) in child_keys:
                base = base.replace(prop, "", 1)
        child_props = "\n\t\t".join(properties(block))
        base = base.replace("(symbol \"%s\"" % parent.group(1), "(symbol \"%s\"\n\t\t%s" % (name, child_props), 1)
        base = base.replace('(symbol "%s_' % parent.group(1), '(symbol "%s_' % name)   # drawing units
        block = base
    return block.replace('(symbol "%s"' % name, '(symbol "%s"' % lib_id, 1)


def symbol_pins(block):
    """pin number -> (x, y, angle) of its connection point, in symbol coordinates (y up)."""
    pins = {}
    for m in re.finditer(r"\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)", block):
        pin_block = find_block(block, m.start())
        number = re.search(r'\(number "([^"]*)"', pin_block).group(1)
        pins[number] = (float(m.group(1)), float(m.group(2)), int(m.group(3)))
    return pins


# ---------------------------------------------------------------- layout

# Group -> top-left corner of its block on the A3 sheet (mm). Parts are placed in rows of 4.
GROUP_AT = {
    "pi": (30.48, 40.64), "sensors": (139.7, 33.02), "mains": (139.7, 116.84), "outputs": (139.7, 200.66),
    "lock": (271.78, 33.02), "i2c": (271.78, 116.84), "keypad": (271.78, 200.66),
    "mech": (30.48, 200.66),
}
STEP_X, STEP_Y, PER_ROW = 27.94, 38.1, 4


def snap(v):
    return round(v / 1.27) * 1.27


def layout():
    """ref -> (x, y) of the symbol on the sheet."""
    placed, count = {}, {}
    for ref, part in PARTS.items():
        group = part[4]
        k = count.get(group, 0)
        count[group] = k + 1
        gx, gy = GROUP_AT[group]
        if group == "pi":
            placed[ref] = (snap(gx + 30), snap(gy + 35))
        else:
            placed[ref] = (snap(gx + 12.7 + (k % PER_ROW) * STEP_X), snap(gy + 17.78 + (k // PER_ROW) * STEP_Y))
    return placed


# ---------------------------------------------------------------- writing

def font(size=1.27, justify=None, hide=False):
    j = " (justify %s)" % justify if justify else ""
    h = " (hide yes)" if hide else ""
    return "(effects (font (size %g %g))%s%s)" % (size, size, j, h)


def label(net, x, y, angle):
    justify = {0: "left bottom", 90: "left bottom", 180: "right bottom", 270: "right bottom"}[angle]
    return '\t(label "%s" (at %.2f %.2f %d) %s (uuid "%s"))\n' % (
        net, x, y, angle, font(justify=justify), uid("label %s %.2f %.2f" % (net, x, y)))


def placed_symbol(ref, lib_id, value, footprint, x, y, pins, note):
    # Name and value to the right of the symbol, or above it if it has pins on its right side
    if any(angle == 180 for _, _, angle in pins.values()):
        top = y - max(py for _, py, _ in pins.values())
        (rx, ry), (vx, vy) = (x - 2.54, top - 6.35), (x - 2.54, top - 3.81)
    else:
        (rx, ry), (vx, vy) = (x + 5.08, y - 1.27), (x + 5.08, y + 1.27)
    props = [
        ('Reference', ref, rx, ry, False),
        ('Value', value, vx, vy, False),
        ('Footprint', footprint, x, y + 5.08, True),
        ('Datasheet', "", x, y, True),
        ('Description', note, x, y, True),
    ]
    in_bom = "no" if lib_id.startswith("Mechanical:") else "yes"     # holes are not bought parts
    text = '\t(symbol (lib_id "%s") (at %.2f %.2f 0) (unit 1) (exclude_from_sim no) (in_bom %s) (on_board yes) (dnp no)\n' % (
        lib_id, x, y, in_bom)
    text += '\t\t(uuid "%s")\n' % uid("sym " + ref)
    for name, val, px, py, hide in props:
        text += '\t\t(property "%s" "%s" (at %.2f %.2f 0) %s)\n' % (
            name, val.replace('"', "'"), px, py, font(justify="left", hide=hide))
    for number in pins:
        text += '\t\t(pin "%s" (uuid "%s"))\n' % (number, uid("pin %s %s" % (ref, number)))
    text += '\t\t(instances (project "%s" (path "/%s" (reference "%s") (unit 1))))\n\t)\n' % (PROJECT, ROOT_UUID, ref)
    return text


def main():
    positions = layout()
    lib_blocks, body = {}, ""
    for ref, (lib_id, value, footprint, pin_nets, group, note) in PARTS.items():
        if lib_id not in lib_blocks:
            lib_blocks[lib_id] = flat_symbol(lib_id)
        pins = symbol_pins(lib_blocks[lib_id])
        x, y = positions[ref]
        body += placed_symbol(ref, lib_id, value, footprint, x, y, pins, note)
        for number, (px, py, angle) in pins.items():
            sx, sy = x + px, y - py                  # symbol y is up, sheet y is down
            if number in pin_nets:
                body += label(pin_nets[number], sx, sy, (angle + 180) % 360)
            else:
                body += '\t(no_connect (at %.2f %.2f) (uuid "%s"))\n' % (sx, sy, uid("nc %s %s" % (ref, number)))

    for group, (gx, gy) in GROUP_AT.items():
        body += '\t(text "%s" (exclude_from_sim no) (at %.2f %.2f 0) %s (uuid "%s"))\n' % (
            GROUP_TITLES[group], gx, gy, font(2.0, "left bottom"), uid("title " + group))
    notes = ("Generated by make_schematic.py from carrier.py (do not edit by hand: change the table and run again).\\n"
             "Lock nets +5V_LOCK and LOCK_N: 1.0 mm tracks (about 1 A, VERIFY). The Peltier's 12 V / ~5 A never "
             "comes onto this board.")
    body += '\t(text "%s" (exclude_from_sim no) (at 30.48 270 0) %s (uuid "%s"))\n' % (
        notes, font(1.5, "left bottom"), uid("notes"))

    lib_text = "".join("\t\t" + block.replace("\n", "\n\t") + "\n" for block in lib_blocks.values())
    sch = ('(kicad_sch\n\t(version 20250610)\n\t(generator "make_schematic.py")\n\t(generator_version "10.0")\n'
           '\t(uuid "%s")\n\t(paper "A3")\n'
           '\t(title_block (title "Cold chain carrier board (Raspberry Pi HAT)") (date "%s") (rev "1")\n'
           '\t\t(company "CMU Africa 04-645 IoT, Fall 2026") (comment 1 "P. L. Samuel, Y. D. Gatoni"))\n'
           '\t(lib_symbols\n%s\t)\n%s'
           '\t(sheet_instances (path "/" (page "1")))\n)\n') % (ROOT_UUID, date.today().isoformat(), lib_text, body)
    path = os.path.join(HERE, PROJECT + ".kicad_sch")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sch)
    print("Wrote", path, "with", len(PARTS), "parts")


if __name__ == "__main__":
    main()
