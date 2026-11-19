"""Builds docs/purchase-request.xlsx: the full materials list for the cold chain prototype."""
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

OUT = sys.argv[1]
FONT = "Arial"

# (section, [(item, specification, qty, unit, priority, purpose, check before buying)])
SECTIONS = [
    ("A. Cooling (the vaccine \"fridge\")", [
        ("Thermoelectric (Peltier) cooling kit",
         "120 W semiconductor refrigeration cooling system kit: Peltier modules (the photo shows two) with cold-side heat sinks "
         "and fans and a large hot-side heat sink with fan. 12 V DC, about 8-10 A.",
         1, "kit", "Essential", "Cools the box",
         "In stock at Nyereka Tech, RWF 41,500. Check in the shop how many Peltier modules it has."),
        ("DC power supply for the cooler", "12 V DC, 30 A (360 W) switching supply, enclosed metal case; CE/UL certified",
         1, "pc", "Essential", "Powers the Peltier kit and its fans",
         "The kit draws 8-10 A; a 10 A supply would run at its limit. Nyereka Tech, RWF 30,000."),
        ("Inline fuse holder", "Blade-fuse holder for a 12 V line, rated at least 15 A, 14 AWG leads", 1, "pc", "Essential", "Protects the 12 V wiring", "Car parts shop."),
        ("Blade fuses", "15 A automotive blade fuses (pack)", 1, "pack", "Essential", "Spares for the fuse holder", "Same size as the holder (standard ATO/ATC or mini)."),
        ("Thermostat controller module", "W1209 (or equivalent) 12 V digital thermostat with NTC probe and relay",
         1, "pc", "Essential", "Switches the Peltier on and off around a set temperature, like a real fridge thermostat",
         "Its own relay (about 10 A) only drives the car relay coil, not the Peltier."),
        ("Car relay with socket", "12 V coil, 30-40 A contacts, 4 or 5 pins (automotive type), with a wired socket",
         1, "pc", "Essential", "Switches the Peltier's 8-10 A; the W1209 switches only its coil",
         "Car parts shop. A 1N4007 diode goes across the coil."),
        ("Insulated cool box", "Small rigid cool box, 5-10 litres, polystyrene or foam walls, flat lid", 1, "pc", "Essential",
         "The vaccine \"fridge\"; the cooler is mounted through the lid, cold side down", "Flat lid at least 12 x 12 cm for the cooler."),
        ("Power wire", "14 AWG (2.5 mm2) two-core, red/black", 3, "m", "Essential", "12 V supply to the cooler", "Carries up to 10 A."),
        ("Gel ice packs", "Reusable, about 200-400 ml each", 4, "pc", "Optional", "Back-up cooling if the Peltier cannot reach +8 C in a warm room", ""),
        ("Foam sealing tape", "Self-adhesive foam weatherstrip, about 10 mm wide", 2, "m", "Optional", "Seals the gap around the cooler and the lid", ""),
    ]),
    ("B. Computer", [
        ("Raspberry Pi 4 Model B", "2 GB RAM or more", 1, "pc", "Essential (if not available)", "Runs the monitoring software", "The lab may already have one."),
        ("Raspberry Pi power supply", "Official Raspberry Pi 15 W USB-C, 5.1 V 3 A", 1, "pc", "Essential (if not available)", "Powers the Pi", ""),
        ("microSD card", "32 GB, Class 10 / A1 (SanDisk, Samsung or similar)", 1, "pc", "Essential (if not available)", "Operating system and data", ""),
    ]),
    ("C. Sensors", [
        ("Waterproof temperature probe", "DS18B20, stainless-steel tip, about 1 m cable, 3 wires", 2, "pc", "Essential", "Temperature inside the box (1 spare)", ""),
        ("Temperature and humidity sensor", "DHT22 / AM2302, module on a small board preferred", 1, "pc", "Essential", "Room temperature and humidity", ""),
        ("Door reed switch with magnet", "Surface-mount magnetic door contact, normally open, MC-38 type", 2, "pc", "Essential", "Door open / closed (1 spare)", ""),
    ]),
    ("D. Alarm and display", [
        ("LCD display", "16x2 character LCD with I2C backpack (PCF8574), 5 V", 1, "pc", "Essential", "Local status display", ""),
        ("Logic level converter", "4-channel bidirectional, BSS138, 3.3 V <-> 5 V", 2, "pc", "Essential", "Connects the 5 V display to the 3.3 V Pi (1 spare)", ""),
        ("Buzzer", "Passive buzzer, 5 V, about 12 mm", 2, "pc", "Essential", "Audible alarm (1 spare)", "Passive, not active."),
        ("LEDs", "5 mm, red and green, assorted pack", 1, "pack", "Essential", "Alarm / OK lights", ""),
    ]),
    ("E. Door lock (extension)", [
        ("Electric solenoid cabinet lock", "5 V DC, small cupboard size, current about 1 A or less", 1, "pc", "Extension", "Locks the box door", "Must be 5 V (not 12 V)."),
        ("Power supply for the lock", "5 V DC, 2 A, barrel plug 5.5 x 2.1 mm; CE/UL certified", 1, "pc", "Extension", "Powers the lock (never from the Pi)", ""),
        ("Keypad", "4x4 matrix membrane keypad, 8-pin ribbon", 1, "pc", "Extension", "PIN entry", ""),
        ("Relay module", "1-channel 5 V relay module that switches on with a HIGH input (or has an H/L jumper)", 1, "pc", "Extension",
         "Switches the lock (no logic-level MOSFET is sold locally)", "Nyereka Tech, RWF 2,300. The lock must stay off while the Pi starts."),
    ]),
    ("F. Electronic parts and wiring", [
        ("Breadboard", "Full size, 830 points", 1, "pc", "Essential", "Circuit assembly", ""),
        ("Jumper wire set", "Male-male, male-female and female-female, 20 cm, about 40 of each", 1, "set", "Essential", "Connections", ""),
        ("Resistor assortment", "1/4 W, E12 values 10 ohm to 1 Mohm (must include 100, 330, 1k, 2.7k, 4.7k, 10k)", 1, "kit", "Essential",
         "Pull-ups, voltage divider, LED and transistor resistors", ""),
        ("Diodes", "1N4007 x5, 1N4148 x5, 1N5819 Schottky x5", 1, "set", "Essential", "Protection diodes", ""),
        ("NPN transistors", "BC547 or 2N2222", 5, "pc", "Essential", "Buzzer driver", ""),
        ("Ceramic capacitors", "100 nF", 5, "pc", "Essential", "Noise filter", ""),
        ("DC barrel jack connectors", "5.5 x 2.1 mm female, with screw terminals", 2, "pc", "Essential", "Connect the 12 V and 5 V supplies", ""),
        ("Hook-up wire", "22 AWG solid core, assorted colours", 1, "set", "Essential", "Longer connections", ""),
        ("Heat-shrink tubing", "Assorted sizes", 1, "set", "Essential", "Insulate soldered joints", ""),
        ("Double-sided mounting tape", "Strong foam tape, outdoor grade", 1, "roll", "Essential", "Fixes sensors and brackets (no screws in the design)", ""),
        ("Cable ties", "Small, 100 mm", 1, "pack", "Essential", "Cable management", ""),
    ]),
    ("G. Enclosure (3D printed by the team)", [
        ("3D printer filament", "PETG, 1.75 mm, 1 kg, any colour", 1, "spool", "Essential", "Electronics box, sensor holders, cooler mounting frame", ""),
        ("Cable glands", "PG7, IP68, for 3-6.5 mm cable", 4, "pc", "Optional", "Sealed cable entries into the box", ""),
    ]),
    ("H. Tools (only if the lab does not already have them)", [
        ("Digital multimeter", "DC voltage and current up to 10 A", 1, "pc", "Essential (if not available)", "Safety checks (voltages, lock current)", ""),
        ("Soldering station", "Temperature controlled, with solder", 1, "pc", "Essential (if not available)", "Sensor cables", ""),
        ("Digital calipers", "150 mm", 1, "pc", "Essential (if not available)", "Measuring parts for the 3D-printed enclosure", ""),
        ("3D printer access", "Prints PETG, bed at least 220 x 220 mm", 1, "access", "Essential (if not available)", "Printing the enclosure", "Access to the lab printer is enough."),
    ]),
]

