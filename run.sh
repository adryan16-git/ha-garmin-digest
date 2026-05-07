#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Garmin Daily Digest add-on..."

export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
export RECIPIENT_EMAIL="$(bashio::config 'recipient_email')"
export GMAIL_SENDER_DISPLAY="$(bashio::config 'gmail_sender_display')"
export GMAIL_SENDER_ADDRESS="$(bashio::config 'gmail_sender_address')"
export GMAIL_APP_PASSWORD="$(bashio::config 'gmail_app_password')"
export CLAUDE_API_KEY="$(bashio::config 'claude_api_key')"
export HISTORY_DAYS="$(bashio::config 'history_days')"
export LOG_LEVEL="$(bashio::config 'log_level')"

exec python3 /garmin_digest/main.py
