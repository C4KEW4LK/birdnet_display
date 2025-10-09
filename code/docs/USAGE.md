# BirdNET Display - Command Line Usage

## Main Server (`birdnet_display`)

### Basic Usage
```bash
# Start with defaults (localhost:8080 API, port 5000)
./birdnet_display
```

### Command-Line Options
```bash
# View all options
./birdnet_display -h

# Custom BirdNET-Go API URL
./birdnet_display -apiURL http://192.168.1.169:8080

# Custom server port
./birdnet_display -port 8000

# Both options combined
./birdnet_display -apiURL http://192.168.1.169:8080 -port 8000
```

### Examples

**Local development:**
```bash
./birdnet_display
# Uses: http://localhost:8080 for API
# Serves on: http://localhost:5000
```

**Remote BirdNET-Go server:**
```bash
./birdnet_display -apiURL http://192.168.1.169:8080
# Uses: http://192.168.1.169:8080 for API
# Serves on: http://localhost:5000
```

**Custom port:**
```bash
./birdnet_display -port 8000
# Uses: http://localhost:8080 for API
# Serves on: http://localhost:8000
```

---

## Cache Builder (`cache_builder`)

### Basic Usage
```bash
# Build cache from species_list.csv
./cache_builder
```

### Command-Line Options
```bash
# View all options
./cache_builder -h

# Custom BirdNET-Go API URL
./cache_builder -apiURL http://192.168.1.169:8080

# Update species list from BirdNET-Go API
./cache_builder -update-species

# Both options combined
./cache_builder -apiURL http://192.168.1.169:8080 -update-species
```

### Examples

**Build cache from existing species_list.csv:**
```bash
./cache_builder
```

**Update species list from API, then build cache:**
```bash
./cache_builder -update-species
# Prompts for confirmation before overwriting species_list.csv
# Then builds cache with the updated species list
```

**Use remote BirdNET-Go server:**
```bash
./cache_builder -apiURL http://192.168.1.169:8080 -update-species
# Fetches species from remote server
# Builds cache with those species
```

---

## Common Scenarios

### Scenario 1: BirdNET-Go on Same Machine
```bash
# Start server (uses localhost by default)
./birdnet_display

# Build cache (uses localhost by default)
./cache_builder
```

### Scenario 2: BirdNET-Go on Different Machine
```bash
# Start server pointing to remote BirdNET-Go
./birdnet_display -apiURL http://192.168.1.100:8080

# Build cache from remote BirdNET-Go
./cache_builder -apiURL http://192.168.1.100:8080 -update-species
```

### Scenario 3: Custom Display Port
```bash
# Run display on port 8000 instead of 5000
./birdnet_display -port 8000

# Access at: http://localhost:8000
```

### Scenario 4: First-Time Setup with Remote Server
```bash
# 1. Update species list from remote server
./cache_builder -apiURL http://192.168.1.100:8080 -update-species

# 2. Build image cache (uses updated species_list.csv)
# This is done automatically by the previous command

# 3. Start display server
./birdnet_display -apiURL http://192.168.1.100:8080
```

---

## Default Values

| Option | Default Value | Description |
|--------|--------------|-------------|
| `-apiURL` | `http://localhost:8080` | BirdNET-Go API base URL |
| `-port` | `5000` | Display server port (main server only) |
| `-update-species` | `false` | Update species from API (cache builder only) |

---

## Tips

1. **URL Format**: Include the protocol (`http://`) in the `-apiURL` parameter
2. **Port Numbers**: The API URL should include the BirdNET-Go port (usually 8080)
3. **Trailing Slashes**: Trailing slashes in URLs are automatically removed
4. **Help Flag**: Use `-h` on any command to see all available options
5. **Windows**: On Windows, use `.exe` extension (e.g., `birdnet_display.exe -h`)