HEADERS = ["#", "Item", "Specification (what to buy)", "Qty", "Unit", "Priority", "Purpose",
           "Check before buying", "Already available?", "Unit price (RWF)", "Total (RWF)", "Supplier / link"]
WIDTHS = [6, 28, 52, 6, 8, 16, 34, 38, 12, 14, 14, 26]

thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HEAD_FILL = PatternFill("solid", fgColor="0B5394")
SECTION_FILL = PatternFill("solid", fgColor="DDEBF7")
INPUT_FILL = PatternFill("solid", fgColor="FFFF99")
MONEY = '#,##0;-#,##0;"-"'

wb = Workbook()
ws = wb.active
ws.title = "Materials"

# ---- heading and legend
ws["A1"] = "Purchase request: IoT cold chain monitoring prototype"
ws["A1"].font = Font(name=FONT, bold=True, size=14, color="0B5394")
info = [
    "Course: 04-645 A Internet of Things, CMU Africa, Fall 2026. Team: Putshu Lunghe Samuel (plunghe), Yves Dominique Gatoni (ygatoni).",
    "Needed by: as soon as possible; the demo is on Wednesday 2 December 2026.",
    "Purpose: a vaccine fridge monitor prototype. A small insulated box is cooled by a Peltier kit and kept at +2 to +8 C; "
    "a Raspberry Pi measures temperature, door and power, raises a local alarm and an SMS, and records every period out of range.",
    "How to fill in: only the YELLOW columns. \"Already available?\" = Yes or No. \"Unit price (RWF)\" = a number only, "
    "for example 25000. Totals are calculated automatically (leave the price empty for items already available).",
    "Priority: Essential = the prototype cannot work without it. Extension = the door-lock feature. Optional = useful but not required.",
]
for i, text in enumerate(info, start=2):
    ws.cell(row=i, column=1, value=text).font = Font(name=FONT, size=10, bold=(i == 5))
    ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=len(HEADERS))
    ws.cell(row=i, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[i].height = 28 if len(text) > 120 else 16

HEAD_ROW = 8
for c, (title, width) in enumerate(zip(HEADERS, WIDTHS), start=1):
    cell = ws.cell(row=HEAD_ROW, column=c, value=title)
    cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
    cell.fill = HEAD_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER
    ws.column_dimensions[cell.column_letter].width = width
ws.row_dimensions[HEAD_ROW].height = 32

yes_no = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
ws.add_data_validation(yes_no)

row = HEAD_ROW + 1
first_item_row = row
n = 0
for section, items in SECTIONS:
    cell = ws.cell(row=row, column=1, value=section)
    cell.font = Font(name=FONT, bold=True, size=11, color="0B5394")
    for c in range(1, len(HEADERS) + 1):
        ws.cell(row=row, column=c).fill = SECTION_FILL
        ws.cell(row=row, column=c).border = BORDER
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(HEADERS))
    row += 1
    for item, spec, qty, unit, prio, purpose, check in items:
        n += 1
        values = [n, item, spec, qty, unit, prio, purpose, check, None, None, f"=IF(J{row}=\"\",0,D{row}*J{row})", None]
        for c, v in enumerate(values, start=1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.font = Font(name=FONT, size=10, bold=(c == 2))
            cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="center" if c in (1, 4, 5, 9) else None)
            cell.border = BORDER
        for c in (9, 10, 12):
            ws.cell(row=row, column=c).fill = INPUT_FILL
        ws.cell(row=row, column=10).number_format = MONEY
        ws.cell(row=row, column=11).number_format = MONEY
        yes_no.add(f"I{row}")
        row += 1
