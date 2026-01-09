#!/bin/bash
# Add a delay to allow the desktop and network to fully initialize
sleep 15

# Require an X session
if [ -z "${DISPLAY:-}" ]; then
  echo "No DISPLAY detected. Run this script from a graphical session (e.g., LXDE)."
  exit 1
fi

# Launch Chromium/Chrome (try common paths)
BROWSER_PATH=""
for candidate in "/usr/bin/chromium-browser" "/usr/bin/chromium" "$(command -v chromium-browser)" "$(command -v chromium)" "$(command -v google-chrome)" "$(command -v google-chrome-stable)"; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    BROWSER_PATH="$candidate"
    break
  fi
done

if [ -z "$BROWSER_PATH" ]; then
  echo "Could not find Chromium/Chrome executable. Please install chromium-browser or set BROWSER_PATH."
  exit 1
fi

# Disable screen blanking (suppress errors if DPMS extension not available)
xset s off 2>/dev/null
xset -dpms 2>/dev/null
xset s noblank 2>/dev/null

echo "Starting Chromium in kiosk mode..."
echo "Note: On-screen keyboard is provided by the web interface"

exec "$BROWSER_PATH" \
  --noerrdialogs \
  --disable-infobars \
  --kiosk \
  --password-store=basic \
  --disable-features=TranslateUI \
  --check-for-update-interval=31536000 \
  http://localhost:5000
