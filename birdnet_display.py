import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, url_for, send_file
from urllib.parse import urljoin, quote_plus
from datetime import datetime
import re
import os
import random
import csv
import socket
import qrcode
import io

# --- Constants and Configuration ---
BASE_URL = "https://127.0.0.1/"
API_ENDPOINT = "api/v1/detections/recent?numDetections=25"
USER_PASS = {'user': 'username', 'pass': 'password'}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'HX-Request': 'true'
}
PROXIES = {"http": None, "https": None}
SERVER_PORT = 5000

# --- Offline Cache Configuration ---
CACHE_DIRECTORY = "static/bird_images_cache"
SPECIES_FILE = "species_list.csv" 
IMAGES_PER_SPECIES = 3 

# --- Flask App Initialization ---
app = Flask(__name__, template_folder='static')

# --- Caching Globals ---
cached_bird_data = []
latest_detection_id = None


# --- IP and QR Code Helpers ---

def get_local_ip():
    """Finds the local IP address of the server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

@app.route('/qr_code.png')
def qr_code():
    """Generates and serves a QR code of the server's local IP address."""
    ip = get_local_ip()
    url = f"http://{ip}:{SERVER_PORT}"
    
    # Generate QR code in memory
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    
    return send_file(buf, mimetype='image/png')


# --- Time Helper Functions ---

def parse_absolute_time_to_seconds_ago(time_str):
    """Converts a timestamp string into seconds elapsed."""
    try:
        time_format = "%Y-%m-%d %H:%M:%S"
        detection_time = datetime.strptime(time_str, time_format)
        time_difference = datetime.now() - detection_time
        return max(0, time_difference.total_seconds())
    except (ValueError, TypeError):
        return 0

def format_seconds_ago(total_seconds):
    """Formats a duration in seconds into a human-readable string like '5m ago'."""
    if total_seconds < 60:
        return f"{int(total_seconds)}s ago"
    minutes = total_seconds / 60
    if minutes < 60:
        return f"{int(minutes)}m ago"
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"

# --- Data Parsing Helper ---

def format_author_name(author_str):
    """Cleans and truncates an author name string."""
    if not author_str:
        return ""
    cleaned_author = author_str.split('[a]')[0].strip()
    if len(cleaned_author) > 20:
        cut_off_point = cleaned_author.rfind(' ', 0, 20)
        return cleaned_author[:cut_off_point] + "..." if cut_off_point != -1 else cleaned_author[:20] + "..."
    return cleaned_author

def parse_detection_item(item, base_url_with_auth):
    """Parses a single detection item from the BeautifulSoup object."""
    try:
        time_raw = item.find('div', class_='text-sm').get_text(strip=True)
        name = item.select_one('a[hx-get*="/api/v1/detections/details"]').get_text(strip=True)
        image_url = item.select_one('div.thumbnail-container img')['src']
        copyright_info = ""
        tooltip_div = item.find('div', class_='thumbnail-tooltip')
        if tooltip_div:
            author = tooltip_div.get_text(strip=True).split('/')[0].strip()
            formatted_author = format_author_name(author)
            if formatted_author:
                formatted_author = formatted_author.strip("©")
                copyright_info = f"© {formatted_author}"
        confidence_value = 0
        confidence_div = item.find('div', class_='confidence-circle')
        if confidence_div and 'style' in confidence_div.attrs:
            match = re.search(r'--progress:\s*(\d+)', confidence_div['style'])
            if match:
                confidence_value = int(match.group(1))
        spectrogram_url = urljoin(base_url_with_auth, item.select_one('div.audio-player-container img')['src'])
        return {
            "name": name, "time_raw": time_raw, "confidence_value": confidence_value,
            "image_url": image_url, "copyright": copyright_info, "spectrogram_url": spectrogram_url
        }
    except (AttributeError, TypeError) as e:
        print(f"Warning: Could not parse an item, skipping. Error: {e}")
        return None

# --- Offline Image Cache Builder ---

def load_species_from_file(filename):
    """Loads a list of bird species from a CSV file (common_name, scientific_name)."""
    if not os.path.exists(filename): return []
    species_list = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2 and row[0] and row[1]:
                    species_list.append((row[0].strip(), row[1].strip()))
        return species_list
    except (IOError, csv.Error) as e:
        print(f"Error reading or parsing species CSV file '{filename}': {e}")
        return []