last_item_row = row - 1

# ---- totals
row += 1
totals = [
    ("Total, Essential items", f'=SUMIF(F{first_item_row}:F{last_item_row},"Essential*",K{first_item_row}:K{last_item_row})'),
    ("Total, Extension (door lock)", f'=SUMIF(F{first_item_row}:F{last_item_row},"Extension",K{first_item_row}:K{last_item_row})'),
    ("Total, Optional items", f'=SUMIF(F{first_item_row}:F{last_item_row},"Optional",K{first_item_row}:K{last_item_row})'),
    ("GRAND TOTAL (RWF)", f"=SUM(K{first_item_row}:K{last_item_row})"),
]
for label, formula in totals:
    ws.cell(row=row, column=8, value=label).font = Font(name=FONT, bold=True, size=10)
    ws.merge_cells(start_row=row, start_column=8, end_row=row, end_column=10)
    ws.cell(row=row, column=8).alignment = Alignment(horizontal="right")
    cell = ws.cell(row=row, column=11, value=formula)
    cell.font = Font(name=FONT, bold=True, size=10 if "GRAND" not in label else 11)
    cell.number_format = MONEY
    cell.border = BORDER
    row += 1

ws.freeze_panes = f"C{HEAD_ROW + 1}"     # header row and the # / Item columns stay visible
ws.print_title_rows = f"{HEAD_ROW}:{HEAD_ROW}"
ws.page_setup.orientation = "landscape"
ws.page_setup.paperSize = ws.PAPERSIZE_A4
ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 0
ws.sheet_properties.pageSetUpPr.fitToPage = True

