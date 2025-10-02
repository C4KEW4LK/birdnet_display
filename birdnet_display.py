import requests
from flask import Flask, render_template, url_for, send_file, request, jsonify
from urllib.parse import urljoin
from datetime import datetime, timedelta
import os
import random
import socket
import qrcode
import io
import json
import sys

# Import variables and functions from the new cache builder script
from cache_builder import CACHE_DIRECTORY, SPECIES_FILE, load_species_from_file

# --- Constants and Configuration ---
BASE_URL = "http://localhost:8080/"
API_ENDPOINT = "api/v2/detections/recent"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json'
}
PROXIES = {"http": None, "https": None}
SERVER_PORT = 5000
PINNED_SPECIES_FILE = "pinned_species.json"
PINNED_DURATION_HOURS = 24

# --- Flask App Initialization ---
app = Flask(__name__, template_folder='static')

# --- Caching & Status Globals ---
DETECTION_CACHE = { "id": None, "raw_data": [] }

# --- Pinned Species Management ---
def load_pinned_species():
    """Load pinned species from JSON file."""
    if not os.path.exists(PINNED_SPECIES_FILE):
        return {}
    try:
        with open(PINNED_SPECIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading pinned species file: {e}")
        return {}

def save_pinned_species(pinned_data):
    """Save pinned species to JSON file."""
    try:
        with open(PINNED_SPECIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(pinned_data, f, indent=2)
    except IOError as e:
        print(f"Error saving pinned species file: {e}")

def add_pinned_species(species_name):
    """Add a species to the pinned list with 24-hour expiration."""
    pinned = load_pinned_species()
    if species_name not in pinned or pinned[species_name].get('dismissed', False):
        pinned[species_name] = {
            'pinned_until': (datetime.now() + timedelta(hours=PINNED_DURATION_HOURS)).isoformat(),
            'dismissed': False
        }
        save_pinned_species(pinned)

def dismiss_pinned_species(species_name):
    """Mark a pinned species as dismissed."""
    pinned = load_pinned_species()
    if species_name in pinned:
        del pinned[species_name]
        save_pinned_species(pinned)
        return True
    return False

def get_active_pinned_species():
    """Get list of currently active (not expired, not dismissed) pinned species."""
    pinned = load_pinned_species()
    active = {}
    now = datetime.now()

    for species_name, data in list(pinned.items()):
        pinned_until = datetime.fromisoformat(data['pinned_until'])
        if not data.get('dismissed', False) and now < pinned_until:
            active[species_name] = data
        elif now >= pinned_until:
            # Clean up expired entries
            del pinned[species_name]

    if len(pinned) != len(active):
        save_pinned_species(pinned)

    return active

# --- IP and QR Code Helpers ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

@app.route('/qr_code.png')
def qr_code():
    ip = get_local_ip()
    url = f"http://{ip}:8080"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# --- Time Helper Functions ---
def parse_absolute_time_to_seconds_ago(time_str):
    if not time_str: return 0
    try:
        time_format = "%Y-%m-%d %H:%M:%S"
        detection_time = datetime.strptime(time_str, time_format)
        time_difference = datetime.now() - detection_time
        return max(0, time_difference.total_seconds())
    except (ValueError, TypeError):
        return 0

def format_seconds_ago(total_seconds):
    if total_seconds < 60: return f"{int(total_seconds)}s ago"
    minutes = total_seconds / 60
    if minutes < 60: return f"{int(minutes)}m ago"
    hours = minutes / 60
    if hours < 24: return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"

# --- Data Parsing and API Helpers ---
def parse_v2_detection_item(detection, server_ip):
    try:
        name = detection.get('commonName', 'Unknown Species')
        time_raw = f"{detection.get('date', '')} {detection.get('time', '')}".strip()
        confidence_value = int(detection.get('confidence', 0.0) * 100)
        species_code = detection.get('speciesCode')
        image_url = f"http://{server_ip}:8080/api/v2/species/{species_code}/thumbnail" if species_code else ""
        is_new_species = detection.get('isNewSpecies', False)
        return {
            "name": name, "time_raw": time_raw, "confidence_value": confidence_value,
            "image_url": image_url, "copyright": "", "is_new_species": is_new_species
        }
    except (AttributeError, TypeError, KeyError) as e:
        print(f"Warning: Could not parse a v2 detection item, skipping. Error: {e}, Data: {detection}")
        return None

# --- Core Data Fetching Logic ---
def get_cached_image(species_name):
    species_folder_name = "".join(c for c in species_name if c.isalnum() or c in ' _').rstrip().replace(' ', '_')
    species_dir = os.path.join(CACHE_DIRECTORY, species_folder_name)
    if os.path.isdir(species_dir):
        images = sorted([f for f in os.listdir(species_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        if not images: return None
        chosen_image = random.choice(images)
        attr_path = os.path.join(species_dir, f"{os.path.splitext(chosen_image)[0]}.txt")
        copyright_info = ""
        if os.path.exists(attr_path):
            with open(attr_path, 'r', encoding='utf-8') as f: copyright_info = f.read().strip()
        image_url = url_for('static', filename=os.path.join(os.path.basename(CACHE_DIRECTORY), species_folder_name, chosen_image).replace('\\', '/'))
        return {"image_url": image_url, "copyright": copyright_info}
    return None

def get_offline_fallback_data():
    print("[INFO] Loading data from local cache.")
    species_list = load_species_from_file(SPECIES_FILE)
    if not species_list: return []
    fallback_data = []
    num_to_sample = min(len(species_list), 4)
    sampled_species = random.sample(species_list, num_to_sample)
    for common_name, scientific_name in sampled_species:
        cached_asset = get_cached_image(common_name)
        if cached_asset:
            fallback_data.append({
                "name": common_name, "time_display": "Offline", "confidence": "0%",
                "confidence_value": 0, "image_url": cached_asset['image_url'],
                "copyright": cached_asset['copyright'], "time_raw": "", "is_offline": True
            })
    return fallback_data

def get_bird_data():
    server_ip = get_local_ip()
    api_url = urljoin(BASE_URL, API_ENDPOINT)
    params = {'limit': 50}
    try:
        response = requests.get(api_url, headers=HEADERS, proxies=PROXIES, timeout=10, params=params)
        response.raise_for_status()
        detections = response.json()
        if not isinstance(detections, list) or not detections:
            return get_offline_fallback_data(), True
        all_parsed = [d for d in [parse_v2_detection_item(item, server_ip) for item in detections] if d]
        if not all_parsed:
            return get_offline_fallback_data(), True

        # Process new species and add to pinned list
        for bird in all_parsed:
            if bird.get('is_new_species', False):
                add_pinned_species(bird['name'])

        # Get currently active pinned species
        active_pinned = get_active_pinned_species()

        # Separate pinned and unpinned birds
        pinned_birds = []
        unpinned_birds = []

        for bird in all_parsed:
            if bird['name'] in active_pinned:
                bird['is_pinned'] = True
                if bird['name'] not in [b['name'] for b in pinned_birds]:
                    pinned_birds.append(bird)
            else:
                bird['is_pinned'] = False
                unpinned_birds.append(bird)

        # Get unique unpinned species (deduplicate by name)
        unique_unpinned = []
        seen_names = set()
        for bird in unpinned_birds:
            if bird['name'] not in seen_names:
                unique_unpinned.append(bird)
                seen_names.add(bird['name'])

        # Combine: pinned first, then unpinned, limit to 4
        final_list = pinned_birds + unique_unpinned
        final_list = final_list[:4]

        new_id = "-".join([f"{d['name']}_{d['time_raw']}" for d in final_list])

        if new_id == DETECTION_CACHE["id"]:
            data_to_process = DETECTION_CACHE["raw_data"]
        else:
            DETECTION_CACHE["raw_data"] = final_list
            DETECTION_CACHE["id"] = new_id
            data_to_process = final_list

        display_data = []
        for bird in data_to_process:
            bird_display_copy = bird.copy()
            bird_display_copy['time_display'] = format_seconds_ago(parse_absolute_time_to_seconds_ago(bird['time_raw']))
            bird_display_copy['confidence'] = f"{bird['confidence_value']}%"
            display_data.append(bird_display_copy)

        return display_data, False
    except requests.exceptions.RequestException:
        print("[INFO] BirdNET-Go API unavailable, using offline mode")
        return get_offline_fallback_data(), True

# --- Flask Routes ---
@app.route('/')
def index():
    bird_data, api_is_down = get_bird_data()
    if not os.path.exists('static'): os.makedirs('static')
    template_path = 'index.html'
    if not os.path.exists(os.path.join('static', template_path)):
         with open(os.path.join('static', template_path), 'w') as f:
              f.write('<h1>Template file not found. Please create an index.html file.</h1>')
    refresh_interval = 30 if api_is_down else 5
    server_url = f"http://{get_local_ip()}:8080"
    return render_template(
        template_path, birds=bird_data, refresh_interval=refresh_interval, 
        api_is_down=api_is_down, server_url=server_url
    )

@app.route('/data')
def data():
    bird_data, api_is_down = get_bird_data()
    return jsonify({'birds': bird_data, 'api_is_down': api_is_down})

@app.route('/audio_status')
def audio_status():
    try:
        status_url = "http://10.42.0.50/api/status"
        response = requests.get(status_url, timeout=5)
        response.raise_for_status()
        status_data = response.json()
        is_connected = status_data.get("streaming") is True
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError):
        print("[INFO] Microphone status unavailable")
        is_connected = False
    return jsonify({"connected": is_connected})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    shutdown_func = request.environ.get('werkzeug.server.shutdown')
    if shutdown_func:
        print("Shutdown request received. Shutting down server...")
        shutdown_func()
        return 'Server is shutting down...'
    else:
        print('Error: Not running with the Werkzeug Server. Cannot shut down.')
        return 'Server not running with Werkzeug.', 500

@app.route('/brightness', methods=['POST'])
def set_brightness():
    try:
        brightness = request.json.get('brightness')
        if brightness is not None and 0 <= int(brightness) <= 255:
            command = f"echo {brightness} | sudo tee /sys/class/backlight/10-0045/brightness"
            print(f"Executing brightness command: {command}")
            os.system(command)
            return jsonify({'status': 'success', 'brightness': brightness})
        return jsonify({'status': 'error', 'message': 'Invalid brightness value'}), 400
    except Exception as e:
        print(f"Error setting brightness: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/reboot', methods=['POST'])
def reboot_system():
    print("Executing reboot command...")
    os.system('sudo reboot')
    return jsonify({'status': 'rebooting'})

@app.route('/poweroff', methods=['POST'])
def poweroff_system():
    print("Executing power off command...")
    os.system('sudo poweroff')
    return jsonify({'status': 'shutting down'})

@app.route('/api/pinned_species')
def get_pinned_species():
    """Return list of currently pinned species with time remaining."""
    active_pinned = get_active_pinned_species()
    now = datetime.now()
    result = []

    for species_name, data in active_pinned.items():
        pinned_until = datetime.fromisoformat(data['pinned_until'])
        time_remaining = pinned_until - now
        hours_remaining = int(time_remaining.total_seconds() / 3600)

        result.append({
            'name': species_name,
            'hours_remaining': hours_remaining,
            'pinned_until': data['pinned_until']
        })

    return jsonify(result)

@app.route('/api/dismiss_pinned/<species_name>', methods=['POST'])
def dismiss_pinned(species_name):
    """Dismiss a pinned species."""
    success = dismiss_pinned_species(species_name)
    if success:
        return jsonify({'status': 'success', 'message': f'{species_name} dismissed'})
    else:
        return jsonify({'status': 'error', 'message': f'{species_name} not found in pinned list'}), 404


# --- Main Execution ---
if __name__ == '__main__':
    if '--build-cache' in sys.argv:
        print("To build the cache, please run 'python cache_builder.py' directly.")
        sys.exit()
    
    print(f"Starting Flask server on http://0.0.0.0:{SERVER_PORT}")
    app.run(host='0.0.0.0', port=SERVER_PORT)