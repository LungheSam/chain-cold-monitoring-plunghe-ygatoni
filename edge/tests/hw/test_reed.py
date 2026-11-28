"""Reed switch (door). Run: python -m tests.hw.test_reed  (uses REED_INVERTED from .env)"""
import os

from dotenv import load_dotenv

from tests.hw.common import banner, say, stop_if_service_running, watch

WIRING = """
Reed switch wire 1 -> GPIO 27 (pin 13)   (internal pull-up is used)
Reed switch wire 2 -> GND (pin 14)
Expected: magnet near = DOOR CLOSED. If it is the other way round, set REED_INVERTED=1 in .env
(or back to 0) and run again.
"""


def main():
    stop_if_service_running()
    from gpiozero import Button
    banner("Reed test: move the magnet towards and away from the switch for 30 s.", WIRING)
    load_dotenv(".env")
    inverted = os.environ.get("REED_INVERTED", "0") == "1"
    print("REED_INVERTED=%d" % inverted)
    reed = Button(27, pull_up=True)
    changes = watch(lambda: reed.is_pressed != inverted, lambda closed: "DOOR CLOSED" if closed else "DOOR OPEN", 30,
                    lcd_title="Reed test 30 s")
    if changes >= 2:
        say("Reed test", "PASS")
    else:
        say("Reed test FAIL", "no change seen")
        print("Move the magnet near and away at least twice. No change at all: check the wires on pins 13 and 14.")


if __name__ == "__main__":
    main()
