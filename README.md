# ha-garmin-digest

Home Assistant add-on that generates and emails a daily health digest from Garmin Connect data.

## Setup

### 1. Install the add-on

Add this repository to your HA add-on store, then install **Garmin Daily Digest**.

### 2. Configure the add-on

In the add-on **Configuration** tab, fill in:

| Option | Description |
|--------|-------------|
| `recipient_email` | Celeste's email address |
| `gmail_sender_display` | Display name (e.g. `Garmin Digest`) |
| `gmail_sender_address` | Your Gmail address |
| `gmail_app_password` | Gmail App Password (not your main password) |
| `claude_api_key` | Anthropic API key |
| `history_days` | Days of history for baseline (default: 60) |

### 3. Add rest_command to configuration.yaml

```yaml
rest_command:
  garmin_digest_trigger:
    url: "http://localhost:8765/trigger"
    method: POST
    headers:
      Content-Type: "application/json"
```

Then restart HA (required for new shell_command/rest_command entries).

### 4. Add the daily automation

In **Settings → Automations**, create a new automation:

```yaml
alias: Garmin Daily Digest
description: Trigger daily health digest at 7:30am Central
trigger:
  - platform: time
    at: "13:30:00"  # 7:30am Central (UTC-6 CDT) — adjust for CST (14:30) in winter
action:
  - service: rest_command.garmin_digest_trigger
mode: single
```

### 5. Test

To trigger manually: `POST http://<ha-ip>:8765/trigger`  
To check status: `GET http://<ha-ip>:8765/health`

## Archive

Daily snapshots (JSON) and digests (HTML) are saved to `/config/.garmin_digest/` — accessible via Samba share.

## Notes

- The Garmin Connect integration must be set up separately in HA (Settings → Devices & Services → Garmin Connect)
- HRV detail and training readiness sensors populate after several days of wear
- The 60-day baseline improves over time — expect rough edges in the first few weeks
