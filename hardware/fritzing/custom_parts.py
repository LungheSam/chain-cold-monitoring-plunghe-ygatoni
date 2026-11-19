"""Custom Fritzing parts that the core library does not have.

Each part is a .fzp file plus three SVG pictures (breadboard, schematic, pcb).
All sizes are in inches; one SVG unit is 0.01 in, so the 0.1 in pin pitch is 10 units.
The pictures are simple drawings, not exact copies of the real modules.
Pin orders marked VERIFY must be checked on the module we actually buy.
"""

FRITZING_VERSION = "0.9.3b"


# ---------------------------------------------------------------- helpers

def svg_open(w, h):
    """SVG header: w and h are in 0.01 in units."""
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.2" '
            f'width="{w / 100}in" height="{h / 100}in" viewBox="0 0 {w} {h}">\n')


def text(x, y, s, size=6, fill="#ffffff", anchor="middle", weight="normal", rotate=None):
    tr = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
    return (f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}"{tr}>{s}</text>\n')


def pin_rect(i, x, y, size=5):
    """A square metal pin; its centre (x, y) is where wires attach."""
    h = size / 2
    return (f'<rect id="connector{i}pin" x="{x - h}" y="{y - h}" width="{size}" height="{size}" '
            f'fill="#c8c8c8" stroke="#707070" stroke-width="0.6"/>\n')


def schematic_svg(title, left, right):
    """Box with pins on the left and right side, 0.1 in apart, 0.3 in pin lines."""
    rows = max(len(left), len(right))
    w = 120 + 60          # body 1.2 in + two 0.3 in pin lines
    h = rows * 10 + 30
    out = svg_open(w, h)
    out += f'<g id="schematic">\n'
    out += f'<rect x="30" y="10" width="120" height="{h - 20}" fill="none" stroke="#000000" stroke-width="1"/>\n'
    out += text(90, 8, title, size=6, fill="#000000")
    for k, (i, name) in enumerate(left):
        y = 20 + k * 10
        out += f'<line id="connector{i}pin" x1="0" y1="{y}" x2="30" y2="{y}" stroke="#000000" stroke-width="1"/>\n'
        out += f'<rect id="connector{i}terminal" x="0" y="{y - 0.5}" width="1" height="1" fill="none"/>\n'
        out += text(33, y + 2, name, size=5, fill="#000000", anchor="start")
    for k, (i, name) in enumerate(right):
        y = 20 + k * 10
        out += f'<line id="connector{i}pin" x1="150" y1="{y}" x2="{w}" y2="{y}" stroke="#000000" stroke-width="1"/>\n'
        out += f'<rect id="connector{i}terminal" x="{w - 1}" y="{y - 0.5}" width="1" height="1" fill="none"/>\n'
        out += text(147, y + 2, name, size=5, fill="#000000", anchor="end")
    out += '</g>\n</svg>\n'
    return out


def pcb_svg(n):
    """One row of n through-hole pads, 0.1 in apart."""
    w, h = n * 10 + 10, 30
    out = svg_open(w, h)
    out += f'<g id="silkscreen"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" fill="none" stroke="#ffffff" stroke-width="1"/></g>\n'
    out += '<g id="copper1"><g id="copper0">\n'
    for i in range(n):
        out += (f'<circle id="connector{i}pin" cx="{10 + i * 10}" cy="15" r="3.2" '
                f'fill="none" stroke="#F7BD13" stroke-width="2"/>\n')
    out += '</g></g>\n</svg>\n'
    return out


def fzp(module_id, filename, title, label, description, pins, family):
    """pins = list of (name, description)."""
    conns = ""
    for i, (name, desc) in enumerate(pins):
        conns += f'''  <connector id="connector{i}" name="{name}" type="male">
   <description>{desc}</description>
   <views>
    <breadboardView><p layer="breadboard" svgId="connector{i}pin"/></breadboardView>
    <schematicView><p layer="schematic" svgId="connector{i}pin" terminalId="connector{i}terminal"/></schematicView>
    <pcbView><p layer="copper0" svgId="connector{i}pin"/><p layer="copper1" svgId="connector{i}pin"/></pcbView>
   </views>
  </connector>
'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<module moduleId="{module_id}" fritzingVersion="{FRITZING_VERSION}">
 <version>1</version>
 <author>Cold chain team (04-645)</author>
 <title>{title}</title>
 <label>{label}</label>
 <date>2026-11-17</date>
 <tags><tag>coldchain</tag></tags>
 <properties><property name="family">{family}</property></properties>
 <description>{description}</description>
 <views>
  <iconView><layers image="breadboard/{filename}.svg"><layer layerId="icon"/></layers></iconView>
  <breadboardView><layers image="breadboard/{filename}.svg"><layer layerId="breadboard"/></layers></breadboardView>
  <schematicView><layers image="schematic/{filename}.svg"><layer layerId="schematic"/></layers></schematicView>
  <pcbView><layers image="pcb/{filename}.svg"><layer layerId="copper0"/><layer layerId="silkscreen"/><layer layerId="copper1"/></layers></pcbView>
 </views>
 <connectors>
{conns} </connectors>
</module>
'''


