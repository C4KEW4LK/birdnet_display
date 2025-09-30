#!/bin/bash

# --- Step 1: EDIT THESE VARIABLES ---
# The name of your USB Wi-Fi interface (usually wlan1)
WIFI_INTERFACE="wlan1"

# The name you want for your new Wi-Fi network (SSID)
HOTSPOT_SSID="Birdhost"

# The password for your new Wi-Fi network (8-63 characters)
HOTSPOT_PASSWORD="birdnetpass"

# The MAC address of the device you want to give a fixed IP
DEVICE_MAC="98:a3:16:61:24:a8"

# The fixed IP address you want to assign to that device
DEVICE_FIXED_IP="10.42.0.50"

# --- Step 2: Save the file and run it with 'sudo ./AP_setup.sh' ---
# The rest of the script is automated.

echo "--- Starting Robust Hotspot Setup ---"

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run this script with sudo."
  exit 1
fi

# Step 1: Clean up any previous hotspot configurations to ensure a clean start
echo "🧹 Cleaning up any old hotspot configurations..."
nmcli connection delete "$HOTSPOT_SSID" &> /dev/null

# Step 2: Create the new connection profile
echo "➕ Creating new hotspot connection profile named '$HOTSPOT_SSID'..."
nmcli connection add type wifi ifname "$WIFI_INTERFACE" con-name "$HOTSPOT_SSID" autoconnect yes ssid "$HOTSPOT_SSID"

# Step 3: Configure the new connection for AP mode and security
echo "🔧 Configuring connection for AP mode (hotspot)..."
nmcli connection modify "$HOTSPOT_SSID" 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared

# **FIXED:** Use the correct property 'wifi.powersave 1' to disable power saving
nmcli connection modify "$HOTSPOT_SSID" wifi.powersave 1

# Set a robust WPA2-Personal security profile for better compatibility
nmcli connection modify "$HOTSPOT_SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp wifi-sec.psk "$HOTSPOT_PASSWORD"

# Step 4: Configure NetworkManager to use dnsmasq for DHCP
NM_CONF="/etc/NetworkManager/NetworkManager.conf"
if ! grep -q "^dns=dnsmasq" "$NM_CONF"; then
    echo "🔧 Configuring NetworkManager to use dnsmasq..."
    # Insert 'dns=dnsmasq' after the [main] section
    sed -i '/^\[main\]/a dns=dnsmasq' "$NM_CONF"
else
    echo "✅ NetworkManager is already configured for dnsmasq."
fi

# Step 5: Create the configuration for the fixed IP
DNSMASQ_DIR="/etc/NetworkManager/dnsmasq-shared.d"
echo "📁 Creating configuration directory: $DNSMASQ_DIR"
mkdir -p "$DNSMASQ_DIR"
FIXED_IP_FILE="$DNSMASQ_DIR/fixed-ip.conf"
echo "📝 Creating fixed IP configuration file for MAC $DEVICE_MAC..."
echo "dhcp-host=$DEVICE_MAC,$DEVICE_FIXED_IP" > "$FIXED_IP_FILE"

# Step 6: Restart NetworkManager to apply all changes
echo "⚙️ Restarting NetworkManager to apply all changes..."
systemctl restart NetworkManager

# **ADDED:** Wait for 3 seconds to allow the Wi-Fi device to initialize
echo "⌛ Waiting for Wi-Fi adapter to be ready..."
sleep 3

# Step 7: Bring the connection up
echo "📶 Activating the hotspot..."
nmcli connection up "$HOTSPOT_SSID"

echo ""
echo "🎉 --- Setup Complete! ---"
echo "Your hotspot named '$HOTSPOT_SSID' should now be active and persistent."