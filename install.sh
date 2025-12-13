#!/bin/bash

# --- Configuration ---
INSTALL_DIR_NAME="birdnet_display"
INSTALL_DIR="$HOME/$INSTALL_DIR_NAME" # Use the current user's home directory for the installation
SOURCE_DIR="$(pwd)"
REBOOT_REQUIRED=false

# Color Codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}--- Starting Bird Detection Display Standalone Setup ---${NC}"
echo -e "${YELLOW}Installation Target: $INSTALL_DIR${NC}"
echo -e "${YELLOW}Source Directory: $SOURCE_DIR${NC}"

# --- Step 0: Ensure BirdNET-Go is Installed ---
echo -e "
${YELLOW}Step 0: Checking BirdNET-Go service status...${NC}"
if sudo systemctl status birdnet-go >/dev/null 2>&1; then
    echo -e "${GREEN}[OK] BirdNET-Go service detected.${NC}"
else
    echo -e "${YELLOW}BirdNET-Go not found. Installing...${NC}"
    curl -fsSL https://github.com/tphakala/birdnet-go/raw/main/install.sh -o /tmp/birdnet-go-install.sh
    bash /tmp/birdnet-go-install.sh
fi

# --- Create Install Directory ---
echo -e "\n${YELLOW}Step 1: Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
echo -e "${GREEN}✅ Directory created at $INSTALL_DIR${NC}"


# --- Step 2: Check for Python and Pip ---
echo -e "\n${YELLOW}Step 2: Checking for Python 3 and Pip...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 is not installed. Please install Python 3 and try again.${NC}"
    exit 1
fi
if ! python3 -m pip --version &> /dev/null; then
    echo -e "${RED}ERROR: Pip for Python 3 is not installed.${NC}"
    echo -e "${YELLOW}Please install it (e.g., with 'sudo apt-get install python3-pip') and try again.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 3 and Pip found.${NC}"

# --- Step 3: Copy Project Files ---
echo -e "\n${YELLOW}Step 3: Copying project files to $INSTALL_DIR...${NC}"
cp "$SOURCE_DIR/birdnet_display.py" "$INSTALL_DIR/"
cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SOURCE_DIR/run.sh" "$INSTALL_DIR/"
cp "$SOURCE_DIR/kiosk_launcher.sh" "$INSTALL_DIR/"
cp "$SOURCE_DIR/cache_builder.py" "$INSTALL_DIR/"
cp "$SOURCE_DIR/species_list.csv" "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/static"
cp -r "$SOURCE_DIR/static/index.html" "$INSTALL_DIR/static/"
cp -r "$SOURCE_DIR/static/bird_images_cache" "$INSTALL_DIR/static/"
echo -e "${GREEN}✅ Project files copied.${NC}"


