"""Small helpers shared by the hardware test scripts.

Every test also shows its progress on the 16x2 LCD (if one answers on I2C), so you can follow a
test at the breadboard without looking at the laptop.
"""
import os
import sys
import time

_lcd = None
_lcd_failed = False


def lcd_show(line1, line2=""):
    """Show two lines (16 characters each) on the LCD. Does nothing if no LCD answers."""
    global _lcd, _lcd_failed
    if _lcd_failed:
        return
    try:
        if _lcd is None:
            from RPLCD.i2c import CharLCD
            address = int(os.environ.get("LCD_ADDRESS", "0x27"), 16)
            _lcd = CharLCD("PCF8574", address, port=1, cols=16, rows=2, charmap="A00")
        _lcd.cursor_pos = (0, 0)
        _lcd.write_string(str(line1)[:16].ljust(16))
        _lcd.cursor_pos = (1, 0)
        _lcd.write_string(str(line2)[:16].ljust(16))
    except Exception:          # no LCD, wrong address, loose wire: the test itself carries on
        _lcd_failed = True


def say(line1, line2=""):
    """Print a line in the terminal and show the same message on the LCD."""
    print(("%s  %s" % (line1, line2)).strip())
    lcd_show(line1, line2)


def banner(title, wiring):
    print("=" * 60)
    print(title)
    print("-" * 60)
    print(wiring.strip())
    print("=" * 60)


def stop_if_service_running():
    """The node service holds the GPIO pins; the tests cannot use them at the same time."""
    import subprocess
    try:
        out = subprocess.run(["systemctl", "is-active", "coldchain-node"], capture_output=True, text=True)
    except OSError:
        return
    if out.stdout.strip() == "active":
        sys.exit("Stop the node first:  sudo systemctl stop coldchain-node")


def watch(read_fn, label_fn, seconds, lcd_title=""):
    """Print the value whenever it changes, for `seconds` seconds (and show it on the LCD)."""
    nothing_yet = object()
    last = nothing_yet
    end = time.monotonic() + seconds
    changes = 0
    while time.monotonic() < end:
        value = read_fn()
        if value != last:
            print("%7.2f s  %s" % (seconds - (end - time.monotonic()), label_fn(value)))
            lcd_show(lcd_title, label_fn(value))
            if last is not nothing_yet:
                changes += 1
            last = value
        time.sleep(0.02)
    return changes