# ---------------------------------------------------------------- parts

def keypad():
    """4x4 membrane keypad, ribbon order R1 R2 R3 R4 C1 C2 C3 C4 (docs/wiring.md)."""
    w, h = 270, 440
    s = svg_open(w, h) + '<g id="breadboard">\n'
    s += f'<rect x="0" y="0" width="{w}" height="300" rx="8" fill="#1b1b1b"/>\n'
    keys = ["1", "2", "3", "A", "4", "5", "6", "B", "7", "8", "9", "C", "*", "0", "#", "D"]
    for k, name in enumerate(keys):
        r, c = divmod(k, 4)
        x, y = 15 + c * 62, 15 + r * 70
        color = "#c0392b" if name in "ABCD" else "#2c6fbb"
        s += f'<rect x="{x}" y="{y}" width="54" height="60" rx="6" fill="{color}"/>\n'
        s += text(x + 27, y + 40, name, size=26, weight="bold")
    # ribbon and 8-pin connector
    s += '<rect x="95" y="300" width="80" height="105" fill="#9a9a9a"/>\n'
    for i in range(8):
        s += f'<line x1="{100 + i * 10}" y1="300" x2="{100 + i * 10}" y2="405" stroke="#d8d8d8" stroke-width="2"/>\n'
    s += '<rect x="92" y="405" width="86" height="22" fill="#111111"/>\n'
    names = ["R1", "R2", "R3", "R4", "C1", "C2", "C3", "C4"]
    for i, n in enumerate(names):
        s += pin_rect(i, 100 + i * 10, 420)
        s += text(100 + i * 10, 398, n, size=5, fill="#000000", rotate=-90)
    s += text(135, 438, "4x4 keypad (ribbon order VERIFY)", size=7, fill="#000000")
    s += '</g>\n</svg>\n'
    pins = [(n, f"keypad {'row' if n[0] == 'R' else 'column'} {n[1]}") for n in names]
    return {
        "file": "coldchain_keypad_4x4",
        "module_id": "coldchain-keypad-4x4-v1",
        "title": "4x4 Membrane Keypad",
        "label": "KP",
        "family": "keypad",
        "description": "16-key membrane keypad, 8-pin ribbon: R1-R4 then C1-C4.",
        "pins": pins,
        "breadboard": s,
        "schematic": schematic_svg("4x4 keypad", [(i, n) for i, n in enumerate(names)], []),
        "pcb": pcb_svg(8),
    }


def relay_module():
    """1-channel 5 V relay module: input header VCC GND IN, terminals NO COM NC (VERIFY order)."""
    w, h = 200, 100
    s = svg_open(w, h) + '<g id="breadboard">\n'
    s += f'<rect x="0" y="0" width="{w}" height="{h}" rx="4" fill="#1f5fae"/>\n'
    s += '<rect x="60" y="12" width="80" height="62" rx="3" fill="#2a7de1" stroke="#0f3d73" stroke-width="1.5"/>\n'
    s += text(100, 40, "RELAY", size=11, weight="bold")
    s += text(100, 54, "5 V DC coil", size=7)
    s += text(100, 90, "1-channel relay module", size=8)
    s += '<circle cx="35" cy="20" r="4" fill="#ff3b30"/>\n'  # status LED
    s += text(35, 12, "LED", size=5)
    # input header (left)
    for i, (n, y) in enumerate([("VCC", 40), ("GND", 50), ("IN", 60)]):
        s += pin_rect(i, 10, y)
        s += text(17, y + 2, n, size=6, anchor="start")
    # screw terminals (right), 0.2 in apart
    s += '<rect x="168" y="18" width="28" height="64" fill="#2e8b57"/>\n'
    for k, (n, y) in enumerate([("NO", 30), ("COM", 50), ("NC", 70)]):
        s += f'<circle cx="182" cy="{y}" r="7" fill="#9c9c9c" stroke="#555555"/>\n'
        s += pin_rect(3 + k, 192, y)
        s += text(162, y + 2, n, size=6, anchor="end")
    s += '</g>\n</svg>\n'
    pins = [("VCC", "5 V supply"), ("GND", "ground"), ("IN", "control input from the Pi (GPIO 25)"),
            ("NO", "normally open contact"), ("COM", "common contact"), ("NC", "normally closed contact")]
    return {
        "file": "coldchain_relay_module",
        "module_id": "coldchain-relay-module-5v-v1",
        "title": "5 V Relay Module (1 channel)",
        "label": "K",
        "family": "relay module",
        "description": "Single-channel 5 V relay module. Pin order and trigger level (HIGH or LOW) VERIFY on the board.",
        "pins": pins,
        "breadboard": s,
        "schematic": schematic_svg("Relay module", [(0, "VCC"), (1, "GND"), (2, "IN")],
                                   [(3, "NO"), (4, "COM"), (5, "NC")]),
        "pcb": pcb_svg(6),
    }


