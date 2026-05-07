"""Home Assistant REST API wrapper using urllib (no external dependencies)."""

import json
import logging
import time
import urllib.request
import urllib.error

from garmin_digest.constants import SUPERVISOR_URL, SUPERVISOR_TOKEN

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2


def _raw_request(method, path, data=None):
    url = f"{SUPERVISOR_URL}{path}"
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode()
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 404:
                raise
            logger.warning("HA API %s %s returned %s (attempt %d/%d)", method, path, e.code, attempt + 1, MAX_RETRIES)
        except (urllib.error.URLError, OSError) as e:
            last_error = e
            logger.warning("HA API %s %s failed (attempt %d/%d): %s", method, path, attempt + 1, MAX_RETRIES, e)

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFF * (2 ** attempt))

    raise last_error


def _request(method, path, data=None):
    resp = _raw_request(method, path, data)
    return json.loads(resp) if resp else None


def get_states():
    return _request("GET", "/states")


def get_history(start_iso, end_iso=None, entity_ids=None):
    path = f"/history/period/{start_iso}"
    params = ["minimal_response=true", "no_attributes=true"]
    if end_iso:
        params.append(f"end_time={end_iso}")
    if entity_ids:
        params.append(f"filter_entity_id={','.join(entity_ids)}")
    if params:
        path += "?" + "&".join(params)
    return _raw_request("GET", path)


def send_persistent_notification(message, title=None, notification_id=None):
    data = {"message": message}
    if title:
        data["title"] = title
    if notification_id:
        data["notification_id"] = notification_id
    return _request("POST", "/services/persistent_notification/create", data)
