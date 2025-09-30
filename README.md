# BirdNET Display

A Python-based web application designed to run on a Raspberry Pi alongside BirdNET-Pi. It displays the latest bird detections on a screen attached to the Pi, using BirdNET data and local image caches. It is designed around the standard 800x480px screens.

## Screenshots

**Online Mode:**

The online version shows the most recently detected unique birds, each with their confidence value as reported by BirdNET-Pi.

![Main Interface (Online)](screenshots/main_interface_online.png)

**Offline Mode:**

The offline version displays a random assortment of birds native to the area, using cached images and information.

![Main Interface (Offline)](screenshots/main_interface_offline.png)

**QR Code Overlay:**

The interface also displays the IP address of the Pi as a QR code for easy access from other devices.

![QR Code Overlay](screenshots/qr%20code%20overlay.png)

## Features
- Designed for Raspberry Pi with a connected display.
- Integrates with BirdNET-Pi to show the latest bird detections.
- Displays the IP address (including a QR code) of the Raspberry Pi on the webpage.
- Caches images for all birds in the species list so the app can work completely offline and still display birds.
- Simple and responsive web interface.
- Kiosk mode for dedicated display on a Raspberry Pi.
- System controls from the web interface (brightness, reboot, power off).
- Microphone status indicator that pings an ESP32 RTSP stream to verify the audio connection.

## Setup and Installation

There are two ways to install the application:

### Automatic Installation (Recommended for Raspberry Pi)

The `install.sh` script automates the entire setup process on a Raspberry Pi.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/C4KEW4LK/birdnet-display.git
    cd birdnet-display
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
    - Optionally, configure the system to run in kiosk mode and set up the BirdNET-Go networking.

### Manual Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/C4KEW4LK/birdnet-display.git
    cd birdnet-display
    ```

2.  **Create a Python virtual environment:**

    *Note: On some systems like Raspbian, you may need to install the `venv` module first:*
    ```bash
    sudo apt-get install python3-venv
    ```

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Build the image cache:**
    ```bash
    python cache_builder.py
    ```

5.  **Run the application:**
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

-   `BASE_URL`: The URL of your BirdNET-Pi instance.
-   `SERVER_PORT`: The port for the display web server.

### Access Point (AP) Setup

For field deployments where you may not have access to a local Wi-Fi network, the `ap_setup.sh` script can configure your Raspberry Pi to act as a Wi-Fi Access Point. This allows you to connect directly to the Pi from your phone or laptop.

**Features:**

- Creates a secure Wi-Fi hotspot with a custom name (SSID) and password.
- Assigns a fixed IP address to a specified device, ensuring a consistent address for your microphone or other peripherals.

**Configuration:**

1.  Open the `ap_setup.sh` script in a text editor.
2.  Edit the following variables at the top of the file:
    -   `WIFI_INTERFACE`: The name of your USB Wi-Fi interface (e.g., `wlan1`).
    -   `HOTSPOT_SSID`: The desired name for your Wi-Fi network.
    -   `HOTSPOT_PASSWORD`: The password for your Wi-Fi network.
    -   `DEVICE_MAC`: The MAC address of the device to receive a fixed IP.
    -   `DEVICE_FIXED_IP`: The fixed IP address to assign.

**Usage:**

Run the script with `sudo`:

```bash
sudo ./ap_setup.sh
```

The script will configure and activate the hotspot. The settings are persistent and will be restored on boot.

### Web Interface Controls

The web interface provides several interactive controls accessible by clicking on the main display area to reveal a QR code and settings icon:

-   **Display Layout:** Change how bird detections are arranged on the screen (e.g., 1 bird, 3 birds, 4 tall, 4 grid).
-   **Screen Brightness:** Adjust the display brightness using a slider.
-   **System Controls:** Buttons for restarting or powering off the Raspberry Pi.

## Project Structure
```
.
├── birdnet_display.py      # Main Flask application
├── ap_setup.sh             # Script to configure a Wi-Fi hotspot
├── cache_builder.py        # Script to build the image cache
├── install.sh              # Installation script for Raspberry Pi
├── kiosk_launcher.sh       # Script to launch Chromium in kiosk mode
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── run.sh                  # Script to run the application
├── species_list.csv        # List of bird species for the cache
└── static/
    ├── index.html          # Web interface
    └── bird_images_cache/  # Cached bird images
```

## Troubleshooting

-   **"Template file not found" error**: Make sure the `static` directory and `index.html` are in the same directory as `birdnet_display.py`.
-   **Images not appearing**:
    -   Ensure the `bird_images_cache` directory exists and has images.
    -   Run `python cache_builder.py` to build the cache.
-   **Application not starting on boot**:
    -   Check the systemd service status: `sudo systemctl status bird-display.service`
    -   Check the logs for errors: `journalctl -u bird-display.service`

## GitHub Repository
[https://github.com/C4KEW4LK/birdnet_display](https://github.com/C4KEW4LK/birdnet_display)

## License
MIT License