#!/bin/bash
# This script activates the virtual environment and starts the Flask server.
echo "Starting the Bird Detection Display..."
cd "/home/super/birdnet_display"
source venv/bin/activate
python3 birdnet_display.py
