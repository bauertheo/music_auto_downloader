#!/bin/bash

RIP_CONFIG_SOURCE="/app/defaults/streamrip_config.toml"
RIP_CONFIG_TARGET="/app/config/streamrip/config.toml"

echo "Moving Streamrip config"
mkdir -p "$(dirname "$RIP_CONFIG_TARGET")"

if [ ! -f "$RIP_CONFIG_TARGET" ]; then
    cp "$RIP_CONFIG_SOURCE" "$RIP_CONFIG_TARGET"
fi

while true; do
    # Use Python from venv for the script
    /app/venv/bin/python3 /app/auto_loader.py
    sleep 3600  # e.g. every 60 minutes
done