# --- Step 4: Set up Python Virtual Environment ---
echo -e "\n${YELLOW}Step 4: Creating Python virtual environment in $INSTALL_DIR...${NC}"
python3 -m venv "$INSTALL_DIR/venv"
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Failed to create virtual environment, python3-venv might be missing.${NC}"
    echo -e "${YELLOW}Attempting to install python3-venv via apt-get...${NC}"
    if ! command -v apt-get &> /dev/null; then
        echo -e "${RED}ERROR: apt-get not found. Please install python3-venv manually and rerun this script.${NC}"
        exit 1
    fi
    sudo apt-get update && sudo apt-get install -y python3-venv
    
    echo -e "${YELLOW}Retrying virtual environment creation...${NC}"
    python3 -m venv "$INSTALL_DIR/venv"
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to create virtual environment after installing python3-venv. Please check for errors.${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✅ Virtual environment created.${NC}"

# --- Step 5: Install Dependencies ---
echo -e "\n${YELLOW}Step 5: Installing required Python packages...${NC}"
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to install Python packages.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ All required packages installed successfully.${NC}"

# --- Step 6: Create Sample species_list.csv ---
echo -e "\n${YELLOW}Step 6: Checking for species_list.csv...${NC}"
if [ ! -f "$INSTALL_DIR/species_list.csv" ]; then
    echo -e "${YELLOW}File not found. Creating a sample species_list.csv...${NC}"
    cat > "$INSTALL_DIR/species_list.csv" << EOF
common_name,scientific_name
Australian Magpie,Gymnorhina tibicen
Laughing Kookaburra,Dacelo novaeguineae
Sulphur-crested Cockatoo,Cacatua galerita
EOF
    echo -e "${GREEN}✅ Sample file created. Please edit it with your local bird species for a better experience.${NC}"
else
    echo -e "${GREEN}✅ Existing species_list.csv found.${NC}"
fi

# --- Step 7: Update Species List from API (Optional) ---
echo ""
read -p "Do you want to fetch the species list from BirdNET-Go API? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Fetching species list from BirdNET-Go API...${NC}"
    "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/cache_builder.py" --update-species
    if [ $? -ne 0 ]; then
        echo -e "${RED}WARNING: Failed to fetch species list from API. Continuing with existing species_list.csv${NC}"
    fi
fi

# --- Step 8: Build and Resize Image Cache (Optional) ---
echo -e "\n${YELLOW}Step 8: Build the offline image cache?${NC}"
read -p "Do you want to build and resize the offline image cache now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Building and resizing the offline image cache...${NC}"
    echo -e "${YELLOW}This may take a few minutes depending on your internet connection and species list size.${NC}"
    "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/cache_builder.py"
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to build and resize the image cache. Please check for errors above.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[OK] Offline image cache is ready.${NC}"
else
    echo -e "${YELLOW}Skipping cache build. You can run it later with:${NC}"
    echo -e "  ${YELLOW}$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/cache_builder.py${NC}"
fi
# --- Step 9: Create Run Script ---
echo -e "\n${YELLOW}Step 9: Creating run.sh script...${NC}"
cat > "$INSTALL_DIR/run.sh" << EOF
#!/bin/bash
# This script activates the virtual environment and starts the Flask server.
echo "Starting the Bird Detection Display..."
cd "$INSTALL_DIR"
source venv/bin/activate
python3 birdnet_display.py
EOF
chmod +x "$INSTALL_DIR/run.sh"
echo -e "${GREEN}✅ run.sh created and made executable.${NC}"

# --- Step 10: Optional Raspberry Pi Kiosk Setup ---
echo ""
read -p "Are you setting this up on a Raspberry Pi for a kiosk display? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}--- Configuring Raspberry Pi Kiosk Mode ---${NC}"
    echo -e "${YELLOW}This section requires sudo permissions for system changes...${NC}"

    # 9.1: Install Kiosk dependencies
    echo -e "\n${YELLOW}Installing kiosk dependencies (chromium-browser, unclutter)...${NC}"
    sudo apt-get update
    sudo apt-get install -y chromium-browser unclutter

    # 9.2: Create and enable systemd service to run the app on boot
    echo -e "\n${YELLOW}Creating systemd service to auto-start the application...${NC}"
    SERVICE_FILE="/etc/systemd/system/bird-display.service"
    CURRENT_USER=$(whoami)
    
    # Use tee with sudo to write the protected file
    tee /tmp/bird-display.service << EOF
[Unit]
Description=Bird Detection Display Flask App
After=network.target caddy.service birdnet-pi.service
Wants=caddy.service birdnet-pi.service

[Service]
User=$CURRENT_USER
Group=$(id -gn "$CURRENT_USER")
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/run.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    sudo mv /tmp/bird-display.service "$SERVICE_FILE"

    echo -e "\n${YELLOW}Enabling and starting the service...${NC}"
    sudo systemctl daemon-reload
    sudo systemctl enable bird-display.service
    sudo systemctl start bird-display.service
    echo -e "${GREEN}✅ Systemd service created and enabled.${NC}"

    # 9.3: Configure desktop autostart using the more robust .desktop file method
    echo -e "\n${YELLOW}Configuring desktop autostart for kiosk mode...${NC}"
    
    # Create the launcher script with a delay
    LAUNCHER_SCRIPT="$INSTALL_DIR/kiosk_launcher.sh"
    cat > "$LAUNCHER_SCRIPT" << EOF
#!/bin/bash
# Add a delay to allow the desktop and network to fully initialize
sleep 15
# Launch Chromium
/usr/bin/chromium-browser --noerrdialogs --disable-infobars --kiosk http://localhost:5000
EOF
    chmod +x "$LAUNCHER_SCRIPT"
    echo -e "${GREEN}  - Created kiosk launcher script.${NC}"
    
    # Create the autostart directory
    AUTOSTART_DIR="$HOME/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"

    # Create the .desktop file
    DESKTOP_FILE="$AUTOSTART_DIR/bird-display-kiosk.desktop"
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Bird Display Kiosk
Exec=$LAUNCHER_SCRIPT
Comment=Starts the bird display in kiosk mode.
EOF
    echo -e "${GREEN}✅ Desktop autostart configured using .desktop file.${NC}"

    echo -e "\n${GREEN}Kiosk setup is complete. A reboot is required for the changes to take effect.${NC}"
    REBOOT_REQUIRED=true
fi

# --- Step 11: Optional BirdNET-Go Network Configuration ---
echo ""
echo -e "${YELLOW}Note: This is only required if using a dedicated network interface for the RTSP microphone.${NC}"
read -p "Do you want to configure the BirdNET-Go container to use host networking? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # --- Helper Functions ---
    function info {
        echo -e "${GREEN}[INFO]${NC} $1"
    }

    function warn {
        echo -e "${YELLOW}[WARN]${NC} $1"
    }

    function error {
        echo -e "${RED}[ERROR]${NC} $1"
    }

    # --- Main Script ---

    # 1. Check if Docker is installed and running
    if ! command -v docker &> /dev/null || ! sudo docker info &> /dev/null; then
        error "Docker is not installed or the Docker daemon is not running. (Sudo check)"
        exit 1
    fi

    info "Starting BirdNET-Go network configuration check..."
    info "This section will use 'sudo' for system changes."

    # 2. Check if the systemd service file exists
    CONTAINER_NAME="birdnet-go"
    SERVICE_FILE="/etc/systemd/system/${CONTAINER_NAME}.service"
    if [ ! -f "$SERVICE_FILE" ]; then
        error "Systemd service file not found at ${SERVICE_FILE}."
        warn "This script is designed for installations managed by the official systemd service."
        warn "Cannot proceed with the update."
        exit 1
    fi
    info "Found systemd service file: ${SERVICE_FILE}"

    # 3. Check if host network mode is already applied
    if sudo grep -q -- '--network host' "$SERVICE_FILE"; then
        info "Network mode is already set to 'host'. No changes needed."
        exit 0
    fi
    info "Network mode is not 'host'. Preparing to apply update."

    # 4. Backup, Stop, and Clean Up
    info "Stopping the ${CONTAINER_NAME} service..."
    sudo systemctl stop "${CONTAINER_NAME}.service"

    info "Backing up original service file to ${SERVICE_FILE}.bak..."
    sudo cp "$SERVICE_FILE" "${SERVICE_FILE}.bak"

    DROP_IN_DIR="/etc/systemd/system/${CONTAINER_NAME}.service.d"
    if [ -d "$DROP_IN_DIR" ]; then
        info "Found and removing systemd drop-in override directory to ensure a clean configuration."
        sudo rm -rf "$DROP_IN_DIR"
    fi

    # 5. Regenerate the Service File
    info "Regenerating the service file with host network mode..."

    # Extract key values from the backup file to preserve the user's setup
    # We need to read the backup file which is root-owned.
    BACKUP_CONTENT=$(sudo cat "${SERVICE_FILE}.bak")
    IMAGE=$(echo "$BACKUP_CONTENT" | grep -o 'ghcr.io/tphakala/birdnet-go:[^ ]*' | head -n 1)
    TZ=$(echo "$BACKUP_CONTENT" | grep -oP '(?<=--env TZ=")[^"]*' | head -n 1)
    UID_VAL=$(echo "$BACKUP_CONTENT" | grep -oP '(?<=--env BIRDNET_UID=)\S+' | head -n 1)
    GID_VAL=$(echo "$BACKUP_CONTENT" | grep -oP '(?<=--env BIRDNET_GID=)\S+' | head -n 1)
    CONFIG_DIR=$(echo "$BACKUP_CONTENT" | grep -oP '(?<=-v )\S+:/config' | cut -d: -f1 | head -n 1)
    DATA_DIR=$(echo "$BACKUP_CONTENT" | grep -oP '(?<=-v )\S+:/data' | cut -d: -f1 | head -n 1)

    # Preserve optional flags
    AUDIO_DEVICE_FLAG=""
    if echo "$BACKUP_CONTENT" | grep -q -- '--device /dev/snd'; then
        AUDIO_DEVICE_FLAG="--device /dev/snd \\
    "
    fi
    THERMAL_FLAG=""
    if echo "$BACKUP_CONTENT" | grep -q -- '-v /sys/class/thermal'; then
        THERMAL_FLAG="-v /sys/class/thermal:/sys/class/thermal:ro \\
    "
    fi

    # Use extracted values or fall back to sensible defaults if parsing failed
    : ${IMAGE:="ghcr.io/tphakala/birdnet-go:nightly"}
    : ${TZ:=$(cat /etc/timezone 2>/dev/null || echo "UTC")}
    : ${UID_VAL:=$(id -u)}
    : ${GID_VAL:=$(id -g)}
    # Use the current user's home directory
    : ${CONFIG_DIR:="$HOME/birdnet-go-app/config"}
    : ${DATA_DIR:="$HOME/birdnet-go-app/data"}


    # Generate the new service file content using a heredoc for clarity and reliability
    read -r -d '' NEW_SERVICE_CONTENT <<EOF
[Unit]
Description=BirdNET-Go
After=docker.service
Requires=docker.service
RequiresMountsFor=${CONFIG_DIR}/hls

[Service]
Restart=always
# Remove any existing birdnet-go container to prevent name conflicts
ExecStartPre=-/usr/bin/docker rm -f birdnet-go
# Create tmpfs mount for HLS segments
ExecStartPre=/bin/mkdir -p ${CONFIG_DIR}/hls
# Mount tmpfs, the '|| true' ensures it doesn't fail if already mounted
ExecStartPre=/bin/sh -c 'mount -t tmpfs -o size=50M,mode=0755,uid=${UID_VAL},gid=${GID_VAL},noexec,nosuid,nodev tmpfs ${CONFIG_DIR}/hls || true'
ExecStart=/usr/bin/docker run --rm \
    --name ${CONTAINER_NAME} \
    --network host \
    --env TZ="${TZ}" \
    --env BIRDNET_UID=${UID_VAL} \
    --env BIRDNET_GID=${GID_VAL} \
    ${AUDIO_DEVICE_FLAG}-v ${CONFIG_DIR}:/config \
    -v ${DATA_DIR}:/data \
    ${THERMAL_FLAG}${IMAGE}
# Cleanup tasks on stop
ExecStopPost=/bin/sh -c 'umount -f ${CONFIG_DIR}/hls || true'
ExecStopPost=-/usr/bin/docker rm -f birdnet-go

[Install]
WantedBy=multi-user.target
EOF

    # Overwrite the service file. Using tee with sudo to ensure correct permissions.
    echo "$NEW_SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null
    if [ ${PIPESTATUS[1]} -ne 0 ]; then
        error "Failed to write new service file. Restoring from backup."
        sudo mv "${SERVICE_FILE}.bak" "$SERVICE_FILE"
        exit 1
    fi

    # 6. Reload systemd and restart the service
    info "Reloading systemd daemon..."
    sudo systemctl daemon-reload

    info "Restarting the ${CONTAINER_NAME} service with the new configuration..."
    sudo systemctl restart "${CONTAINER_NAME}.service"

    # 7. Verify the change
    info "Waiting a moment for the container to start..."
    sleep 5 # Give the container a few seconds to initialize

    if sudo docker ps --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
        info "Container is running."
        NETWORK_MODE=$(sudo docker inspect ${CONTAINER_NAME} --format '{{.HostConfig.NetworkMode}}')
        if [ "$NETWORK_MODE" == "host" ]; then
            info "✅ Success! Container is now running with host network mode."
            # Clean up backup file on success
            sudo rm -f "${SERVICE_FILE}.bak"
        else
            error "Verification failed. Container is running but not in host mode."
            error "Current mode: ${NETWORK_MODE}"
            warn "Restoring original service file from ${SERVICE_FILE}.bak"
            sudo mv "${SERVICE_FILE}.bak" "$SERVICE_FILE"
            sudo systemctl daemon-reload
            sudo systemctl restart "${CONTAINER_NAME}.service"
        fi
    else
        error "Container failed to start after the update."
        warn "Check the service status with: systemctl status ${CONTAINER_NAME}.service"
        warn "Check the container logs with: docker logs ${CONTAINER_NAME}"
        warn "Restoring original service file from ${SERVICE_FILE}.bak"
        sudo mv "${SERVICE_FILE}.bak" "$SERVICE_FILE"
        sudo systemctl daemon-reload
    fi
fi

# --- Reboot Prompt ---
if [ "$REBOOT_REQUIRED" = true ]; then
    echo ""
    read -p "Kiosk mode was configured. Reboot now to apply changes? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo reboot
    fi
fi

# --- Final Instructions ---
echo -e "\n${GREEN}--- 🎉 Setup Complete! ---${NC}"
echo -e "The application has been installed in ${YELLOW}$INSTALL_DIR${NC}"
echo -e "To start the application manually, simply run:"
echo -e "\n  ${YELLOW}$INSTALL_DIR/run.sh${NC}\n"
echo -e "Then, open a web browser on any device on your network to the server's IP address (e.g., http://192.168.1.123:5000)."