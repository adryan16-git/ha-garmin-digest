"""Garmin data fetching, baseline computation, and Claude digest generation."""

import json
import logging
import re
from datetime import datetime, timedelta, timezone

import anthropic

from garmin_digest import ha_api
from garmin_digest.constants import CLAUDE_API_KEY, CLAUDE_MODEL, HISTORY_DAYS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------------

ACCUMULATING_SENSORS = {
    "sensor.garmin_connect_steps",
    "sensor.garmin_connect_active_calories",
    "sensor.garmin_connect_burned_calories",
    "sensor.garmin_connect_active_time",
    "sensor.garmin_connect_highly_active_time",
    "sensor.garmin_connect_sedentary_time",
    "sensor.garmin_connect_intensity_minutes",
    "sensor.garmin_connect_moderate_intensity_minutes",
    "sensor.garmin_connect_vigorous_intensity_minutes",
    "sensor.garmin_connect_distance",
    "sensor.garmin_connect_floors_ascended",
}

SENSORS = [
    # Sleep
    "sensor.garmin_connect_sleep_score",
    "sensor.garmin_connect_sleep_duration",
    "sensor.garmin_connect_total_sleep_duration",
    "sensor.garmin_connect_deep_sleep",
    "sensor.garmin_connect_light_sleep",
    "sensor.garmin_connect_rem_sleep",
    "sensor.garmin_connect_awake_duration",
    "sensor.garmin_connect_awake_time",
    "sensor.garmin_connect_bedtime",
    "sensor.garmin_connect_wake_time",
    "sensor.garmin_connect_unmeasurable_sleep",
    # Body Battery
    "sensor.garmin_connect_body_battery",
    "sensor.garmin_connect_body_battery_highest",
    "sensor.garmin_connect_body_battery_lowest",
    "sensor.garmin_connect_body_battery_charged",
    "sensor.garmin_connect_body_battery_drained",
    # Heart Rate
    "sensor.garmin_connect_resting_heart_rate",
    "sensor.garmin_connect_7_day_average_resting_heart_rate",
    "sensor.garmin_connect_min_heart_rate",
    "sensor.garmin_connect_max_heart_rate",
    "sensor.garmin_connect_min_average_heart_rate",
    "sensor.garmin_connect_max_average_heart_rate",
    # HRV
    "sensor.garmin_connect_hrv_status",
    "sensor.garmin_connect_hrv_baseline",
    "sensor.garmin_connect_hrv_last_night_average",
    "sensor.garmin_connect_hrv_weekly_average",
    # Stress
    "sensor.garmin_connect_average_stress_level",
    "sensor.garmin_connect_max_stress_level",
    "sensor.garmin_connect_stress_qualifier",
    "sensor.garmin_connect_rest_stress_duration",
    "sensor.garmin_connect_rest_stress_percentage",
    "sensor.garmin_connect_activity_stress_duration",
    "sensor.garmin_connect_activity_stress_percentage",
    "sensor.garmin_connect_high_stress_duration",
    "sensor.garmin_connect_high_stress_percentage",
    "sensor.garmin_connect_low_stress_duration",
    "sensor.garmin_connect_low_stress_percentage",
    "sensor.garmin_connect_medium_stress_duration",
    "sensor.garmin_connect_medium_stress_percentage",
    # Respiration
    "sensor.garmin_connect_highest_respiration",
    "sensor.garmin_connect_lowest_respiration",
    "sensor.garmin_connect_latest_respiration",
    # Activity
    "sensor.garmin_connect_steps",
    "sensor.garmin_connect_daily_step_goal",
    "sensor.garmin_connect_yesterday_steps",
    "sensor.garmin_connect_weekly_step_average",
    "sensor.garmin_connect_active_calories",
    "sensor.garmin_connect_burned_calories",
    "sensor.garmin_connect_bmr_calories",
    "sensor.garmin_connect_active_time",
    "sensor.garmin_connect_highly_active_time",
    "sensor.garmin_connect_sedentary_time",
    "sensor.garmin_connect_intensity_minutes",
    "sensor.garmin_connect_intensity_minutes_goal",
    "sensor.garmin_connect_moderate_intensity_minutes",
    "sensor.garmin_connect_vigorous_intensity_minutes",
    "sensor.garmin_connect_distance",
    "sensor.garmin_connect_yesterday_distance",
    "sensor.garmin_connect_floors_ascended",
    "sensor.garmin_connect_floors_ascended_goal",
    # Workouts
    "sensor.garmin_connect_last_activity",
    "sensor.garmin_connect_last_activities",
    # Fitness
    "sensor.garmin_connect_fitness_age",
    "sensor.garmin_connect_achievable_fitness_age",
    "sensor.garmin_connect_vo2_max",
    "sensor.garmin_connect_training_readiness",
    "sensor.garmin_connect_morning_training_readiness",
    "sensor.garmin_connect_training_status",
]

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _get_yesterday_finals() -> dict:
    """Fetch last recorded value before midnight for accumulating sensors."""
    now = datetime.now(timezone.utc)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    try:
        raw = ha_api.get_history(
            start.isoformat(),
            end_iso=end.isoformat(),
            entity_ids=list(ACCUMULATING_SENSORS),
        )
        entity_histories = json.loads(raw)
    except Exception as e:
        logger.warning("Could not fetch yesterday finals: %s", e)
        return {}

    result = {}
    for entity_history in entity_histories:
        if not entity_history:
            continue
        entity_id = entity_history[0].get("entity_id")
        if not entity_id:
            continue
        for entry in reversed(entity_history):
            state = entry.get("state", "")
            if state not in ("unknown", "unavailable", "None"):
                try:
                    float(state)
                    result[entity_id] = state
                    break
                except (ValueError, TypeError):
                    pass
    return result