def lcd_i2c():
    """16x2 LCD with PCF8574 I2C backpack: GND VCC SDA SCL (VERIFY order on the backpack)."""
    w, h = 315, 142
    s = svg_open(w, h) + '<g id="breadboard">\n'
    s += f'<rect x="0" y="0" width="{w}" height="{h}" rx="4" fill="#1d7a35"/>\n'
    for (cx, cy) in [(10, 10), (305, 10), (10, 132), (305, 132)]:
        s += f'<circle cx="{cx}" cy="{cy}" r="5" fill="#d9d9d9"/>\n'
    s += '<rect x="35" y="26" width="262" height="86" fill="#111111"/>\n'
    s += '<rect x="48" y="38" width="236" height="62" fill="#7fc7ff"/>\n'
    s += text(166, 64, "COLD CHAIN  OK", size=17, fill="#08305a", weight="bold")
    s += text(166, 90, "4.6 C  door shut", size=17, fill="#08305a", weight="bold")
    s += '<rect x="2" y="38" width="24" height="52" fill="#222222"/>\n'
    for i, (n, y) in enumerate([("GND", 45), ("VCC", 55), ("SDA", 65), ("SCL", 75)]):
        s += pin_rect(i, 8, y)
        s += text(30, y + 2, n, size=6, anchor="start")
    s += text(166, 132, "16x2 LCD + PCF8574 I2C backpack (address 0x27, VERIFY)", size=7)
    s += '</g>\n</svg>\n'
    pins = [("GND", "ground"), ("VCC", "5 V supply"), ("SDA", "I2C data (5 V side)"), ("SCL", "I2C clock (5 V side)")]
    return {
        "file": "coldchain_lcd_i2c",
        "module_id": "coldchain-lcd16x2-i2c-v1",
        "title": "LCD 16x2 with I2C backpack",
        "label": "LCD",
        "family": "lcd",
        "description": "HD44780 16x2 LCD with PCF8574 I2C backpack, 5 V.",
        "pins": pins,
        "breadboard": s,
        "schematic": schematic_svg("LCD 16x2 I2C", [(i, n) for i, (n, _) in enumerate(pins)], []),
        "pcb": pcb_svg(4),
    }


def w1209():
    """W1209 thermostat module: 12 V power in, relay contacts out (terminal names VERIFY)."""
    w, h = 190, 160
    s = svg_open(w, h) + '<g id="breadboard">\n'
    s += f'<rect x="0" y="0" width="{w}" height="{h}" rx="4" fill="#c8102e"/>\n'
    s += '<rect x="55" y="15" width="80" height="40" fill="#222222"/>\n'
    s += text(95, 47, "4.0", size=30, fill="#ff3b30", weight="bold")
    for k, n in enumerate(["SET", "+", "-"]):
        s += f'<circle cx="{70 + k * 25}" cy="80" r="7" fill="#f2f2f2" stroke="#555555"/>\n'
        s += text(70 + k * 25, 97, n, size=7)
    s += '<rect x="55" y="105" width="80" height="34" fill="#3a6fd8"/>\n'
    s += text(95, 126, "relay", size=9)
    s += text(95, 154, "W1209 thermostat", size=9, weight="bold")
    # power terminals left, relay terminals right (0.2 in apart)
    s += '<rect x="0" y="40" width="26" height="50" fill="#2e8b57"/>\n'
    s += '<rect x="164" y="40" width="26" height="50" fill="#2e8b57"/>\n'
    pins_xy = [("+12V", 8, 55), ("GND", 8, 75), ("RELAY A", 182, 55), ("RELAY B", 182, 75)]
    for i, (n, x, y) in enumerate(pins_xy):
        s += pin_rect(i, x, y)
        s += text(x + (12 if x < 100 else -12), y - 8, n.replace("RELAY ", "RLY "), size=6,
                  anchor="start" if x < 100 else "end")
    s += text(95, 8, "NTC probe goes into the box", size=6)
    s += '</g>\n</svg>\n'
    pins = [("+12V", "12 V supply"), ("GND", "ground"),
            ("RELAY A", "relay contact (terminal name VERIFY)"), ("RELAY B", "relay contact (terminal name VERIFY)")]
    return {
        "file": "coldchain_w1209",
        "module_id": "coldchain-w1209-thermostat-v1",
        "title": "W1209 Thermostat Module",
        "label": "TH",
        "family": "thermostat",
        "description": "W1209 12 V thermostat with NTC probe; its relay switches the Peltier kit.",
        "pins": pins,
        "breadboard": s,
        "schematic": schematic_svg("W1209", [(0, "+12V"), (1, "GND")], [(2, "RELAY A"), (3, "RELAY B")]),
        "pcb": pcb_svg(4),
    }


