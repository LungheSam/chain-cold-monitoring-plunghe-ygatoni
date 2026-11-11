"""Keypad PINs, stored as salted hashes in edge/pins.json (git-ignored, never committed).

File format:
    {"users": [{"name": "Samuel", "salt": "<hex>", "hash": "<hex>", "iterations": 20000}]}

Each PIN has its own random salt and is hashed with PBKDF2-HMAC-SHA256, so the file never holds a
PIN in clear text and two people with the same PIN get different hashes. Be honest about the limit:
a 4-digit PIN has only 10 000 values, so someone who copies pins.json could still try them all.
The real protection is the keypad lockout and keeping the Pi's SD card inside the locked box.

Manage PINs from the edge/ folder (the PIN is typed, never put on the command line):
    python -m coldchain.pins add Samuel
    python -m coldchain.pins list
    python -m coldchain.pins remove Samuel
"""
import argparse
import getpass
import hashlib
import hmac
import os
import secrets

from coldchain.store import load_json, save_json_atomic

# 20 000 iterations take about 20-40 ms per check on a Pi 4 (VERIFY with `python -m coldchain.pins
# time`). More would block the main loop longer for every user in the file.
ITERATIONS = 20000
MIN_DIGITS = 4
MAX_DIGITS = 8


def hash_pin(pin, salt, iterations=ITERATIONS):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations).hex()


def valid_pin_format(pin):
    return pin.isdigit() and MIN_DIGITS <= len(pin) <= MAX_DIGITS


class PinStore:
    def __init__(self, path):
        self.path = path
        data = load_json(path) or {}
        self.users = data.get("users", [])

    def check(self, pin):
        """Return the user's name if the PIN matches someone, else None."""
        if not valid_pin_format(pin):
            return None
        for user in self.users:
            salt = bytes.fromhex(user["salt"])
            digest = hash_pin(pin, salt, user.get("iterations", ITERATIONS))
            if hmac.compare_digest(digest, user["hash"]):   # constant-time comparison
                return user["name"]
        return None

    def add(self, name, pin):
        if not valid_pin_format(pin):
            raise ValueError("a PIN is %d to %d digits" % (MIN_DIGITS, MAX_DIGITS))
        if self.check(pin) not in (None, name):     # each PIN must identify one person
            raise ValueError("this PIN is already used by someone else; choose another")
        salt = secrets.token_bytes(16)
        self.users = [u for u in self.users if u["name"] != name]
        self.users.append({"name": name, "salt": salt.hex(), "hash": hash_pin(pin, salt), "iterations": ITERATIONS})
        self.save()

    def remove(self, name):
        before = len(self.users)
        self.users = [u for u in self.users if u["name"] != name]
        self.save()
        return len(self.users) < before

    def save(self):
        save_json_atomic(self.path, {"users": self.users})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage the keypad PINs")
    parser.add_argument("command", choices=["add", "list", "remove", "time"])
    parser.add_argument("name", nargs="?")
    parser.add_argument("--file", default=os.environ.get("PINS_FILE", "pins.json"))
    args = parser.parse_args(argv)
    store = PinStore(args.file)

    if args.command == "list":
        print("\n".join(u["name"] for u in store.users) or "(no PINs)")
    elif args.command == "time":
        import time
        start = time.perf_counter()
        hash_pin("0000", b"x" * 16)
        print("one PIN check takes %.0f ms" % ((time.perf_counter() - start) * 1000))
    elif not args.name:
        parser.error("give a name")
    elif args.command == "remove":
        print("removed" if store.remove(args.name) else "no such user")
    else:
        pin = getpass.getpass("PIN for %s (%d-%d digits): " % (args.name, MIN_DIGITS, MAX_DIGITS))
        if getpass.getpass("Again: ") != pin:
            print("The two PINs differ. Nothing saved.")
            return
        try:
            store.add(args.name, pin)
        except ValueError as e:
            print("Not saved:", e)
            return
        print("Saved PIN for %s in %s" % (args.name, args.file))


if __name__ == "__main__":
    main()
