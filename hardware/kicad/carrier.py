"""The carrier board as a table: every part, its value, footprint and which net each pin is on.

make_schematic.py and make_pcb.py both read this table, so the schematic and the board can never
disagree (and `kicad-cli pcb drc --schematic-parity` checks it again).

Circuit decisions are in docs/wiring.md. Pin numbers of the Pi header are physical pin numbers.
"""

# ---------------------------------------------------------------- Raspberry Pi 40-pin header
# Physical pin -> net. Pins that are not listed are not used (no-connect flags in the schematic).
PI_PINS = {
    1: "+3V3", 17: "+3V3",
    2: "+5V", 4: "+5V",
    6: "GND", 9: "GND", 14: "GND", 20: "GND", 25: "GND", 30: "GND", 34: "GND", 39: "GND",
    3: "SDA",        # GPIO 2
    5: "SCL",        # GPIO 3
    7: "OW",         # GPIO 4   DS18B20 (1-Wire)
    11: "DHT",       # GPIO 17  DHT22
    12: "BUZZ",      # GPIO 18  buzzer (PWM)
    13: "REED",      # GPIO 27  door reed switch (internal pull-up)
    15: "MAINS",     # GPIO 22  12 V present (divider)
    16: "LED_R",     # GPIO 23
    18: "LED_G",     # GPIO 24
    22: "LOCK",      # GPIO 25  lock MOSFET gate (pulled down at boot)
    29: "ROW1", 31: "ROW2", 33: "ROW3", 35: "ROW4",   # GPIO 5, 6, 13, 19
    32: "COL1", 36: "COL2", 38: "COL3", 40: "COL4",   # GPIO 12, 16, 20, 21
    37: "SPARE",     # GPIO 26  kept free (e.g. a hardware acknowledge button)
}

# Footprint shortcuts
JST2 = "Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical"
JST3 = "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical"
JST4 = "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical"
SCREW2 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
RES = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"