def get_current_states() -> dict:
    """Fetch current HA states for all Garmin sensors, using yesterday finals for accumulators."""
    all_states = ha_api.get_states()
    yesterday_finals = _get_yesterday_finals()
    sensor_set = set(SENSORS)
    result = {}
    for s in all_states:
        eid = s["entity_id"]
        if eid not in sensor_set:
            continue
        state = s["state"]
        if eid in ACCUMULATING_SENSORS and eid in yesterday_finals:
            state = yesterday_finals[eid]
        result[eid] = {
            "state": state,
            "unit": s.get("attributes", {}).get("unit_of_measurement", ""),
            "attributes": s.get("attributes", {}),
        }
    return result


def get_history_baseline() -> dict:
    """Fetch N-day history and compute per-sensor stats for Claude baseline context."""
    start = (datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).isoformat()
    try:
        raw = ha_api.get_history(start, entity_ids=SENSORS)
        entity_histories = json.loads(raw)
    except Exception as e:
        logger.warning("Could not fetch history: %s", e)
        return {}

    baseline = {}
    for entity_history in entity_histories:
        if not entity_history:
            continue
        entity_id = entity_history[0].get("entity_id")
        if not entity_id:
            continue
        values = []
        for h in entity_history:
            try:
                values.append(float(h["state"]))
            except (ValueError, TypeError):
                pass
        if values:
            baseline[entity_id] = {
                "mean": round(sum(values) / len(values), 1),
                "min": round(min(values), 1),
                "max": round(max(values), 1),
            }
    return baseline

# ---------------------------------------------------------------------------
# Claude prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a personal health analyst writing a daily digest for Celeste.
Your job is to interpret her Garmin health data clearly and helpfully.

