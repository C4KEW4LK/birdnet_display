#!/usr/bin/env python3
"""
RTSP Connection Monitor
Checks if last_rtsp_connect matches last_stream_start, and reboots if they differ.
"""

import requests
import sys

# Configuration
STATUS_URL = "http://10.42.0.50/api/status"
REBOOT_URL = "http://10.42.0.50/api/action/reboot"
TIMEOUT = 10  # seconds


def check_status():
    """Check RTSP connection status and reboot if necessary."""
    try:
        print(f"Checking status at {STATUS_URL}")
        response = requests.get(STATUS_URL, timeout=TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        last_rtsp_connect = data.get('last_rtsp_connect')
        last_stream_start = data.get('last_stream_start')
        
        print(f"last_rtsp_connect: {last_rtsp_connect}")
        print(f"last_stream_start: {last_stream_start}")
        
        # Check if values match
        if last_rtsp_connect != last_stream_start:
            print("MISMATCH detected - triggering reboot")
            requests.post(REBOOT_URL, timeout=TIMEOUT)
            print("Reboot command sent")
        else:
            print("Status OK - times match")
        
        return 0
                
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(check_status())