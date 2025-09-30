#!/bin/bash
# Add a delay to allow the desktop and network to fully initialize
sleep 15
# Launch Chromium
/usr/bin/chromium-browser --noerrdialogs --disable-infobars --kiosk http://localhost:5000