# ---- second sheet: safety and notes
ns = wb.create_sheet("Notes and safety")
notes = [
    ("Notes and safety for the purchasing office", True),
    ("", False),
    ("Peltier cooling kit (item 1)", True),
    ("Buy the complete 120 W KIT (Nyereka Tech, RWF 41,500): Peltier modules already mounted between cold-side heat sinks with "
     "fans and a large hot-side heat sink with a fan. A bare Peltier module has no heat sink or fan and burns out within a "
     "minute if powered like that.", False),
    ("The kit draws about 8-10 A at 12 V, so the supply is 30 A, the fuse 15 A, the wire 14 AWG, and a 30-40 A car relay "
     "switches it (the W1209's own relay is only about 10 A).", False),
    ("", False),
    ("Electrical safety", True),
    ("All mains-powered items (12 V 30 A supply, Raspberry Pi supply, lock supply) must be certified (CE / UL or equivalent). "
     "The team never opens or wires anything at 230 V; only the low-voltage (12 V / 5 V) side is used.", False),
    ("The Peltier's 12 V current never passes through the Raspberry Pi or the circuit board: it goes from the supply through "
     "the 15 A fuse and the car relay (switched by the W1209 thermostat) to the cooler only.", False),
    ("", False),
    ("Why a thermostat (W1209)", True),
    ("A Peltier cooler has no temperature control of its own. The thermostat switches it on and off around a set temperature, "
     "like a real fridge, while the Raspberry Pi independently monitors and records the temperature and raises the alarms.", False),
    ("", False),
    ("Prices", True),
    ("Prices are in Rwandan francs (RWF). Leave the unit price empty for items the lab already has; they are then not counted "
     "in the totals.", False),
]
ns.column_dimensions["A"].width = 120
for i, (text, bold) in enumerate(notes, start=1):
    cell = ns.cell(row=i, column=1, value=text)
    cell.font = Font(name=FONT, bold=bold, size=13 if i == 1 else 10, color="0B5394" if bold else "000000")
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    if len(text) > 120:
        ns.row_dimensions[i].height = 15 * (len(text) // 110 + 1)

wb.save(OUT)
print("saved", OUT, "| items:", n, "| item rows", first_item_row, "-", last_item_row)