def ds18b20_probe():
    """Waterproof DS18B20 probe: 3 wires. Usual colours red = VDD, black = GND,
    yellow = DQ (VERIFY on our probe). The wire ends plug into the breadboard 0.1 in apart;
    the cable rises and the stainless tip lies to the right."""
    w, h = 80, 75
    s = svg_open(w, h) + '<g id="breadboard">\n'
    # cable and stainless tip
    s += '<path d="M20 48 C20 30 28 18 40 16" fill="none" stroke="#111111" stroke-width="5"/>\n'
    s += '<rect x="38" y="10" width="40" height="12" rx="5" fill="#c9ced6" stroke="#8a9099"/>\n'
    s += text(58, 32, "DS18B20 probe", size=6, fill="#000000")
    # three wire ends: black GND, yellow DQ, red VDD
    for i, (color, x) in enumerate([("#222222", 10), ("#e6c300", 20), ("#d11a1a", 30)]):
        s += f'<path d="M20 48 L{x} 58 L{x} 70" fill="none" stroke="{color}" stroke-width="2.5"/>\n'
        s += pin_rect(i, x, 70, size=4)
    s += '</g>\n</svg>\n'
    pins = [("GND", "ground (black wire)"), ("DQ", "1-Wire data (yellow wire)"), ("VDD", "3.3 V (red wire)")]
    return {
        "file": "coldchain_ds18b20_probe",
        "module_id": "coldchain-ds18b20-probe-v1",
        "title": "DS18B20 waterproof probe",
        "label": "U",
        "family": "temperature sensor",
        "description": "DS18B20 1-Wire temperature sensor in a stainless waterproof probe, 3 wires.",
        "pins": pins,
        "breadboard": s,
        "schematic": schematic_svg("DS18B20 probe", [(0, "GND"), (1, "DQ"), (2, "VDD")], []),
        "pcb": pcb_svg(3),
    }


def car_relay():
    """12 V automotive relay, 30-40 A contacts. Standard pin numbers: 85/86 coil, 30 common,
    87 normally open (printed on the relay; VERIFY on ours)."""
    w, h = 100, 100
    s = svg_open(w, h) + '<g id="breadboard">\n'
    s += f'<rect x="14" y="8" width="72" height="84" rx="4" fill="#2b2b2b"/>\n'
    s += text(50, 40, "12 V", size=11, weight="bold")
    s += text(50, 55, "30-40 A", size=9)
    s += text(50, 70, "car relay", size=8)
    for i, (name, x, y) in enumerate([("86", 10, 30), ("85", 10, 70), ("30", 90, 30), ("87", 90, 70)]):
        s += pin_rect(i, x, y)
        s += text(x + (8 if x < 50 else -8), y - 6, name, size=6, anchor="start" if x < 50 else "end")
    s += '</g>\n</svg>\n'
    pins = [("86", "coil + (from the W1209 relay)"), ("85", "coil - (ground)"),
            ("30", "common contact (12 V after the fuse)"), ("87", "normally open contact (to the Peltier +)")]
    return {
        "file": "coldchain_car_relay",
        "module_id": "coldchain-car-relay-12v-v1",
        "title": "Car relay 12 V 30-40 A",
        "label": "K",
        "family": "relay",
        "description": "Automotive relay, 12 V coil, 30-40 A contacts; switches the Peltier kit.",
        "pins": pins,
        "breadboard": s,
        "schematic": schematic_svg("Car relay", [(0, "86"), (1, "85")], [(2, "30"), (3, "87")]),
        "pcb": pcb_svg(4),
    }


ALL = [keypad, relay_module, lcd_i2c, w1209, ds18b20_probe, car_relay]


def build_all():
    """Return {module_id: part dict} with the fzp text added."""
    parts = {}
    for make in ALL:
        p = make()
        p["fzp"] = fzp(p["module_id"], p["file"], p["title"], p["label"], p["description"],
                       p["pins"], p["family"])
        parts[p["module_id"]] = p
    return parts
