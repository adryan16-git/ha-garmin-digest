"""Constants for Garmin Daily Digest."""

import json
import os

# HA API — supervisor provides token via environment
SUPERVISOR_URL = "http://supervisor/core/api"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

# Trigger server
TRIGGER_PORT = 8765

# Archive path (inside the add-on container, mapped to /config)
ARCHIVE_DIR = "/config/.garmin_digest"

# Claude model
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# HA notification ID for failures
NOTIFICATION_ID = "garmin_digest_failure"

_OPTIONS_FILE = "/data/options.json"


def load_options() -> dict:
    """Read add-on options fresh from disk — picks up UI changes without restart."""
    try:
        with open(_OPTIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def get(key: str, default=None):
    """Get a single config value fresh from options.json."""
    return load_options().get(key, default)
