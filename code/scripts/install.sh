#!/bin/bash

# Installation script for BirdNET Display (Go version)

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} BirdNET Display - Installation Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Configuration
INSTALL_DIR="$HOME/birdnet_display"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REBOOT_REQUIRED=false

echo -e "${YELLOW}Installation directory: $INSTALL_DIR${NC}"
echo -e "${YELLOW}Source directory: $SOURCE_DIR${NC}"
echo ""

# Create installation directory
echo -e "${YELLOW}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}✓ Directory created${NC}"
echo ""

# Copy files
echo -e "${YELLOW}Copying application files...${NC}"
cp -r "$SOURCE_DIR"/* "$INSTALL_DIR/"
echo -e "${GREEN}✓ Files copied${NC}"
echo ""

# Make binaries and scripts executable
echo -e "${YELLOW}Making binaries and scripts executable...${NC}"
chmod +x "$INSTALL_DIR/bin/birdnet_display"
chmod +x "$INSTALL_DIR/bin/cache_builder"
chmod +x "$INSTALL_DIR/scripts/"*.sh
chmod +x "$INSTALL_DIR/build.sh"
echo -e "${GREEN}✓ Executables configured${NC}"
echo ""

# Build image cache
echo ""
read -p "Do you want to build the image cache now? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo -e "\n${YELLOW}Building image cache...${NC}"
    echo -e "${YELLOW}This may take several minutes depending on your internet connection.${NC}"

    # Ask if they want to fetch species from API
    read -p "Fetch species list from BirdNET-Go API? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter BirdNET-Go API URL (default: http://localhost:8080): " api_url
        api_url=${api_url:-http://localhost:8080}
        "$INSTALL_DIR/bin/cache_builder" -apiURL "$api_url" -update-species
    else
        "$INSTALL_DIR/bin/cache_builder"
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Image cache built successfully${NC}"
    else
        echo -e "${RED}✗ Failed to build cache${NC}"
        echo -e "${YELLOW}You can build it later with: $INSTALL_DIR/bin/cache_builder${NC}"
    fi
else
    echo -e "${YELLOW}Skipping cache build. Build it later with: $INSTALL_DIR/bin/cache_builder${NC}"
fi
echo ""

# Setup systemd service
echo ""
read -p "Set up systemd service (auto-start on boot)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter BirdNET-Go API URL (default: http://localhost:8080): " api_url
    api_url=${api_url:-http://localhost:8080}

    SERVICE_FILE="/etc/systemd/system/birdnet-display.service"
    CURRENT_USER=$(whoami)

    echo -e "\n${YELLOW}Creating systemd service...${NC}"
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=BirdNET Display Service
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/bin/birdnet_display -apiURL $api_url
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable birdnet-display.service
    sudo systemctl start birdnet-display.service

    echo -e "${GREEN}✓ Service installed and started${NC}"
    echo -e "Check status with: ${YELLOW}sudo systemctl status birdnet-display.service${NC}"
fi
echo ""

# Setup kiosk mode
echo ""
read -p "Set up kiosk mode (fullscreen display on boot)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Installing kiosk dependencies...${NC}"

    # Check if chromium is installed
    if ! command -v chromium-browser &> /dev/null && ! command -v chromium &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y chromium-browser unclutter xdotool
    fi

    # Create kiosk launcher script
    LAUNCHER_SCRIPT="$INSTALL_DIR/scripts/kiosk_launcher.sh"
    cat > "$LAUNCHER_SCRIPT" <<'EOF'
#!/bin/bash

# Wait for network and display
sleep 10

# Hide cursor
unclutter -idle 0.5 -root &

# Disable screen blanking
xset s off
xset -dpms
xset s noblank

# Start Chromium in kiosk mode
DISPLAY=:0 chromium-browser --noerrdialogs --disable-infobars --kiosk http://localhost:5000 &
EOF

    chmod +x "$LAUNCHER_SCRIPT"

    # Create autostart directory
    AUTOSTART_DIR="$HOME/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"

    # Create desktop entry
    cat > "$AUTOSTART_DIR/birdnet-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=BirdNET Display Kiosk
Exec=$LAUNCHER_SCRIPT
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

    echo -e "${GREEN}✓ Kiosk mode configured${NC}"
    REBOOT_REQUIRED=true
fi
echo ""

# Final instructions
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Installation directory: ${YELLOW}$INSTALL_DIR${NC}"
echo ""
echo -e "${GREEN}To run manually:${NC}"
echo -e "  cd $INSTALL_DIR"
echo -e "  ./bin/birdnet_display"
echo ""
echo -e "${GREEN}With custom BirdNET-Go URL:${NC}"
echo -e "  ./bin/birdnet_display -apiURL http://192.168.1.100:8080"
echo ""
echo -e "${GREEN}To build/update cache:${NC}"
echo -e "  ./bin/cache_builder"
echo -e "  ./bin/cache_builder -update-species"
echo ""
echo -e "${GREEN}Access the display:${NC}"
echo -e "  http://localhost:5000"
echo -e "  http://$(hostname -I | awk '{print $1}'):5000"
echo ""

# Reboot prompt
if [ "$REBOOT_REQUIRED" = true ]; then
    echo ""
    read -p "Kiosk mode configured. Reboot now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo reboot
    else
        echo -e "${YELLOW}Remember to reboot for kiosk mode to take effect${NC}"
    fi
fi
