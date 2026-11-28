"""12 V mains sense through a divider (two resistors or a potentiometer).

Run:  python -m tests.hw.test_mains         30 s test: plug and unplug the 12 V, PASS after 2 changes
      python -m tests.hw.test_mains live    live view until Ctrl+C: pin level and flicker count,
                                            on the LCD and in the terminal (to set the potentiometer)

The Pi has no analog input: GPIO 22 only reads HIGH or LOW, never the voltage. Measure the voltage
itself with a multimeter (pin 15 to GND).
"""
import sys
import time

from tests.hw.common import banner, lcd_show, say, stop_if_service_running, watch

WIRING = """
12 V (+), after the fuse -> divider -> sense node -> 1 kOhm -> GPIO 22 (pin 15)
  divider = 10 kOhm (top) + 2.7 kOhm (bottom), or a potentiometer >= 10 kOhm:
  outer legs to 12 V and GND, middle leg = sense node
sense node -> 100 nF -> GND;  1N5819 from the pin 15 row (anode) to 3.3 V (stripe)
12 V adapter (-) -> Pi GND (common ground!)
BEFORE connecting to the Pi: measure the sense node with a multimeter. 12 V in -> about 2.5 V.
It must be below 3.3 V. If it is higher, STOP (resistor values or the pot setting).
"""


def live(sense):
    """Print and show the level every 0.5 s, with how often it flickered in that half second."""
    print("Live view, Ctrl+C to stop. 'flicker' > 0 with a steady 12 V = pot set too close to the edge.")
    start = time.monotonic()
    total_flips = 0
    last = sense.value
    try:
        while True:
            flips = 0
            high_samples = samples = 0
            window_end = time.monotonic() + 0.5
            while time.monotonic() < window_end:      # sample every 5 ms for half a second
                value = sense.value
                if value != last:
                    flips += 1
                    last = value
                high_samples += value
                samples += 1
                time.sleep(0.005)
            total_flips += flips
            high_pct = 100 * high_samples // max(1, samples)
            state = "PRESENT" if high_pct >= 50 else "LOST"
            level = "HIGH" if high_pct == 100 else "LOW" if high_pct == 0 else "MIXED"
            print("%7.1f s  pin15 %-5s (%3d%% high)  POWER %-7s  flicker %d  (total %d)"
                  % (time.monotonic() - start, level, high_pct, state, flips, total_flips))
            lcd_show("Pin15 %s %3d%%" % (level, high_pct), "%s flick %d" % (state, flips))
    except KeyboardInterrupt:
        say("12V live stopped", "flickers: %d" % total_flips)


def main():
    stop_if_service_running()
    from gpiozero import DigitalInputDevice
    sense = DigitalInputDevice(22, pull_up=None, active_state=True)
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        banner("Mains live view (GPIO 22, pin 15)", WIRING)
        live(sense)
        return
    banner("Mains test: plug and unplug the 12 V adapter a few times in 30 s.", WIRING)
    changes = watch(lambda: sense.value, lambda v: "POWER PRESENT" if v else "POWER LOST", 30,
                    lcd_title="12V sense 30 s")
    if changes >= 2:
        say("12V sense test", "PASS")
    else:
        say("12V sense FAIL", "no change seen")
        print("Measure the sense node voltage.")


if __name__ == "__main__":
    main()