Guidelines:
- Write warmly but concisely — she reads this over morning coffee
- Focus on patterns, trends, and what's notable, not just restating numbers
- Highlight outliers relative to her 60-day baseline when meaningful
- Connect related metrics (e.g. poor sleep → lower body battery → higher stress)
- Forward-looking recommendations should be practical and pattern-informed, not prescriptive or medical
- Tone: informative, supportive, not alarmist
- Do NOT start with "Good morning" or similar pleasantries
- Do NOT use the word "delve"
"""


def _build_prompt(today: dict, baseline: dict, today_date: str) -> str:
    has_baseline = len(baseline) > 0
    baseline_note = "" if has_baseline else " (no baseline yet — integration recently set up)"

    lines = [
        f"Date: {today_date}",
        "",
        "DATA NOTES:",
        "- Sensors marked [today so far] show the accumulating current-day value as of 7:30am — use only for context, not as a daily summary.",
        "- Sensors marked [yesterday] show yesterday's complete total.",
        f"- 60-day baseline{baseline_note}",
        "",
        "GARMIN DATA:",
        "",
    ]

    for eid in SENSORS:
        data = today.get(eid, {})
        state = data.get("state", "unknown")
        if state in ("unknown", "unavailable", "None", "none"):
            continue
        name = eid.replace("sensor.garmin_connect_", "").replace("_", " ")
        unit = data.get("unit", "")
        tag = " [today so far]" if eid in ACCUMULATING_SENSORS else ""
        base = baseline.get(eid, {})
        base_str = f" [60-day avg: {base['mean']} {unit}, range: {base['min']}–{base['max']}]" if base else ""
        lines.append(f"  {name}{tag}: {state} {unit}{base_str}".strip())

    lines += [
        "",
        "---",
        "",
        "Write the daily digest using this exact structure:",
        "",
        "## How Last Night Went",
        "(2-3 sentences on sleep and recovery — quality, body battery arc, HRV, comparison to baseline)",
        "",
        "## The Day's Picture",
        "(2-3 sentences on activity, stress, energy — what the data shows about how yesterday unfolded)",
        "",
        "## What Stands Out",
        "(1-3 bullet points flagging notable outliers or patterns. Omit this section entirely if nothing is truly notable.)",
        "",
        "## For Today",
        "(2-3 bullet points: pattern-informed, practical suggestions based on recovery state and recent trends)",
        "",
        "## Yesterday at a Glance",
        "(Write a literal HTML <table> element — NOT markdown — with two columns: Metric and Value.",
        "Use <thead> with <th> headers and <tbody> with <tr><td> rows.",
        "Group rows with a full-width bold category label row for: Sleep, Recovery, Stress, Activity.",
        "Include all metrics that have real values. Omit unknown/unavailable ones.)",
    ]
    return "\n".join(lines)


def generate_narrative(today: dict, baseline: dict, today_date: str) -> str:
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(today, baseline, today_date)}],
    )
    return message.content[0].text

# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _narrative_to_html(text: str) -> str:
    """Convert Claude's output (markdown + inline HTML tables) to email-ready HTML."""
    lines = text.split("\n")
    html_lines = []
    in_ul = False
    in_table = False
    table_buf = []

    for line in lines:
        stripped = line.strip()

        # HTML table passthrough — buffer until </table>
        if stripped.startswith("<table") or in_table:
            in_table = True
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            table_buf.append(line)
            if "</table>" in stripped:
                in_table = False
                html_lines.append("\n".join(table_buf))
                table_buf = []
            continue

        if stripped.startswith("## "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped[2:])
            html_lines.append(f"<li>{content}</li>")
            continue

        if in_ul and not stripped:
            html_lines.append("</ul>")
            in_ul = False

        if stripped:
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
            html_lines.append(f"<p>{content}</p>")
        else:
            html_lines.append("")

    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def build_html_email(narrative: str, today_date: str) -> str:
    body = _narrative_to_html(narrative)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Garmin Daily Digest</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: #1a1a1a;
    background: #f5f5f5;
    margin: 0;
    padding: 0;
  }}
  .wrapper {{
    max-width: 600px;
    margin: 0 auto;
    background: #ffffff;
    padding: 24px 20px 32px;
  }}
  .header {{
    border-bottom: 3px solid #00b4d8;
    padding-bottom: 12px;
    margin-bottom: 24px;
  }}
  .header h1 {{ margin: 0; font-size: 20px; font-weight: 700; color: #0077b6; }}
  .header .date {{ font-size: 13px; color: #666; margin-top: 4px; }}
  h2 {{
    font-size: 16px;
    font-weight: 700;
    color: #0077b6;
    margin: 24px 0 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #e0e0e0;
  }}
  p {{ margin: 0 0 12px; }}
  ul {{ margin: 0 0 12px; padding-left: 20px; }}
  li {{ margin-bottom: 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 8px; }}
  th {{ background: #0077b6; color: white; text-align: left; padding: 8px 10px; font-weight: 600; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #e8e8e8; }}
  tr:nth-child(even) td {{ background: #f9f9f9; }}
  .footer {{
    margin-top: 32px;
    padding-top: 12px;
    border-top: 1px solid #e0e0e0;
    font-size: 12px;
    color: #999;
  }}
  @media (max-width: 480px) {{
    .wrapper {{ padding: 16px 14px 24px; }}
    h2 {{ font-size: 15px; }}
    body {{ font-size: 15px; }}
  }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Garmin Daily Digest</h1>
    <div class="date">{today_date}</div>
  </div>
  {body}
  <div class="footer">Generated from Garmin Connect via Home Assistant</div>
</div>
</body>
</html>"""
