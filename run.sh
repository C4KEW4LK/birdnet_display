#!/bin/bash
# Activate the virtual environment next to this script and start the app.
cd "$(dirname "$0")"
source venv/bin/activate
exec python3 birdnet_display.py "$@"
