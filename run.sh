#!/bin/bash

RIP_CONFIG_SOURCE="/app/defaults/streamrip_config.toml"
RIP_CONFIG_TARGET="/app/config/streamrip/config.toml"

echo "Movin Streamrip config"
mkdir -p "$(dirname "$TARGET")"
if [ ! -f "$TARGET" ]; then
  cp "$RIP_CONFIG_SOURCE" "$RIP_CONFIG_TARGET"
fi

while true; do
  python3 /app/auto_loader.py
  sleep 3600  # z. B. alle 60 Minuten
done

