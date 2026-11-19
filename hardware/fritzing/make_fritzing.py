"""Build the Fritzing breadboard model of the cold chain node: coldchain.fzz.

Run:  python make_fritzing.py          (needs: pip install svgelements)
The wiring follows docs/wiring.md (the reduced design we build on the breadboard).

Layout (breadboard view, Fritzing units: 9 = 0.1 in):
- Raspberry Pi turned 180 degrees above the breadboard, so its 40-pin header sits right above
  breadboard columns 28 (pins 39/40) to 47 (pins 1/2).
- Top rails: + = 3.3 V, - = GND.  Bottom rails: + = 5 V, - = GND.
- Top half of the breadboard: 3.3 V circuits (12 V sense divider, reed switch, DS18B20, DHT22).
- Bottom half: 5 V circuits (buzzer transistor, LEDs) and the lock diode.
- Off the breadboard: 12 V supply, fuse, W1209 thermostat, car relay and Peltier (left), level shifter,
  LCD and keypad (right), relay module, lock supply and solenoid (below).
"""
import os
import sys

import custom_parts
from fzlib import Sketch

HERE = os.path.dirname(os.path.abspath(__file__))
FRITZING_DIR = os.environ.get(
    "FRITZING_DIR",
    r"C:/Users/samue/Downloads/fritzing Software/fritzing Software/fritzing Software")
PARTS = os.path.join(FRITZING_DIR, "fritzing-parts")

# wire colours (docs/wiring.md colour code)
RED, ORANGE, BLACK = "#cc1414", "#ff7033", "#404040"
YELLOW, WHITE, BLUE, PINK = "#ffe24d", "#ffffff", "#418dd9", "#ff8fc6"
PURPLE, BROWN, GREEN, CYAN = "#ab58a2", "#8c3b00", "#47cc79", "#33d6c4"
GREY, OCHRE = "#999999", "#c8a000"


def pi_pin(p):
    """Physical header pin (1-40) -> connector id of the Fritzing 'Raspberry Pi 3' part."""
    if p % 2:
        return f"connector{(p - 1) // 2}"
    return f"connector{40 - p // 2}"


