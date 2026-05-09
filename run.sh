#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Garmin Daily Digest add-on..."

export PYTHONPATH=/
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
export LOG_LEVEL="$(bashio::config 'log_level')"

exec python3 /garmin_digest/main.py
