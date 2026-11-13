"""4x4 keypad. Run: python -m tests.hw.test_keypad"""
import time

from tests.hw.common import banner, stop_if_service_running

WIRING = """
Keypad ribbon (8 wires, left to right with the keys facing you, from the seller's diagram):
R1 R2 R3 R4 C1 C2 C3 C4 -> GPIO 5, 6, 13, 19, 12, 16, 20, 21
                        -> pins 29, 31, 33, 35, 32, 36, 38, 40
"""


def main():
    stop_if_service_running()
    from coldchain.keypad import Keypad
    banner("Keypad test: press every key once within 40 s. Wrong characters = ribbon order.", WIRING)
    keypad = Keypad()
    seen = set()
    end = time.monotonic() + 40
    try:
        while time.monotonic() < end and len(seen) < 16:
            key = keypad.get_key()
            if key:
                seen.add(key)
                print("key %s   (%d/16)" % (key, len(seen)))
            time.sleep(0.02)
    finally:
        keypad.close()
    missing = [k for row in ("123A", "456B", "789C", "*0#D") for k in row if k not in seen]
    print("PASS" if not missing else "Keys never seen: " + " ".join(missing))


if __name__ == "__main__":
    main()