# ---------------------------------------------------------------- parts
# ref: (symbol, value, footprint, {pin number: net}, group, note)
PARTS = {
    "J1": ("Connector_Generic:Conn_02x20_Odd_Even", "Pi GPIO socket",
           "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical",
           {str(p): n for p, n in PI_PINS.items()}, "pi", "2x20 female socket on the bottom side"),

    # Sensors
    "J2": ("Connector_Generic:Conn_01x03", "DS18B20", JST3, {"1": "+3V3", "2": "OW", "3": "GND"}, "sensors", ""),
    "R1": ("Device:R", "4.7k", RES, {"1": "+3V3", "2": "OW"}, "sensors", "1-Wire pull-up"),
    "J3": ("Connector_Generic:Conn_01x03", "DHT22", JST3, {"1": "+3V3", "2": "DHT", "3": "GND"}, "sensors", ""),
    "R2": ("Device:R", "10k", RES, {"1": "+3V3", "2": "DHT"}, "sensors",
           "DHT22 pull-up; leave out if the module has one (VERIFY)"),
    "J4": ("Connector_Generic:Conn_01x02", "Reed switch", JST2, {"1": "REED", "2": "GND"}, "sensors",
           "uses the Pi's internal pull-up"),

    # 12 V mains sense: 10k / 2.7k divider (2.55 V at 12 V), RC filter, 1k series, BAT54S clamp
    "J9": ("Connector_Generic:Conn_01x02", "12V sense in", SCREW2, {"1": "V12_SENSE", "2": "GND"}, "mains",
           "only the divider's ~1 mA; never the Peltier current"),
    "R3": ("Device:R", "10k", RES, {"1": "V12_SENSE", "2": "SENSE_DIV"}, "mains", ""),
    "R4": ("Device:R", "2.7k", RES, {"1": "SENSE_DIV", "2": "GND"}, "mains", ""),
    "C1": ("Device:C", "100n", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
           {"1": "SENSE_DIV", "2": "GND"}, "mains", "filters noise on the sense line"),
    "R5": ("Device:R", "1k", RES, {"1": "SENSE_DIV", "2": "MAINS"}, "mains", "limits the clamp current"),
    "D1": ("Diode:BAT54S", "BAT54S", "Package_TO_SOT_SMD:SOT-23",
           {"1": "GND", "2": "+3V3", "3": "MAINS"}, "mains", "clamps GPIO 22 between GND and 3.3 V"),

    # Buzzer (NPN low-side) and LED resistors
    "J6": ("Connector_Generic:Conn_01x02", "Buzzer", JST2, {"1": "+5V", "2": "BUZ_N"}, "outputs", ""),
    "R6": ("Device:R", "1k", RES, {"1": "BUZZ", "2": "Q1_B"}, "outputs", ""),
    "Q1": ("Transistor_BJT:BC547", "BC547", "Package_TO_SOT_THT:TO-92_Inline",
           {"1": "BUZ_N", "2": "Q1_B", "3": "GND"}, "outputs", "C-B-E pin order (VERIFY on the part)"),
    "D2": ("Diode:1N4148", "1N4148", "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
           {"1": "+5V", "2": "BUZ_N"}, "outputs", "across the buzzer coil"),
    "J5": ("Connector_Generic:Conn_01x03", "LEDs", JST3, {"1": "LED_R_A", "2": "LED_G_A", "3": "GND"}, "outputs", ""),
    "R7": ("Device:R", "330", RES, {"1": "LED_R", "2": "LED_R_A"}, "outputs", "red LED"),
    "R8": ("Device:R", "330", RES, {"1": "LED_G", "2": "LED_G_A"}, "outputs", "green LED"),

    # Solenoid lock: logic-level MOSFET low-side switch, own 5 V adapter
    "J10": ("Connector_Generic:Conn_01x02", "Lock 5V in", SCREW2, {"1": "+5V_LOCK", "2": "GND"}, "lock",
            "separate 5 V 2 A adapter; its GND joins the Pi GND here"),
    "J11": ("Connector_Generic:Conn_01x02", "Solenoid", SCREW2, {"1": "+5V_LOCK", "2": "LOCK_N"}, "lock", ""),
    "R9": ("Device:R", "100", RES, {"1": "LOCK", "2": "GATE"}, "lock", "gate series resistor"),
    "R10": ("Device:R", "10k", RES, {"1": "GATE", "2": "GND"}, "lock", "keeps the lock OFF when the Pi is off"),
    "Q2": ("Transistor_FET:AO3400A", "AO3400A", "Package_TO_SOT_SMD:SOT-23",
           {"1": "GATE", "2": "GND", "3": "LOCK_N"}, "lock",
           "logic-level at 3.3 V, 5.7 A; the breadboard uses an IRLB8721 instead (docs/wiring.md)"),
    "D3": ("Diode:1N4007", "1N4007", "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
           {"1": "+5V_LOCK", "2": "LOCK_N"}, "lock", "flyback diode across the solenoid"),

    # I2C level shifter for the 5 V LCD backpack (two BSS138, docs/wiring.md D13)
    "Q3": ("Transistor_FET:BSS138", "BSS138", "Package_TO_SOT_SMD:SOT-23",
           {"1": "+3V3", "2": "SDA", "3": "SDA_5V"}, "i2c", ""),
    "Q4": ("Transistor_FET:BSS138", "BSS138", "Package_TO_SOT_SMD:SOT-23",
           {"1": "+3V3", "2": "SCL", "3": "SCL_5V"}, "i2c", ""),
    "R11": ("Device:R", "10k", RES, {"1": "+5V", "2": "SDA_5V"}, "i2c",
            "5 V side pull-up; the 3.3 V side uses the Pi's own 1.8k pull-ups"),
    "R12": ("Device:R", "10k", RES, {"1": "+5V", "2": "SCL_5V"}, "i2c", ""),
    "J7": ("Connector_Generic:Conn_01x04", "LCD I2C", JST4,
           {"1": "GND", "2": "+5V", "3": "SDA_5V", "4": "SCL_5V"}, "i2c", "same order as the PCF8574 backpack"),

    # Keypad and spare
    "J8": ("Connector_Generic:Conn_01x08", "Keypad", "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
           {"1": "ROW1", "2": "ROW2", "3": "ROW3", "4": "ROW4", "5": "COL1", "6": "COL2", "7": "COL3", "8": "COL4"},
           "keypad", "ribbon order VERIFY"),
    "J12": ("Connector_Generic:Conn_01x02", "Spare GPIO26", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
            {"1": "SPARE", "2": "GND"}, "keypad", ""),

    # Mounting holes on the HAT pattern (58 x 49 mm), M2.5
    **{"H%d" % k: ("Mechanical:MountingHole", "M2.5", "MountingHole:MountingHole_2.7mm_M2.5", {}, "mech",
                   "M2.5 spacer to the Pi") for k in range(1, 5)},
}

GROUP_TITLES = {
    "pi": "Raspberry Pi 40-pin header",
    "sensors": "Sensors: DS18B20, DHT22, reed switch",
    "mains": "12 V mains sense (2.55 V at 12 V, 3.19 V at 15 V)",
    "outputs": "Buzzer driver and LED resistors",
    "lock": "Solenoid lock driver (separate 5 V adapter)",
    "i2c": "I2C level shifter for the 5 V LCD backpack",
    "keypad": "Keypad and spare GPIO",
    "mech": "Mounting holes (Pi HAT pattern)",
}

# Nets that carry the lock current (~1 A, VERIFY): wide tracks, see make_pcb.py
POWER_NETS = {"+5V_LOCK": 1.0, "LOCK_N": 1.0, "+5V": 0.5, "GND": 0.5}


def nets():
    """net -> list of (ref, pin)."""
    result = {}
    for ref, (_, _, _, pins, _, _) in PARTS.items():
        for pin, net in pins.items():
            result.setdefault(net, []).append((ref, pin))
    return result


if __name__ == "__main__":
    for net, pins in sorted(nets().items()):
        print("%-10s %s" % (net, " ".join("%s.%s" % p for p in pins)))
