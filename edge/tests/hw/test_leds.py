"""Red and green LEDs. Run: python -m tests.hw.test_leds"""
import time

from tests.hw.common import banner, stop_if_service_running

WIRING = """
GPIO 23 (pin 16) -> 330 Ohm -> red LED anode (long leg); cathode -> GND
GPIO 24 (pin 18) -> 330 Ohm -> green LED anode (long leg); cathode -> GND
"""


def main():
    stop_if_service_running()
    from gpiozero import LED
    banner("LED test: red and green take turns 5 times.", WIRING)
    red, green = LED(23), LED(24)
    try:
        for _ in range(5):
            red.on()
            green.off()
            time.sleep(0.5)
            red.off()
            green.on()
            time.sleep(0.5)
    finally:
        red.off()
        green.off()
    print("If an LED stays dark: it is probably the wrong way round (long leg to the resistor).")


if __name__ == "__main__":
    main()