def build():
    sk = Sketch(PARTS)
    cp = custom_parts.build_all()

    # ------------------------------------------------------------ main boards
    bb = sk.core_part("core/breadboard2.fzp", "Breadboard-RSR03MB102-ModuleID", "Breadboard",
                      0, 300, kind="breadboard")

    def h(col, row):
        """Breadboard hole name, e.g. h(12, 'J') -> 'pin12J'. Rails: W/X bottom, Y/Z top."""
        return f"pin{col}{row}"

    pi = sk.core_part("core/Raspberry Pi 3.fzp", "raspberry_pi_3_rev-1.2",
                      "Raspberry Pi 4 (Fritzing Pi 3 part: same 40-pin header)",
                      150.05, 20, angle=180, sch=(0, 0), pcb=(0, 0))
    # check the header really sits over the breadboard columns
    x_pin1 = pi.at(pi_pin(1))[0]
    x_col47 = bb.at(h(47, "J"))[0]
    if abs(x_pin1 - x_col47) > 0.5:
        sys.exit(f"Pi header not aligned with the breadboard: {x_pin1} vs {x_col47}")

    y_odd = pi.at(pi_pin(1))[1]       # inner header row (odd pins)
    y_even = pi.at(pi_pin(2))[1]      # outer header row (even pins)

    def from_pi(p, lane, to_x, end_y=None):
        """Bend points for a wire leaving header pin p: odd pins first step between two
        columns so they do not run over the even pin below them."""
        x = pi.at(pi_pin(p))[0]
        pts = []
        if p % 2:
            x -= 4.5
            pts.append((x, y_odd + 4.5))
        pts.append((x, lane))
        pts.append((to_x, lane))
        if end_y is not None:
            pts.append((to_x, end_y))
        return pts

    def hx(col):
        return bb.at(h(col, "J"))[0]

    def two_leg(rel, module_id, title, pin_a, hole_a, pin_b, hole_b, lift=4.0, props=None, sch=(0, 0)):
        """A two-leg part (resistor, diode, capacitor...) centred over its two holes."""
        it = sk.core_part(rel, module_id, title, 0, 0, props=props, sch=sch, pcb=sch)
        sk.center_on(it, pin_a, bb.at(hole_a), pin_b, bb.at(hole_b), lift)
        sk.leg(it, pin_a, bb, hole_a)
        sk.leg(it, pin_b, bb, hole_b)
        return it

    RES, RES_ID = "core/resistor.fzp", "ResistorModuleID"

    # Each wire that leaves the header gets its own horizontal lane between the Pi and the
    # breadboard (y = 224 ... 290), so no two wires run on top of each other.
    lane_order = [2, 9, 22, 5, 3, 29, 31, 33, 35, 32, 36, 38, 40, 1, 7, 11, 15, 13, 12, 16, 18]
    lane = {p: 224 + 3.3 * k for k, p in enumerate(lane_order)}

    # ------------------------------------------------------------ power rails
    # 3.3 V: pin 1 -> top + rail (Y).  GND: pin 6 -> top - rail (Z).
    sk.wire(pi, pi_pin(1), bb, h(48, "Y"), ORANGE, via=from_pi(1, lane[1], hx(48)))
    sk.wire(pi, pi_pin(6), bb, h(45, "Z"), BLACK)
    # 5 V: pin 2 -> bottom + rail (W); GND: pin 9 -> bottom - rail (X); both round the right end
    w61, x60 = bb.at(h(61, "W")), bb.at(h(60, "X"))
    sk.wire(pi, pi_pin(2), bb, h(61, "W"), RED, via=from_pi(2, lane[2], 596) + [(596, w61[1])])
    sk.wire(pi, pi_pin(9), bb, h(60, "X"), BLACK, via=from_pi(9, lane[9], 592) + [(592, x60[1])])

    # ------------------------------------------------------------ 12 V mains sense (top left)
    # columns: 3 = 12 V node, 7 = sense node, 11 = GPIO 22 node
    r3 = two_leg("core/resistor.fzp", "ResistorModuleID", "R3 10k", "connector0", h(3, "I"), "connector1", h(7, "I"),
                 props={"resistance": "10k"}, sch=(500, 0))
    r4 = two_leg("core/resistor.fzp", "ResistorModuleID", "R4 2.7k", "connector0", h(7, "H"), "connector1", h(10, "Z"),
                 props={"resistance": "2.7k"}, sch=(500, 40))
    c1 = two_leg("core/capacitor_ceramic_100mil.fzp", "100milCeramicCapacitorModuleID", "C1 100nF",
                 "connector0", h(7, "G"), "connector1", h(9, "Z"), lift=12,
                 props={"capacitance": "100nF"}, sch=(500, 80))
    r5 = two_leg("core/resistor.fzp", "ResistorModuleID", "R5 1k", "connector0", h(7, "F"), "connector1", h(11, "F"),
                 props={"resistance": "1k"}, sch=(500, 120))
    # D1: anode on the GPIO node, cathode (stripe) to 3.3 V
    d1 = two_leg("core/diode_schottky_1N5817_300mil.fzp", "145554CBFC44diode", "D1 1N5819 clamp",
                 "connector1", h(11, "G"), "connector0", h(13, "Y"), sch=(500, 160))
    sk.wire(pi, pi_pin(15), bb, h(11, "J"), PINK, via=from_pi(15, lane[15], hx(11)))

    # ------------------------------------------------------------ reed switch (top, columns 16-22)
    reed = two_leg("core/reedSwitch_500mil.fzp", "c0e65b2d0c9003507cf4a3222e995a45", "Door reed switch",
                   "connector0", h(16, "H"), "connector1", h(22, "H"), lift=2, sch=(500, 200))
    sk.wire(pi, pi_pin(13), bb, h(16, "J"), BLUE, via=from_pi(13, lane[13], hx(16)))
    sk.wire(bb, h(22, "J"), bb, h(22, "Z"), BLACK)

    # ------------------------------------------------------------ DS18B20 (top right, columns 50-52)
    probe = cp["coldchain-ds18b20-probe-v1"]
    ds = sk.custom_part(probe, "DS18B20 waterproof probe (wire colours VERIFY)", 0, 0, sch=(250, 0), pcb=(250, 0))
    gnd_local = ds.geo.pins[ds.cid("GND")]
    ds.x = bb.at(h(50, "H"))[0] - gnd_local[0]
    ds.y = bb.at(h(50, "H"))[1] - gnd_local[1]
    sk.plug(ds, "GND", bb, h(50, "H"))
    sk.plug(ds, "DQ", bb, h(51, "H"))
    sk.plug(ds, "VDD", bb, h(52, "H"))
    # the probe's cable covers the rails over columns 50-57, so its rail links use columns 46-49
    sk.wire(bb, h(50, "J"), bb, h(49, "Z"), BLACK)
    sk.wire(bb, h(52, "J"), bb, h(49, "Y"), ORANGE, via=[(bb.at(h(52, "J"))[0], 336), (bb.at(h(49, "Y"))[0], 336)])
    r1 = two_leg("core/resistor.fzp", "ResistorModuleID", "R1 4.7k", "connector0", h(51, "I"), "connector1", h(46, "Y"),
                 props={"resistance": "4.7k"}, sch=(500, 240))
    sk.wire(pi, pi_pin(7), bb, h(51, "J"), YELLOW, via=from_pi(7, lane[7], hx(51)))

    # ------------------------------------------------------------ DHT22 (top right, columns 59-62)
    dht = sk.core_part("core/Humidity_and_Temperature_Sensor_RHT03.fzp",
                       "Humidity_and_Temperature_Sensor_RHT03_6", "DHT22 (AM2302)", 0, 0,
                       sch=(250, 100), pcb=(250, 100))
    vcc_local = dht.geo.pins["connector8"]
    dht.x = bb.at(h(59, "H"))[0] - vcc_local[0]
    dht.y = bb.at(h(59, "H"))[1] - vcc_local[1]
    sk.plug(dht, "connector8", bb, h(59, "H"))            # pin 1 VCC
    sk.plug(dht, "connector9", bb, h(60, "H"))            # pin 2 DATA
    sk.plug(dht, "connector10", bb, h(61, "H"), tol=2.5)  # pin 3, not connected
    sk.plug(dht, "connector11", bb, h(62, "H"))           # pin 4 GND
    sk.wire(bb, h(59, "J"), bb, h(58, "Y"), ORANGE)
    sk.wire(bb, h(62, "J"), bb, h(60, "Z"), BLACK)
    r2 = two_leg("core/resistor.fzp", "ResistorModuleID", "R2 10k", "connector0", h(60, "I"), "connector1", h(61, "Y"),
                 props={"resistance": "10k"}, sch=(500, 280))
    sk.wire(pi, pi_pin(11), bb, h(60, "J"), WHITE, via=from_pi(11, lane[11], hx(60)))

    # ------------------------------------------------------------ buzzer driver (bottom left)
    # Q1 2N2222 (E B C) in columns 4, 5, 6, row C
    q1 = sk.core_part("core/transistor_signal_NPN_TO92_EBC.fzp", "NPN-to92-ebc", "Q1 2N2222 (VERIFY pin order)",
                      bb.at(h(4, "C"))[0] - 1.35, bb.at(h(4, "C"))[1] - 30.1 - 3, sch=(250, 200), pcb=(250, 200))
    sk.leg(q1, "connector0", bb, h(4, "C"))   # E
    sk.leg(q1, "connector1", bb, h(5, "C"))   # B
    sk.leg(q1, "connector2", bb, h(6, "C"))   # C
    sk.wire(bb, h(4, "A"), bb, h(4, "X"), BLACK)
    r6 = two_leg("core/resistor.fzp", "ResistorModuleID", "R6 1k", "connector0", h(5, "E"), "connector1", h(9, "E"),
                 props={"resistance": "1k"}, sch=(500, 320))
    # D2 across the buzzer: anode on the collector, cathode (stripe) to 5 V
    d2 = two_leg("core/diode_1N4001_300mil.fzp", "3254CBFC44diode", "D2 1N4148",
                 "connector1", h(6, "B"), "connector0", h(10, "W"), lift=-4, sch=(500, 360))
    buz = sk.core_part("core/sparkfun-electromechanical-buzzer-pth.fzp", "SparkFun-Electromechanical-BUZZER-PTH",
                       "Buzzer (polarity VERIFY)", 10, 515, sch=(250, 300), pcb=(250, 300))
    sk.wire(buz, "connector1", bb, h(6, "A"), BLACK, via=[(buz.at("connector1")[0], 500), (bb.at(h(6, "A"))[0], 500)])
    sk.wire(buz, "connector0", bb, h(11, "W"), RED,
            via=[(buz.at("connector0")[0] + 40, buz.at("connector0")[1]),
                 (buz.at("connector0")[0] + 40, 505), (bb.at(h(11, "W"))[0], 505)])
    sk.wire(pi, pi_pin(12), bb, h(9, "D"), PURPLE,
            via=from_pi(12, lane[12], -12) + [(-12, 392), (bb.at(h(9, "D"))[0], 392)])

    # ------------------------------------------------------------ LEDs (bottom middle)
    led_r = sk.core_part("core/LED-generic-5mm.fzp", "5mmColorLEDModuleID", "Red LED (alarm)",
                         bb.at(h(14, "C"))[0] - 5.66, 390, props={"color": "Red (633nm)"},
                         sch=(250, 400), pcb=(250, 400))
    sk.leg(led_r, "connector0", bb, h(14, "C"))   # cathode
    sk.leg(led_r, "connector1", bb, h(15, "C"))   # anode
    sk.wire(bb, h(14, "A"), bb, h(13, "X"), BLACK)
    r7 = two_leg("core/resistor.fzp", "ResistorModuleID", "R7 330", "connector0", h(15, "E"), "connector1", h(19, "E"),
                 props={"resistance": "330"}, sch=(500, 400))
    sk.wire(pi, pi_pin(16), bb, h(19, "D"), BROWN,
            via=from_pi(16, lane[16], -6) + [(-6, 396), (bb.at(h(19, "D"))[0], 396)])

    led_g = sk.core_part("core/LED-generic-5mm.fzp", "5mmColorLEDModuleID", "Green LED (OK)",
                         bb.at(h(22, "C"))[0] - 5.66, 390, props={"color": "Green (570nm)"},
                         sch=(250, 450), pcb=(250, 450))
    sk.leg(led_g, "connector0", bb, h(22, "C"))
    sk.leg(led_g, "connector1", bb, h(23, "C"))
    sk.wire(bb, h(22, "A"), bb, h(21, "X"), BLACK)
    r8 = two_leg("core/resistor.fzp", "ResistorModuleID", "R8 330", "connector0", h(23, "E"), "connector1", h(27, "E"),
                 props={"resistance": "330"}, sch=(500, 440))
    sk.wire(pi, pi_pin(18), bb, h(27, "D"), GREEN,
            via=from_pi(18, lane[18], 0) + [(0, 399.5), (bb.at(h(27, "D"))[0], 399.5)])

    # ------------------------------------------------------------ level shifter + LCD (right)
    ls = sk.core_part("core/I2C level shifter bidirectional.fzp",
                      "I2C_level_converter_444e27d4b4b231371fe2ccfc428902c1_1",
                      "Level shifter (BSS138, 4 channels)", 610, 185, sch=(750, 0), pcb=(750, 0))
    lcd = sk.custom_part(cp["coldchain-lcd16x2-i2c-v1"], "LCD 16x2 + I2C backpack", 720, -10,
                         sch=(750, 150), pcb=(750, 150))
    sk.wire(pi, pi_pin(3), ls, "LV1", CYAN, via=from_pi(3, lane[3], ls.at("LV1")[0]))
    sk.wire(pi, pi_pin(5), ls, "LV2", GREY, via=from_pi(5, lane[5], ls.at("LV2")[0]))
    y59, z61 = bb.at(h(59, "Y")), bb.at(h(61, "Z"))
    sk.wire(ls, "LV", bb, h(59, "Y"), ORANGE, via=[(ls.at("LV")[0], 294), (y59[0], 294)])
    sk.wire(ls, "connector2", bb, h(61, "Z"), BLACK, via=[(ls.at("connector2")[0], 297), (z61[0], 297)])
    # 5 V side: LCD SDA/SCL from HV1/HV2; LCD power from the shifter's HV and GND pins
    # (the same 5 V and GND nets as the rails: HV -> bottom + rail)
    sk.wire(ls, "HV1", lcd, "SDA", CYAN, via=[(ls.at("HV1")[0], lcd.at("SDA")[1])])
    sk.wire(ls, "HV2", lcd, "SCL", GREY, via=[(ls.at("HV2")[0], lcd.at("SCL")[1])])
    sk.wire(ls, "HV", lcd, "VCC", RED, via=[(ls.at("HV")[0], lcd.at("VCC")[1])])
    sk.wire(ls, "connector9", lcd, "GND", BLACK, via=[(ls.at("connector9")[0], lcd.at("GND")[1])])
    w57 = bb.at(h(57, "W"))
    sk.wire(ls, "HV", bb, h(57, "W"), RED,
            via=[(ls.at("HV")[0], 175), (682, 175), (682, 493), (w57[0], 493)])

    # ------------------------------------------------------------ keypad (far right)
    kp = sk.custom_part(cp["coldchain-keypad-4x4-v1"], "4x4 keypad", 1030, -150, sch=(750, 300), pcb=(750, 300))
    keypad_pins = [("R1", 29), ("R2", 31), ("R3", 33), ("R4", 35),
                   ("C1", 32), ("C2", 36), ("C3", 38), ("C4", 40)]
    for name, p in keypad_pins:
        col = YELLOW if name[0] == "R" else CYAN
        sk.wire(pi, pi_pin(p), kp, name, col, via=from_pi(p, lane[p], kp.at(name)[0]))

    # ------------------------------------------------------------ 12 V supply, fuse, W1209, Peltier (left)
    jack12 = sk.core_part("core/Power plug.fzp", "d8f570d723ea4d14f9b61b34575a9699",
                          "12 V 30 A supply (certified)", -360, 150, sch=(0, 400), pcb=(0, 400))
    fuse = sk.core_part("core/Fuse_with_Handler.fzp", "fuse_with_handler_cff5", "F1 15 A fuse",
                        -270, 152, sch=(0, 500), pcb=(0, 500))
    th = sk.custom_part(cp["coldchain-w1209-thermostat-v1"], "W1209 thermostat", -330, 200,
                        sch=(0, 600), pcb=(0, 600))
    pel = sk.core_part("core/peltier element.fzp", "93d4585be720f3982141f4d032f44c8e",
                       "Peltier kit 120 W (8-10 A)", -110, 230, sch=(0, 700), pcb=(0, 700))
    for c in ("connector0", "connector1"):      # short straight leads below the module
        start = pel.geo.legs[c][0]
        sk.leg_free(pel, c, (pel.x + start[0], pel.y + start[1] + 12))
    # the car relay switches the Peltier's 8-10 A; the W1209 relay only switches the car relay's coil
    kr = sk.custom_part(cp["coldchain-car-relay-12v-v1"], "Car relay 12 V 30-40 A", -130, 420,
                        sch=(0, 900), pcb=(0, 900))
    f_out = fuse.at("connector1")
    sk.wire(jack12, "VCC", fuse, "connector0", RED)
    sk.wire(fuse, "connector1", th, "+12V", RED,
            via=[(f_out[0] + 10, f_out[1]), (f_out[0] + 10, 185), (th.at("+12V")[0] - 14, 185),
                 (th.at("+12V")[0] - 14, th.at("+12V")[1])])
    sk.wire(fuse, "connector1", th, "RELAY A", RED,
            via=[(-140, f_out[1]), (-140, th.at("RELAY A")[1])])
    sk.wire(fuse, "connector1", kr, "30", RED,
            via=[(-140, f_out[1]), (-140, 400), (-30, 400), (-30, kr.at("30")[1])])
    sk.wire(th, "RELAY B", kr, "86", ORANGE,
            via=[(-150, th.at("RELAY B")[1]), (-150, kr.at("86")[1])])
    sk.wire(kr, "87", pel, "connector0", RED,
            via=[(-15, kr.at("87")[1]), (-15, 372), (pel.at("connector0")[0], 372)])
    sk.wire(kr, "85", th, "GND", BLACK,
            via=[(-135, kr.at("85")[1]), (-135, 515), (-352, 515), (-352, th.at("GND")[1])])
    # D4 1N4007 across the relay coil: cathode (stripe) on 86, anode on 85
    d4 = sk.core_part("core/diode_1N4001_300mil.fzp", "3254CBFC44diode", "D4 1N4007 (coil)",
                      -205, 456, sch=(500, 540), pcb=(500, 540))
    sk.leg_free(d4, "connector0", (-208, 465))
    sk.leg_free(d4, "connector1", (-163, 465))
    sk.wire(d4, "connector0", kr, "86", ORANGE, via=[(-208, kr.at("86")[1] - 4), (-121 - 6, kr.at("86")[1] - 4),
                                                    (-121 - 6, kr.at("86")[1])])
    sk.wire(d4, "connector1", kr, "85", BLACK, via=[(-163, kr.at("85")[1] + 4), (-128, kr.at("85")[1] + 4),
                                                   (-128, kr.at("85")[1])])
    j3 = bb.at(h(3, "J"))
    sk.wire(fuse, "connector1", bb, h(3, "J"), RED,
            via=[(f_out[0] + 10, f_out[1]), (f_out[0] + 10, 140), (j3[0] - 4.5, 140), (j3[0] - 4.5, j3[1])])
    # ground: supply - -> W1209 GND; Peltier - -> W1209 GND; W1209 GND -> bottom - rail (common ground)
    sk.wire(jack12, "connector0", th, "GND", BLACK,
            via=[(jack12.at("connector0")[0] + 6, jack12.at("connector0")[1]),
                 (jack12.at("connector0")[0] + 6, 190), (-345, 190), (-345, th.at("GND")[1])])
    sk.wire(pel, "connector1", th, "GND", BLACK,
            via=[(pel.at("connector1")[0], 360), (-345, 360), (-345, th.at("GND")[1])])
    x3 = bb.at(h(3, "X"))
    sk.wire(th, "GND", bb, h(3, "X"), BLACK,
            via=[(-345, th.at("GND")[1]), (-345, 500), (x3[0] - 4.5, 500), (x3[0] - 4.5, x3[1])])

    # ------------------------------------------------------------ lock: relay module, own supply, solenoid (below)
    # breadboard columns 55 (lock +) and 59 (lock -) carry the flyback diode D3
    rel = sk.custom_part(cp["coldchain-relay-module-5v-v1"], "Relay module 5 V (trigger level VERIFY)",
                         300, 540, sch=(250, 550), pcb=(250, 550))
    sk.wire(rel, "VCC", bb, h(33, "W"), RED, via=[(rel.at("VCC")[0] - 12, rel.at("VCC")[1]),
                                                   (rel.at("VCC")[0] - 12, 520), (bb.at(h(33, "W"))[0], 520)])
    sk.wire(rel, "GND", bb, h(31, "X"), BLACK, via=[(rel.at("GND")[0] - 18, rel.at("GND")[1]),
                                                     (rel.at("GND")[0] - 18, 512), (bb.at(h(31, "X"))[0], 512)])
    sk.wire(pi, pi_pin(22), rel, "IN", OCHRE,
            via=from_pi(22, lane[22], 600) + [(600, 528), (rel.at("IN")[0] - 24, 528),
                                          (rel.at("IN")[0] - 24, rel.at("IN")[1])])
    # D3 across the solenoid: cathode (stripe) to lock +, anode to lock -
    d3 = two_leg("core/diode_1N4001_300mil.fzp", "3254CBFC44diode", "D3 1N4007 (flyback)",
                 "connector0", h(55, "C"), "connector1", h(59, "C"), sch=(500, 500))
    jack5 = sk.core_part("core/Power plug.fzp", "d8f570d723ea4d14f9b61b34575a9699",
                         "Lock supply (own adapter, 5 V or 12 V: VERIFY the lock)", 560, 640,
                         sch=(0, 800), pcb=(0, 800))
    sol = sk.core_part("core/solenoid.fzp", "9f2b90fcf9c65c9bc09d570e3442069e", "Solenoid lock",
                       690, 500, sch=(250, 650), pcb=(250, 650))
    for c in ("connector0", "connector1"):
        start = sol.geo.legs[c][0]
        sk.leg_free(sol, c, (sol.x + start[0], sol.y + start[1] + 12))
    sk.wire(jack5, "VCC", rel, "COM", RED,
            via=[(jack5.at("VCC")[0] + 10, jack5.at("VCC")[1]), (jack5.at("VCC")[0] + 10, 600),
                 (rel.at("COM")[0] + 14, 600), (rel.at("COM")[0] + 14, rel.at("COM")[1])])
    sk.wire(rel, "NO", bb, h(55, "A"), RED,
            via=[(rel.at("NO")[0] + 20, rel.at("NO")[1]), (rel.at("NO")[0] + 20, 500),
                 (bb.at(h(55, "A"))[0], 500)])
    sk.wire(sol, "connector0", bb, h(55, "B"), RED,
            via=[(sol.at("connector0")[0], 660), (650, 660), (650, 496), (bb.at(h(55, "B"))[0] + 4.5, 496),
                 (bb.at(h(55, "B"))[0] + 4.5, bb.at(h(55, "B"))[1])])
    sk.wire(sol, "connector1", bb, h(59, "B"), BLACK,
            via=[(sol.at("connector1")[0], 668), (660, 668), (660, 490), (bb.at(h(59, "B"))[0], 490)])
    sk.wire(jack5, "connector0", bb, h(59, "A"), BLACK,
            via=[(jack5.at("connector0")[0] + 16, jack5.at("connector0")[1]),
                 (jack5.at("connector0")[0] + 16, 486), (bb.at(h(59, "A"))[0] + 4.5, 486),
                 (bb.at(h(59, "A"))[0] + 4.5, bb.at(h(59, "A"))[1])])

    # ------------------------------------------------------------ notes
    sk.note(-380, -40, 300, 85, [
        "IoT cold chain node: breadboard model (design review)",
        "Wiring list: docs/wiring.md. Top rails: + = 3.3 V, - = GND.",
        "Bottom rails: + = 5 V, - = GND. Both GND rails meet at the Pi.",
        "The Pi is a Raspberry Pi 4; Fritzing has only the Pi 3 part,",
        "which has the same 40-pin header.",
    ])
    sk.note(-380, 540, 300, 100, [
        "12 V side (left): the Peltier kit's 8-10 A runs only",
        "supply -> F1 15 A fuse -> car relay -> Peltier and fans.",
        "The W1209 switches only the car relay's coil.",
        "It never flows through the breadboard or the Pi.",
        "Only the 10k/2.7k divider (about 1 mA) senses 12 V.",
        "Nobody touches 230 V: only certified adapters.",
    ])
    sk.note(300, 650, 240, 72, [
        "Lock (extension): the relay contacts switch the lock's",
        "own supply. The lock must stay OFF at start-up:",
        "use a module that switches on with a HIGH input",
        "(VERIFY the trigger level on the module).",
    ])
    return sk


if __name__ == "__main__":
    sketch = build()
    out = os.path.join(HERE, "coldchain.fzz")
    sketch.save(out, "coldchain")
    print("wrote", out, "-", len(sketch.items), "parts,", len(sketch.wires), "wire segments")