def _fetch_and_parse_wikimedia_search(search_query, num_images):
    """Helper function to perform a single search query on Wikimedia and parse results."""
    base_url = "https://commons.wikimedia.org"
    search_url = f"{base_url}/w/index.php?search={quote_plus(search_query)}&title=Special:MediaSearch&go=Go&type=image"
    try:
        response = requests.get(search_url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        result_elements = soup.select('a.sdms-image-result')
        image_data = []
        for result_a_tag in list(dict.fromkeys(result_elements))[:num_images]:
            file_page_url = urljoin(base_url, result_a_tag.get('href', ''))
            img_tag = result_a_tag.find('img')
            if not file_page_url or not img_tag or not img_tag.get('data-src'): continue
            thumbnail_url = img_tag['data-src']
            full_res_url = thumbnail_url.replace('/thumb', '').rsplit('/', 1)[0]
            try:
                page_response = requests.get(file_page_url, headers=HEADERS, timeout=10)
                page_soup = BeautifulSoup(page_response.text, 'html.parser')
                attribution = "Wikimedia Commons"
                author_header = page_soup.find('td', string=re.compile(r'^\s*Author\s*$'))
                if author_header and author_header.find_next_sibling('td'):
                    attribution_cell = author_header.find_next_sibling('td')
                    attribution = attribution_cell.get_text(strip=True, separator=' ').split('(')[0].strip()
                formatted_attribution = format_author_name(attribution)
                final_attribution = f"© {formatted_attribution}" if formatted_attribution else "© Wikimedia Commons"
                image_data.append({'url': full_res_url, 'attribution': final_attribution})
            except requests.exceptions.RequestException: continue
        return image_data
    except requests.exceptions.RequestException as e:
        print(f"Error scraping Wikimedia for query '{search_query}': {e}")
        return []

def scrape_wikimedia_for_image_data(common_name, scientific_name, num_images):
    """Searches Wikimedia with a priority of queries to find the best quality images."""
    search_queries = [f"{common_name} {scientific_name} bird", f"{scientific_name} bird", f"{common_name} bird"]
    for query in search_queries:
        image_data = _fetch_and_parse_wikimedia_search(query, num_images)
        if image_data: return image_data
    return []

def download_image_and_attribution(image_info, folder_path, file_name_base):
    """Downloads an image and saves its attribution, skipping if files already exist."""
    if not os.path.exists(folder_path): os.makedirs(folder_path)
    file_ext = os.path.splitext(image_info['url'].split('(')[0])[-1] or ".jpg"
    image_file_path = os.path.join(folder_path, f"{file_name_base}{file_ext}")
    attr_file_path = os.path.join(folder_path, f"{file_name_base}.txt")
    if os.path.exists(image_file_path) and os.path.exists(attr_file_path): return
    try:
        image_response = requests.get(image_info['url'], timeout=15, headers=HEADERS)
        image_response.raise_for_status()
        with open(image_file_path, 'wb') as f: f.write(image_response.content)
        with open(attr_file_path, 'w', encoding='utf-8') as f: f.write(image_info['attribution'])
        print(f"Successfully cached {os.path.basename(image_file_path)}")
    except (requests.exceptions.RequestException, IOError) as e:
        print(f"Failed to download/save for {file_name_base}. Error: {e}")

def ensure_cache_is_built():
    """Checks for and builds the offline image cache, skipping already completed species."""
    print("--- Checking local image cache... ---")
    bird_species_to_cache = load_species_from_file(SPECIES_FILE)
    if not bird_species_to_cache: return
    for common_name, scientific_name in bird_species_to_cache:
        species_folder_name = "".join(c for c in common_name if c.isalnum() or c in ' _').rstrip().replace(' ', '_')
        species_folder_path = os.path.join(CACHE_DIRECTORY, species_folder_name)
        if os.path.isdir(species_folder_path):
            images_found = len([f for f in os.listdir(species_folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
            if images_found >= IMAGES_PER_SPECIES:
                print(f"Cache for '{common_name}' is already complete ({images_found} images). Skipping.")
                continue
        image_infos = scrape_wikimedia_for_image_data(common_name, scientific_name, IMAGES_PER_SPECIES)
        if not image_infos: continue
        for i, info in enumerate(image_infos):
            download_image_and_attribution(info, species_folder_path, f"{species_folder_name}_{i+1}")
    print("--- Image cache check complete. ---")

# --- Core Data Fetching Logic ---

def is_internet_available():
    """Checks for an active internet connection by pinging Wikimedia."""
    try:
        requests.head("https://commons.wikimedia.org", timeout=3)
        return True
    except requests.RequestException:
        return False

def get_cached_image(species_name, time_raw=None):
    """
    Gets a cached image for a species.
    If time_raw is provided, the image selection is deterministic.
    Otherwise, a random image is chosen.
    """
    species_folder_name = "".join(c for c in species_name if c.isalnum() or c in ' _').rstrip().replace(' ', '_')
    species_dir = os.path.join(CACHE_DIRECTORY, species_folder_name)
    if os.path.isdir(species_dir):
        images = sorted([f for f in os.listdir(species_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        if not images:
            return None

        chosen_image = None
        if time_raw and len(time_raw) > 0:
            try:
                last_digit = int(time_raw[-1])
                image_index = last_digit % len(images)
                chosen_image = images[image_index]
            except (ValueError, IndexError):
                chosen_image = random.choice(images)
        else:
            chosen_image = random.choice(images)
        
        attr_path = os.path.join(species_dir, f"{os.path.splitext(chosen_image)[0]}.txt")
        copyright_info = "N/A"
        if os.path.exists(attr_path):
            with open(attr_path, 'r', encoding='utf-8') as f: copyright_info = f.read().strip()
        
        image_url = url_for('static', filename=os.path.join(os.path.basename(CACHE_DIRECTORY), species_folder_name, chosen_image).replace('\\', '/'))
        return {"image_url": image_url, "copyright": copyright_info}
            
    return None

def get_offline_fallback_data():
    """Provides a fresh randomized list of bird data from the local cache when the bird API is down."""
    print("[WARN] Building fresh OFFLINE data from local cache because bird API is unreachable.")
    species_list = load_species_from_file(SPECIES_FILE)
    if not species_list: return []
    
    fallback_data = []
    
    num_to_sample = min(len(species_list), 3)
    sampled_species = random.sample(species_list, num_to_sample)
    
    for common_name, scientific_name in sampled_species:
        cached_asset = get_cached_image(common_name)
        if cached_asset:
            fallback_data.append({
                "name": common_name, "time_display": "Offline", "confidence": "0%",
                "confidence_value": 0, "image_url": cached_asset['image_url'],
                "copyright": cached_asset['copyright'], "time_raw": ""
            })
    return fallback_data

def get_bird_data():
    """Fetches bird data from API and returns it along with a flag indicating API status."""
    global cached_bird_data, latest_detection_id
    base_url_with_auth = f"https://{USER_PASS['user']}:{USER_PASS['pass']}@{BASE_URL.split('//')[-1]}"
    api_url = urljoin(base_url_with_auth, API_ENDPOINT)
    
    try:
        response = requests.get(api_url, headers=HEADERS, proxies=PROXIES, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        detections = soup.find_all('div', class_='grid grid-cols-12 gap-4 items-center px-4 py-1 hover:bg-gray-50')
        if not detections: return [], False

        all_parsed = [d for d in [parse_detection_item(item, base_url_with_auth) for item in detections] if d]
        top_species = list(dict.fromkeys(d['name'] for d in all_parsed))[:3]
        new_id = "-".join(sorted(top_species))

        data_to_process = []
        if new_id == latest_detection_id and cached_bird_data:
            print("[INFO] Top species unchanged. Using data from memory cache.")
            data_to_process = cached_bird_data
        else:
            print("[INFO] New top species detected or cache empty. Refreshing data cache.")
            final_list = [next(d for d in all_parsed if d['name'] == name) for name in top_species]
            if len(final_list) < 3:
                urls_in_list = {b['image_url'] for b in final_list}
                for bird in all_parsed:
                    if len(final_list) >= 3: break
                    if bird['image_url'] not in urls_in_list: final_list.append(bird)
            cached_bird_data = final_list
            latest_detection_id = new_id
            data_to_process = final_list
            
        internet_up = is_internet_available()
        display_data = []
        for bird in data_to_process:
            bird_display_copy = bird.copy()
            bird_display_copy['time_display'] = format_seconds_ago(parse_absolute_time_to_seconds_ago(bird['time_raw']))
            bird_display_copy['confidence'] = f"{bird['confidence_value']}%"
            if not internet_up:
                cached_asset = get_cached_image(bird['name'], bird['time_raw'])
                if cached_asset:
                    bird_display_copy['image_url'] = cached_asset['image_url']
                    bird_display_copy['copyright'] = cached_asset['copyright']
                else:
                    print(f"[WARN] No cached image found for '{bird['name']}'.")
            display_data.append(bird_display_copy)
        
        if not internet_up and new_id != latest_detection_id:
            for bird in cached_bird_data:
                 cached_asset = get_cached_image(bird['name'], bird['time_raw'])
                 if cached_asset:
                    bird['image_url'] = cached_asset['image_url']
                    bird['copyright'] = cached_asset['copyright']

        return display_data, False # API is UP

    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to fetch data from API: {e}")
        return get_offline_fallback_data(), True # API is DOWN

# --- Flask Route ---
@app.route('/')
def index():
    """Renders the main page with the latest bird detection data."""
    bird_data, api_is_down = get_bird_data()
    if not bird_data:
        return "<h1>Could not find any bird detections.</h1><p>Please check the console for errors.</p>", 500
    
    refresh_interval = 30 if api_is_down else 5
    server_url = f"http://{get_local_ip()}:{SERVER_PORT}"

    return render_template(
        'index.html', 
        birds=bird_data, 
        refresh_interval=refresh_interval, 
        api_is_down=api_is_down,
        server_url=server_url
    )

# --- Main Execution ---
if __name__ == '__main__':
    ensure_cache_is_built()
    app.run(host='0.0.0.0', port=SERVER_PORT)