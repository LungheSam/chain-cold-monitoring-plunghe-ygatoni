"""Small helpers shared by the hardware test scripts."""
import sys
import time


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


def watch(read_fn, label_fn, seconds):
    """Print the value whenever it changes, for `seconds` seconds."""
    nothing_yet = object()
    last = nothing_yet
    end = time.monotonic() + seconds
    changes = 0
    while time.monotonic() < end:
        value = read_fn()
        if value != last:
            print("%7.2f s  %s" % (seconds - (end - time.monotonic()), label_fn(value)))
            if last is not nothing_yet:
                changes += 1
            last = value
        time.sleep(0.02)
    return changes
