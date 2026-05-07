"""Garmin Daily Digest — add-on entry point and HTTP trigger server."""

import json
import logging
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from garmin_digest import digest, email_sender, ha_api
from garmin_digest.constants import (
    ARCHIVE_DIR,
    LOG_LEVEL,
    NOTIFICATION_ID,
    TRIGGER_PORT,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("garmin_digest")


def run_digest() -> tuple[bool, str]:
    """Run the full digest pipeline. Returns (success, message)."""
    today_date = datetime.now().strftime("%B %-d, %Y")
    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"Garmin Daily Digest — {datetime.now().strftime('%A, %B %-d')}"
    errors = []

    logger.info("Fetching current Garmin states...")
    try:
        today = digest.get_current_states()
        logger.info("Got %d sensors", len(today))
    except Exception as e:
        msg = f"Failed to fetch HA states: {e}"
        logger.error(msg)
        _notify_failure(msg)
        return False, msg

    logger.info("Fetching %d-day history baseline...", digest.HISTORY_DAYS)
    try:
        baseline = digest.get_history_baseline()
        logger.info("Got baseline for %d sensors", len(baseline))
    except Exception as e:
        logger.warning("History fetch failed, proceeding without baseline: %s", e)
        baseline = {}

    logger.info("Generating narrative with Claude...")
    try:
        narrative = digest.generate_narrative(today, baseline, today_date)
        logger.info("Narrative generated")
    except Exception as e:
        msg = f"Claude API failed: {e}"
        logger.error(msg)
        _notify_failure(msg)
        return False, msg

    html = digest.build_html_email(narrative, today_date)
    snapshot = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sensors": today,
    }

    # Save locally to /config/.garmin_digest/
    try:
        archive = Path(ARCHIVE_DIR)
        archive.mkdir(parents=True, exist_ok=True)
        (archive / f"{date_str}.json").write_text(json.dumps(snapshot, indent=2, default=str))
        (archive / f"{date_str}.html").write_text(html)
        logger.info("Archived to %s", ARCHIVE_DIR)
    except Exception as e:
        errors.append(f"Archive write failed: {e}")
        logger.warning("Archive write failed: %s", e)

    # Send email
    try:
        email_sender.send(html, subject)
    except Exception as e:
        msg = f"Email send failed: {e}"
        logger.error(msg)
        errors.append(msg)
        _notify_failure(msg)
        return False, msg

    if errors:
        _notify_failure("Digest sent but with warnings:\n" + "\n".join(errors))
        return True, "Completed with warnings: " + "; ".join(errors)

    return True, "Garmin digest complete"


def _notify_failure(message: str):
    try:
        ha_api.send_persistent_notification(
            message=message,
            title="Garmin Digest Failed",
            notification_id=NOTIFICATION_ID,
        )
    except Exception as e:
        logger.warning("Could not send HA failure notification: %s", e)


class TriggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/trigger":
            self.send_response(404)
            self.end_headers()
            return

        logger.info("Trigger received — running digest")
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "accepted"}')

        # Run digest after responding so the HTTP call doesn't time out
        import threading
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        success, message = run_digest()
        logger.info("Digest result: %s — %s", "OK" if success else "FAILED", message)

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        logger.debug("HTTP %s", fmt % args)


def main():
    logger.info("Garmin Daily Digest add-on starting on port %d", TRIGGER_PORT)
    logger.info("POST /trigger to generate digest, GET /health to check status")

    server = HTTPServer(("0.0.0.0", TRIGGER_PORT), TriggerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")


if __name__ == "__main__":
    main()
