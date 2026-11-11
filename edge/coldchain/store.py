"""Small JSON file storage that survives power cuts.

save_json_atomic() writes to a temporary file, flushes it to the SD card, then renames it over the
old file. A rename is atomic, so after a crash we have either the old file or the new one, never
half a file.
"""
import json
import logging
import os

log = logging.getLogger(__name__)


def save_json_atomic(path, data):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def load_json(path):
    """Return the saved data, or None if there is no file. A corrupt file is kept aside as .corrupt."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        log.error("State file %s is unreadable (%s); starting fresh", path, e)
        os.replace(path, path + ".corrupt")
        return None
