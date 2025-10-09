# BirdNET Display

A high-performance display interface for [BirdNET-Go](https://github.com/tphakala/birdnet-go) written in Go. Designed to run on a Raspberry Pi with an attached 800x480px touchscreen, showing the latest bird detections with images, confidence scores, and offline caching capabilities.

![Main Interface](images/main_interface_online.png)

## Features

- 🐦 **Live Bird Detections** - Real-time display of detected birds from BirdNET-Go
- 🖼️ **Image Caching** - Offline mode with locally cached bird images from Wikimedia
- 📌 **New Species Badges** - Automatically pins newly detected species for 24 hours
- 🎨 **Multiple Layouts** - 1, 3, or 4 bird display configurations
- 📱 **QR Code** - Quick access to BirdNET-Go interface
- ⚙️ **System Controls** - Brightness adjustment, reboot, and power off
- 🔌 **Offline Support** - Works without internet using cached images (once setup)

## Screenshots

### Online Mode
![Online Mode](images/main_interface_online.png)

### Offline Mode
![Offline Mode](images/main_interface_offline.png)

### Settings
![Settings Modal](images/settings%20modal.png)

## Hardware

### Confirmed Working Setup
- Raspberry Pi 4B (other Pi models may work)
- 5" DSI touchscreen (800x480px) - [Example](https://www.aliexpress.com/item/1005007091586628.html)
- GeeekPi Armor lite heatsink ([Link](https://52pi.com/products/52pi-cnc-extreme-heatsink-with-pwm-fan-for-raspberry-pi-4))

### Optional
- USB WiFi adapter for access point mode
- 3D printed enclosure (files included in `3d print files/`)

## Quick Start

### Prerequisites

- Raspberry Pi running Raspberry Pi OS 64-bit
- [BirdNET-Go](https://github.com/tphakala/birdnet-go) installed and running

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/C4KEW4LK/birdnet_display.git
   cd birdnet_display/code
   ```

2. **Make binaries executable:**
   ```bash
   chmod +x bin/birdnet_display bin/cache_builder scripts/*.sh
   ```

3. **Run automatic installation (recommended):**
   ```bash
   ./scripts/install.sh
   ```

   This will:
   - Set up the application directory
   - Build the image cache
   - Optionally configure systemd service (auto-start on boot)
   - Optionally set up kiosk mode

4. **Or run manually:**
   ```bash
   # Build image cache (optional)
   ./bin/cache_builder

   # Start the server
   ./bin/birdnet_display
   ```

5. **Access the display:**
   ```
   http://raspberrypi.local:5000
   ```
   Or from any device on the network using the Pi's IP address.

## Usage

### Command-Line Options

**Main Server:**
```bash
./bin/birdnet_display -h

# Start with defaults (localhost:8080 BirdNET-Go API, port 5000)
./bin/birdnet_display

# Custom BirdNET-Go URL
./bin/birdnet_display -apiURL http://192.168.1.100:8080

# Custom port
./bin/birdnet_display -port 8000
```

**Cache Builder:**
```bash
./bin/cache_builder -h

# Build cache from species_list.csv
./bin/cache_builder

# Update species list from BirdNET-Go API
./bin/cache_builder -update-species

# Use custom BirdNET-Go URL
./bin/cache_builder -apiURL http://192.168.1.100:8080 -update-species
```

### Configuration

#### Species List

Edit `code/species_list.csv` to customize which birds appear in offline mode:

```csv
Common Name,Scientific Name
Australian Magpie,Gymnorhina tibicen
Torresian Crow,Corvus orru
```

Then rebuild the cache:
```bash
./bin/cache_builder
```

Or fetch species from BirdNET-Go API based on your location:
```bash
./bin/cache_builder -update-species
```

#### Display Settings

All settings are accessible through the web interface:
- Display layout (1, 3, or 4 birds)
- Screen brightness
- System controls (reboot/power off)
- Pinned species management

## Project Structure

```
.
├── code/                      # Application code
│   ├── bin/                   # Pre-compiled binaries (ARM64)
│   │   ├── birdnet_display   # Main server
│   │   └── cache_builder     # Cache builder
│   ├── cmd/                   # Additional commands
│   ├── scripts/               # Installation & setup scripts
│   ├── templates/             # HTML templates
│   ├── static/                # Static files & image cache
│   ├── docs/                  # Documentation
│   ├── main.go               # Server source code
│   ├── go.mod                # Go dependencies
│   └── species_list.csv      # Bird species list
├── 3d print files/           # Enclosure STL/3MF files
├── images/                   # Screenshots & documentation images
└── README.md                 # This file
```

## Advanced Setup

### Systemd Service (Auto-start on boot)

The install script can do this automatically, or manually:

```bash
sudo nano /etc/systemd/system/birdnet-display.service
```

```ini
[Unit]
Description=BirdNET Display Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/birdnet_display/code
ExecStart=/home/pi/birdnet_display/code/bin/birdnet_display -apiURL http://YOUR_BIRDNET_IP:8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable birdnet-display.service
sudo systemctl start birdnet-display.service
```

### Kiosk Mode

For a dedicated display that auto-starts in fullscreen:

The install script can configure this, or use the provided `scripts/kiosk_launcher.sh`.

### Access Point Mode

To create a WiFi hotspot (useful for field deployments):

```bash
./scripts/ap_setup.sh
```

Edit the script to configure SSID, password, and fixed IP assignments.

## Building from Source

The repository includes pre-compiled ARM64 binaries. To rebuild:

### On Raspberry Pi
```bash
cd code
./build.sh
```

### Cross-compile from another machine
```bash
cd code
GOOS=linux GOARCH=arm64 go build -o bin/birdnet_display main.go
GOOS=linux GOARCH=arm64 go build -o bin/cache_builder ./cmd/cache_builder/main.go
```

## 3D Printed Enclosure

The `3d print files/` directory contains STL and 3MF files for:
- Main housing for Raspberry Pi and screen
- ESP32 microphone housing (optional)

Files are oriented for printing without supports. Choose between:
- Threaded inserts (recommended)
- Direct machine screws

See hardware list in each subdirectory.

## Troubleshooting

### Cannot connect to BirdNET-Go
```bash
# Use -apiURL flag with correct IP
./bin/birdnet_display -apiURL http://192.168.1.100:8080

# Test API connectivity
curl http://192.168.1.100:8080/api/v2/detections/recent?limit=1
```

### Images not loading
```bash
# Build the cache
./bin/cache_builder

# Update species list and build cache
./bin/cache_builder -update-species
```

### Service won't start
```bash
# Check logs
journalctl -u birdnet-display.service -f

# Check status
sudo systemctl status birdnet-display.service
```

### Binary architecture mismatch
```bash
# Check binary
file bin/birdnet_display
# Should show: ARM aarch64

# Check system
uname -m
# Should show: aarch64
```

## Documentation

- [Command-Line Usage](code/docs/USAGE.md) - Detailed CLI documentation

## License

MIT License

## Acknowledgments

- [BirdNET-Go](https://github.com/tphakala/birdnet-go) - The backend bird detection system
- [Wikimedia Commons](https://commons.wikimedia.org/) - Bird images
- Original Python version contributors

## Links

- **GitHub Repository:** [https://github.com/C4KEW4LK/birdnet_display](https://github.com/C4KEW4LK/birdnet_display)
- **BirdNET-Go:** [https://github.com/tphakala/birdnet-go](https://github.com/tphakala/birdnet-go)

---

**Note:** This is a Go rewrite of the original Python version. All features have been preserved with improved performance and easier deployment.
