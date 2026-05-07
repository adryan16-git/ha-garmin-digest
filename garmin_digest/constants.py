"""Constants for Garmin Daily Digest."""

import os

# HA API — supervisor provides token via environment
SUPERVISOR_URL = "http://supervisor/core/api"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

# Add-on config (injected by run.sh from bashio::config)
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
GMAIL_SENDER_DISPLAY = os.environ.get("GMAIL_SENDER_DISPLAY", "Garmin Digest")
GMAIL_SENDER_ADDRESS = os.environ.get("GMAIL_SENDER_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
HISTORY_DAYS = int(os.environ.get("HISTORY_DAYS", "60"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()

# Trigger server
TRIGGER_PORT = 8765

# Archive path (inside the add-on container, mapped to /config)
ARCHIVE_DIR = "/config/.garmin_digest"

# Claude model
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# HA notification ID for failures
NOTIFICATION_ID = "garmin_digest_failure"
