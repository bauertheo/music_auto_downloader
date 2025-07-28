#!/bin/bash

while true; do
  echo "==== $(date) - Running Deezer Watch ===="
  python3 /app/auto_loader.py
  sleep 3600  # z. B. alle 60 Minuten
done

