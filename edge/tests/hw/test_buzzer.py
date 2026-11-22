"""Passive buzzer through an NPN transistor. Run: python -m tests.hw.test_buzzer"""
import time

from tests.hw.common import banner, lcd_show, say, stop_if_service_running

WIRING = """
GPIO 18 (pin 12) -> 1 kOhm -> NPN base (2N2222 or BC547: pin order differs, VERIFY on the datasheet)
NPN emitter -> GND
NPN collector -> buzzer (-) ; buzzer (+) -> 5 V (pin 2)
1N4148 across the buzzer (cathode to 5 V) if it is a magnetic type.
"""


def main():
    stop_if_service_running()
    from gpiozero import PWMOutputDevice
    banner("Buzzer test: 3 beeps at 2 kHz, then a sweep 1 -> 3 kHz.", WIRING)
    buzzer = PWMOutputDevice(18, frequency=2000, initial_value=0)
    try:
        for n in range(3):
            lcd_show("Buzzer test", "beep %d of 3" % (n + 1))
            buzzer.value = 0.5
            time.sleep(0.3)
            buzzer.value = 0
            time.sleep(0.3)
        for hz in range(1000, 3001, 250):
            buzzer.frequency = hz
            lcd_show("Buzzer sweep", "%d Hz" % hz)
            buzzer.value = 0.5
            time.sleep(0.15)
    finally:
        buzzer.off()
    say("Buzzer test done", "heard 3 beeps?")
    print("Did you hear 3 beeps and a rising tone? If silent: check the transistor pins and 5 V.")


if __name__ == "__main__":
    main()
