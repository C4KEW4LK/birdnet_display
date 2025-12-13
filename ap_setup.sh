#!/bin/sh

# --- Configuration (edit as needed) ---
WIFI_INTERFACE="wlan1"          # USB Wi-Fi interface (e.g., wlan1)
HOTSPOT_SSID="Birdhost"         # Hotspot SSID
HOTSPOT_PASSWORD="birdnetpass"  # Hotspot password (8-63 chars)
DEVICE_MAC="98:a3:16:61:24:a8"  # MAC address for fixed IP
DEVICE_FIXED_IP="10.42.0.50"    # Fixed IP to assign

DNSMASQ_DIR="/etc/NetworkManager/dnsmasq-shared.d"
FIXED_IP_FILE="$DNSMASQ_DIR/fixed-ip.conf"
NM_CONF="/etc/NetworkManager/NetworkManager.conf"
IP_CMD=$(command -v ip || echo /sbin/ip)

echo "--- Starting Hotspot Setup ---"

# Require root
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run this script with sudo."
  exit 1
fi

# Step 1: Clean any previous hotspot configs
echo "Cleaning old hotspot configuration..."
nmcli connection delete "$HOTSPOT_SSID" >/dev/null 2>&1 || true

# Step 2: Create the connection profile
echo "Creating hotspot connection profile '$HOTSPOT_SSID'..."
nmcli connection add type wifi ifname "$WIFI_INTERFACE" con-name "$HOTSPOT_SSID" autoconnect yes ssid "$HOTSPOT_SSID"

# Step 3: Configure AP mode and security
echo "Configuring hotspot settings..."
nmcli connection modify "$HOTSPOT_SSID" 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
nmcli connection modify "$HOTSPOT_SSID" wifi.powersave 1
nmcli connection modify "$HOTSPOT_SSID" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.proto rsn \
  wifi-sec.pairwise ccmp \
  wifi-sec.group ccmp \
  wifi-sec.psk "$HOTSPOT_PASSWORD"

# Step 4: Configure NetworkManager to use dnsmasq for DHCP
if ! grep -q "^dns=dnsmasq" "$NM_CONF"; then
  echo "Enabling dnsmasq in NetworkManager..."
  sed -i '/^\[main\]/a dns=dnsmasq' "$NM_CONF"
else
  echo "NetworkManager already configured for dnsmasq."
fi

# Step 5: Prepare dnsmasq drop-in directory
echo "Creating dnsmasq drop-in at $DNSMASQ_DIR ..."
mkdir -p "$DNSMASQ_DIR"

# Step 6: Restart NetworkManager to apply changes
echo "Restarting NetworkManager..."
systemctl restart NetworkManager

# Step 7: Wait for Wi-Fi device and bring up hotspot
echo "Waiting for Wi-Fi adapter..."
sleep 3
echo "Activating hotspot..."
nmcli connection up "$HOTSPOT_SSID"

echo ""
echo "--- Hotspot Active ---"
echo "Hotspot '$HOTSPOT_SSID' should now be active."

# Step 8: Optionally capture client MAC for fixed IP
echo ""
if [ -f "$FIXED_IP_FILE" ] && grep -q "^dhcp-host=" "$FIXED_IP_FILE"; then
  echo "Existing fixed IP mapping found:"
  cat "$FIXED_IP_FILE"
  printf "Keep existing mapping and skip scan? (Y/n): "
  read keep_map
  case "$keep_map" in
    n|N) echo "Proceeding to scan / set new mapping." ;;
    *) echo "Keeping existing mapping. Skipping MAC selection."; echo ""; echo "--- Setup Complete ---"; echo "Hotspot '$HOTSPOT_SSID' is active."; exit 0 ;;
  esac
fi

printf "Is the device connected and ready to scan for its MAC? (y/N): "
read do_scan

if [ "$do_scan" = "y" ] || [ "$do_scan" = "Y" ]; then

  run_scan() {
    if [ -z "$IP_CMD" ] || ! command -v "$IP_CMD" >/dev/null 2>&1; then
      echo "ERROR: 'ip' command not found. Enter MAC manually or install iproute2."
      RAW_NEIGH=""
      DEVICES=""
      return
    fi
    echo "Running: $IP_CMD neigh show dev $WIFI_INTERFACE"
    RAW_NEIGH=$($IP_CMD neigh show dev "$WIFI_INTERFACE" 2>&1)
    echo "Raw neighbor output:"
    printf '%s\n' "$RAW_NEIGH" | sed 's/^/  /'
    DEVICES=$(printf "%s\n" "$RAW_NEIGH" | awk '{
      mac="";
      for(i=1;i<=NF;i++){ if($i=="lladdr" && (i+1)<=NF) mac=$(i+1); }
      if(mac!=""){ print NR "|" $1 "|" mac; }
    }')
  }

  # Allow up to 3 scans, with manual entry or skip
  SELECTED_MAC=""
  for attempt in 1 2 3; do
    echo "Scan attempt $attempt..."
    run_scan
    if [ -n "$DEVICES" ]; then
      echo "Detected devices:"
      echo "$DEVICES" | while IFS='|' read -r idx ip mac; do
        echo "  $idx) IP: $ip  MAC: $mac"
      done
      printf "Select a device number, or press Enter to skip: "
      read choice
      if [ -n "$choice" ]; then
        SELECTED_MAC=$(echo "$DEVICES" | awk -F'|' -v n="$choice" '$1==n{print $3}')
      fi
      break
    else
      if [ -n "$RAW_NEIGH" ]; then
        echo "No parsable MAC addresses found above."
      else
        echo "No devices detected."
      fi
      if [ $attempt -lt 3 ]; then
        printf "Options: [r]escan, [m]anual MAC entry, [s]kip scanning: "
        read choice
        case "$choice" in
          m|M) printf "Enter MAC (e.g., aa:bb:cc:dd:ee:ff): "; read manual_mac; SELECTED_MAC="$manual_mac"; break ;;
          s|S) break ;;
          *) continue ;;
        esac
      fi
    fi
  done

  if [ -z "$SELECTED_MAC" ]; then
    echo "No MAC selected; skipping fixed IP assignment."
    echo ""
    echo "--- Setup Complete ---"
    echo "Hotspot '$HOTSPOT_SSID' is active."
    exit 0
  fi

  if [ -n "$SELECTED_MAC" ]; then
    DEVICE_MAC="$SELECTED_MAC"
    echo "Using MAC $DEVICE_MAC for fixed IP $DEVICE_FIXED_IP"
    echo "dhcp-host=$DEVICE_MAC,$DEVICE_FIXED_IP" > "$FIXED_IP_FILE"
    echo "Restarting NetworkManager to apply fixed IP mapping..."
    systemctl restart NetworkManager
    sleep 2
    nmcli connection up "$HOTSPOT_SSID"
    echo "Fixed IP mapping applied."
  else
    echo "No MAC selected; skipping fixed IP assignment."
  fi
else
  echo "Skipping MAC selection and fixed IP assignment."
fi

echo ""
echo "--- Setup Complete ---"
echo "Hotspot '$HOTSPOT_SSID' is active."
