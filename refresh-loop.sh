#!/bin/bash
# Re-enrich + rebuild data.js every 10 minutes while the scrape runs.
cd "$(dirname "$0")"
while true; do
  echo "=== refresh at $(date) ==="
  /opt/homebrew/anaconda3/bin/python enrich.py
  /opt/homebrew/anaconda3/bin/python build_json.py
  sleep 600
done
