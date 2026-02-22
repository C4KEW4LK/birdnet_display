# BirdNET Display

A Python-based web application designed to run on a Raspberry Pi alongside [BirdNET-Go](https://github.com/tphakala/birdnet-go). It displays the latest bird detections on a screen attached to the Pi, using BirdNET data and local image caches. It is designed around the standard 800x480px screens.

## Completed System

Here are some shots of the completed system in its 3d printed enclosure.

**Front:**
![System Front](images/system%20front.png)

**Side:**
![System Side](images/system%20side.png)

**Internals:**
![System Internals](images/system%20internals.png)

## Screenshots

**Online Mode:**

The online version shows the most recently detected unique birds, each with their confidence value as reported by [BirdNET-Go](https://github.com/tphakala/birdnet-go).

![Main Interface (Online)](images/main_interface_online.png)

**Offline Mode:**

The offline version displays a random assortment of birds native to the area, using cached images and information.

![Main Interface (Offline)](images/main_interface_offline.png)

**QR Code Overlay:**

The interface also displays the IP address of the Pi as a QR code for easy access from other devices.

![QR Code Overlay](images/qr%20code%20overlay.png)

**Settings Modal:**

The settings modal allows you to control the display and system.

![Settings Modal](images/settings%20modal.png)

## Features
- **Designed for Raspberry Pi** with a connected 800x480px touchscreen display.
- **BirdNET-Go Integration** - Shows the latest bird detections with confidence values.
- **Multiple Display Layouts** - Choose from 1 bird, 3 birds, 4 tall, or 4 grid layout modes.
- **Pinned Species Management** - Recently detected birds are automatically pinned for 24 hours with a "NEW" indicator. You can dismiss individual species or clear all pinned species.
- **WiFi Management** - Built-in WiFi configuration interface:
  - Scan for available networks
  - Connect to WiFi networks with password support
  - View current connection status and signal strength
  - Real-time WiFi signal indicator in the UI
- **Access Point (AP) Mode Support** - Automatically detects and displays connection instructions when the Pi is running as a WiFi hotspot.
- **On-Screen Keyboard** - JavaScript-based virtual keyboard for entering WiFi passwords and network names without needing a physical keyboard.
- **Offline Mode** - Caches images for all birds in the species list so the app can work completely offline and still display birds.
- **QR Code Display** - Shows the IP address as a QR code for easy access from other devices.
- **Kiosk Mode** - Full-screen dedicated display mode for Raspberry Pi.
- **System Controls** - Brightness adjustment, reboot, and power off controls from the web interface.
- **Status Indicators** - Real-time microphone and WiFi connection status with signal strength bars.

## Prerequisites

This project requires a locally installed and running instance of [BirdNET-Go](https://github.com/tphakala/birdnet-go). You can install it by running the following commands:

```bash
curl -fsSL https://github.com/tphakala/birdnet-go/raw/main/install.sh -o install.sh
bash ./install.sh
```

**For WiFi Management:**

The application requires NetworkManager and appropriate permissions to manage WiFi connections. On Raspberry Pi OS, you need to:

1. Add your user to the `netdev` group:
   ```bash
   sudo usermod -aG netdev $USER
   ```

2. Create PolicyKit rules to allow NetworkManager access without sudo:
   ```bash
   # Old-style rule (for compatibility)
   sudo mkdir -p /etc/polkit-1/localauthority/50-local.d/
   sudo tee /etc/polkit-1/localauthority/50-local.d/org.freedesktop.NetworkManager.pkla > /dev/null << 'EOF'
   [Allow netdev group to manage NetworkManager]
   Identity=unix-group:netdev
   Action=org.freedesktop.NetworkManager.*
   ResultAny=yes
   ResultInactive=yes
   ResultActive=yes
   EOF

   # New-style rule (for Bookworm/Trixie and newer)
   sudo mkdir -p /etc/polkit-1/rules.d/
   sudo tee /etc/polkit-1/rules.d/50-NetworkManager.rules > /dev/null << 'EOF'
   polkit.addRule(function(action, subject) {
       if (action.id.indexOf("org.freedesktop.NetworkManager.") == 0 && subject.isInGroup("netdev")) {
           return polkit.Result.YES;
       }
   });
   EOF
   ```

3. Restart polkit and the application:
   ```bash
   sudo systemctl restart polkit || sudo systemctl restart polkitd
   sudo systemctl restart bird-display.service
   ```
   Or if running manually, just restart the Python script.

   **If you still get permission errors, reboot the system:**
   ```bash
   sudo reboot
   ```

The automatic installer (`install.sh`) handles all of this for you.

## Setup and Installation

There are two ways to install the application:

### Automatic Installation (Recommended for Raspberry Pi)

The `install.sh` script automates the entire setup process on a Raspberry Pi.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/C4KEW4LK/birdnet_display.git
    cd birdnet_display
    ```

2.  **Run the installer:**
    ```bash
    chmod +x install.sh
    ./install.sh
    ```

    The script will:
    - Create an installation directory (`~/birdnet_display`).
    - Set up a Python virtual environment.
    - Install all required dependencies.
    - Build the initial image cache from your `species_list.csv`.
    - Optionally, configure the system to run in kiosk mode and set up the [BirdNET-Go](https://github.com/tphakala/birdnet-go) networking.

### Manual Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/C4KEW4LK/birdnet_display.git
    cd birdnet_display
    ```

2.  **Add your user to the netdev group (required for WiFi management):**
    ```bash
    sudo usermod -aG netdev $USER
    ```
    *Note: You'll need to log out and back in for this to take effect.*

3.  **Create a Python virtual environment:**

    *Note: On some systems like Raspbian, you may need to install the `venv` module first:*
    ```bash
    sudo apt-get install python3-venv
    ```

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Build the image cache:**
    ```bash
    python cache_builder.py
    ```

6.  **Run the application:**
    ```bash
    python birdnet_display.py
    ```

## Usage

-   **To run the application manually:**
    ```bash
    cd ~/birdnet_display
    ./run.sh
    ```
-   If you enabled the kiosk mode during installation, the application will start automatically on boot.
-   The Flask app serves the web interface on port 5000, which you can open in a web browser by navigating to `http://<your-pi-ip>:5000` to view the display.

## Configuration

### Species List

To customize the birds displayed in offline mode, edit the `species_list.csv` file. Add the common and scientific names of the birds you want to see.

```csv
Common Name,Scientific Name
Australian Magpie,Gymnorhina tibicen
Torresian Crow,Corvus orru
...
```

After modifying the list, rebuild the cache:

```bash
cd ~/birdnet_display
source venv/bin/activate
python cache_builder.py
```

### Application Settings

The main application settings are at the top of `birdnet_display.py`:

-   `BASE_URL`: The URL of your [BirdNET-Go](https://github.com/tphakala/birdnet-go) instance.
-   `SERVER_PORT`: The port for the display web server.

### WiFi Management

The BirdNET Display includes a built-in WiFi management interface accessible from the web UI:

1.  Click on the main display to reveal the settings icon
2.  Click the settings icon and select "Open WiFi Settings"
3.  From here you can:
    -   **Scan** for available WiFi networks
    -   **Connect** to a network by selecting it and entering the password using the on-screen keyboard
    -   View your **current connection** status
    -   See **signal strength** in real-time

The WiFi status icon in the top-right corner shows the current connection state with color-coded signal bars (green = excellent, orange = good, yellow = fair, red = weak, gray = disconnected).

### Pinned Species

The BirdNET Display automatically tracks new bird detections and marks them as "pinned" for 24 hours:

-   **NEW Indicator:** Recently detected birds show a "NEW" label in the corner of their card
-   **Pin Management:** Access pinned species from the settings menu
-   **Time Remaining:** See how long each species will remain pinned
-   **Dismissal:** Dismiss individual species or clear all pins at once
-   **Automatic Expiration:** Pins automatically expire after 24 hours

This feature helps you keep track of new or interesting birds that have been detected, even after they've been replaced by more recent detections.

### Access Point (AP) Setup for ESP32 Microphone

The `ap_setup.sh` script configures a **dedicated WiFi network** on a USB WiFi adapter specifically for connecting an ESP32 RTSP microphone to the Raspberry Pi. This setup uses a dual-WiFi configuration:

- **wlan0** (built-in WiFi): Connects to your home/main WiFi network for internet access
- **wlan1** (USB WiFi adapter): Creates a dedicated Access Point for the ESP32 microphone

**Why use this setup?**

- Provides a dedicated, reliable connection for the ESP32 microphone
- Assigns a fixed IP address to the microphone for consistent RTSP streaming
- Isolates microphone traffic from your main network
- The web interface automatically detects AP mode and displays connection instructions

**Hardware Requirements:**

- USB WiFi adapter (for wlan1)
- ESP32-based microphone with WiFi capability

**Configuration:**

1.  Open the `ap_setup.sh` script in a text editor.
2.  Edit the following variables at the top of the file:
    -   `WIFI_INTERFACE`: The name of your USB Wi-Fi adapter (typically `wlan1`)
    -   `HOTSPOT_SSID`: The WiFi network name for your microphone to connect to (default: "Birdhost")
    -   `HOTSPOT_PASSWORD`: The WiFi password (default: "birdnetpass")
    -   `DEVICE_MAC`: The MAC address of your ESP32 microphone
    -   `DEVICE_FIXED_IP`: The fixed IP address to assign to the microphone (default: "10.42.0.50")

**Usage:**

1. Connect your USB WiFi adapter to the Raspberry Pi

2. Run the script with `sudo`:
   ```bash
   sudo ./ap_setup.sh
   ```

3. The script will create and activate the "Birdhost" WiFi network on your USB adapter

4. When prompted, connect your ESP32 microphone to the "Birdhost" WiFi network

5. The script will scan the network and display all connected devices

6. Select your ESP32 from the list (identified by its IP and MAC address)

7. The script will assign a fixed IP address to your ESP32's MAC address for reliable RTSP streaming

The settings are persistent and will be restored on boot. You can connect to your Pi's web interface from your home WiFi network (wlan0) while the microphone streams over the dedicated network (wlan1).

### Web Interface Controls

The web interface provides several interactive controls accessible by clicking on the main display area to reveal a QR code and settings icon:

-   **Display Layout:** Change how bird detections are arranged on the screen (1 bird, 3 birds, 4 tall, 4 grid).
-   **WiFi Settings:**
    -   Scan for available WiFi networks
    -   Connect to networks with password entry via on-screen keyboard
    -   View currently connected network
    -   See real-time WiFi signal strength
-   **Pinned Species Management:**
    -   View all currently pinned birds with time remaining
    -   Dismiss individual species
    -   Dismiss all pinned species at once
-   **Screen Brightness:** Adjust the display brightness using a slider.
-   **System Controls:** Buttons for restarting or powering off the Raspberry Pi.
-   **Status Indicators:** Real-time microphone and WiFi connection status icons with signal bars in the top-right corner.

## Project Structure
```
.
├── 3d print files          # 3D printable enclosure files
├── birdnet_display.py      # Main Flask application
├── ap_setup.sh             # Script to configure a Wi-Fi hotspot
├── cache_builder.py        # Script to build the image cache
├── install.sh              # Installation script for Raspberry Pi
├── kiosk_launcher.sh       # Script to launch Chromium in kiosk mode
├── pinned_species.json     # Pinned species data (auto-generated)
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── run.sh                  # Script to run the application
├── species_list.csv        # List of bird species for the cache
└── static/
    ├── index.html          # Web interface with WiFi management and on-screen keyboard
    └── bird_images_cache/  # Cached bird images
```

## 3D Printed Files

This project includes 3D printable enclosure files (.3mf format) for housing the Raspberry Pi and display. These files are designed with the following considerations:

-   **No Supports Needed:** The models are oriented in the .3mf files to be printed without the need for support material.
-   **Mounting Options:** Designs include options for either directly threading machine screws into the plastic or using heat-set threaded inserts for a more robust assembly.

### Required Hardware

For the main housing, you will need:

- RPI 4B is confirmed other Pis might not fit (mainly thinking about the usb wifi adaptor)
- 5" DSI touch screen (eg. https://www.aliexpress.com/item/1005007091586628.html)
- USB-C connector holes perpendicular to connector (eg. D-type of https://www.aliexpress.com/item/1005005010606562.html)
- Heatsink I used:
	- GeeekPi Armor lite heatsink for Raspberry Pi 4 (https://52pi.com/products/52pi-cnc-extreme-heatsink-with-pwm-fan-for-raspberry-pi-4) though I had to drill out the threaded holes to allow mount the RPi to the screen

- 4x Threaded inserts M2.5xD3.5xL3
- 4x M2.5x8mm button head screws
- 4x M2.5x4mm button head screws
- 4x M2.5x8mm countersunk head screws
- 2x M2x6mm Button head screws

## Troubleshooting

-   **"Template file not found" error**: Make sure the `static` directory and `index.html` are in the same directory as `birdnet_display.py`.
-   **Images not appearing**:
    -   Ensure the `bird_images_cache` directory exists and has images.
    -   Run `python cache_builder.py` to build the cache.
-   **Application not starting on boot**:
    -   Check the systemd service status: `sudo systemctl status bird-display.service`
    -   Check the logs for errors: `journalctl -u bird-display.service`
-   **WiFi connection issues**:
    -   **Permission denied errors**:
        1. Verify you're in the `netdev` group: `groups $USER | grep netdev`
        2. Check PolicyKit rules exist:
           - Old-style: `ls -la /etc/polkit-1/localauthority/50-local.d/org.freedesktop.NetworkManager.pkla`
           - New-style: `ls -la /etc/polkit-1/rules.d/50-NetworkManager.rules`
        3. If missing, run `./fix_wifi_permissions.sh` from the project folder or follow the manual steps in the Prerequisites section above
        4. Restart polkit: `sudo systemctl restart polkit` or `sudo systemctl restart polkitd`
        5. Restart the application: `sudo systemctl restart bird-display.service`
        6. If still not working, **reboot the system**: `sudo reboot`
    -   If you get "wireless-security.key-mgmt: property is missing" error, the app will automatically delete conflicting connection profiles and retry.
    -   Make sure NetworkManager is installed and running: `sudo systemctl status NetworkManager`
    -   WiFi icon not updating: The app checks WiFi status every 5 seconds. If it's not updating, check that wlan0 is your WiFi interface with `ip link show`
-   **Keyboard not appearing**: If the on-screen keyboard doesn't show when tapping WiFi password fields, try refreshing the page or restarting the application.

## GitHub Repository
[https://github.com/C4KEW4LK/birdnet_display](https://github.com/C4KEW4LK/birdnet_display)

## Disclaimer

This software is provided "as is" and is confirmed to work with my specific setup. However, it may not be compatible with other configurations. Your mileage may vary.

## License
MIT License
