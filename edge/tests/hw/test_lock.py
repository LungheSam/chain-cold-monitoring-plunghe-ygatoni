"""Lock test: the servo latch (LOCK_TYPE=servo) or the cabinet lock through the relay module.

Run:  python -m tests.hw.test_lock          one unlock and lock again (uses the settings in .env)
      python -m tests.hw.test_lock 45       servo only: move to 45 degrees and stay (to find the angles)
"""
import os
import sys
import time

from dotenv import load_dotenv

from tests.hw.common import banner, say, stop_if_service_running

SERVO_WIRING = """
Servo: brown/black -> GND rail, red -> 5 V rail, orange/yellow (signal) -> GPIO 25 (pin 22).
A micro servo (SG90/MG90S class) can use the Pi's 5 V with the official 3 A supply. A bigger servo
(MG996R class) needs its own 5-6 V supply: then join its GND to the Pi's GND.
A 100-470 uF capacitor across the servo's 5 V and GND (stripe to GND) helps against resets.
"""

RELAY_WIRING = """
Relay module: VCC -> 5 V, GND -> GND, IN -> GPIO 25 (pin 22)
Lock supply (+) -> relay COM; relay NO -> lock (+); lock (-) -> lock supply (-)
1N4007 across the lock, CATHODE (stripe) to the lock's (+).
The lock gets power ONLY from its own supply, never from the Pi.
"""


def servo_test(settings, angle=None):
    from gpiozero import AngularServo
    locked, unlocked = settings["SERVO_LOCKED_DEG"], settings["SERVO_UNLOCKED_DEG"]
    servo = AngularServo(25, initial_angle=None, min_angle=0, max_angle=180,
                         min_pulse_width=settings["SERVO_MIN_PULSE_MS"] / 1000,
                         max_pulse_width=settings["SERVO_MAX_PULSE_MS"] / 1000)
    try:
        if angle is not None:
            say("Servo test", "go to %d deg" % angle)
            servo.angle = angle
            time.sleep(1.0)
            print("Look at the latch. Put the good angles in .env as SERVO_LOCKED_DEG / SERVO_UNLOCKED_DEG.")
            return
        say("Servo: LOCKED", "%d deg" % locked)
        servo.angle = locked
        time.sleep(1.5)
        say("Servo: UNLOCKED", "%d deg, 5 s" % unlocked)
        servo.angle = unlocked
        time.sleep(5)
        say("Servo: LOCKED", "%d deg" % locked)
        servo.angle = locked
        time.sleep(1.0)
    finally:
        servo.detach()
    say("Lock test done", "did it turn?")
    print("If it jitters or turns the wrong way, change the angles in .env and run again.")


def relay_test(settings):
    from gpiozero import DigitalOutputDevice
    pulse = settings["LOCK_PULSE_S"]
    lock = DigitalOutputDevice(25, active_high=not settings["LOCK_ACTIVE_LOW"], initial_value=False)
    try:
        say("Lock test", "OPEN %.1f s" % pulse)
        lock.on()
        time.sleep(pulse)
    finally:
        lock.off()
    say("Lock test done", "did it click?")
    print("Also measure the current once (VERIFY against the lock's label).")


def main():
    stop_if_service_running()
    load_dotenv(".env")
    from coldchain.config import load_settings
    settings = load_settings()
    angle = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if settings["LOCK_TYPE"] == "servo" or angle is not None:
        banner("Servo lock test (LOCK_TYPE=%s)" % settings["LOCK_TYPE"], SERVO_WIRING)
        if angle is not None and not 0 <= angle <= 180:
            sys.exit("Angle must be 0 to 180.")
        servo_test(settings, angle)
        return
    banner("Relay lock test: one %.1f s pulse." % settings["LOCK_PULSE_S"], RELAY_WIRING)
    if input("Diode fitted and lock on its own supply? Type yes: ").strip().lower() != "yes":
        print("Stopped.")
        return
    relay_test(settings)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    main()
