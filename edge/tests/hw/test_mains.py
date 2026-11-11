"""12 V mains sense through the 10k / 2.7k divider. Run: python -m tests.hw.test_mains"""
from tests.hw.common import banner, stop_if_service_running, watch

WIRING = """
12 V (+), after the fuse -> 10 kOhm -> node -> 2.7 kOhm -> GND
node -> 100 nF -> GND
node -> 1 kOhm -> GPIO 22 (pin 15)
12 V adapter (-) -> Pi GND (common ground!)
BEFORE connecting to the Pi: measure the node with a multimeter. 12 V in -> about 2.55 V.
It must be below 3.3 V. If it is higher, STOP and check the resistor values.
"""


def main():
    stop_if_service_running()
    from gpiozero import DigitalInputDevice
    banner("Mains test: plug and unplug the 12 V adapter a few times in 30 s.", WIRING)
    sense = DigitalInputDevice(22, pull_up=None, active_state=True)
    changes = watch(lambda: sense.value, lambda v: "POWER PRESENT" if v else "POWER LOST", 30)
    print("PASS" if changes >= 2 else "FAIL: no change seen. Measure the divider node voltage.")


if __name__ == "__main__":
    main()
