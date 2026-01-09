import os
import re
import csv
import requests
from urllib.parse import urljoin, quote_plus
from PIL import Image
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import random

# --- Constants and Configuration ---
CACHE_DIRECTORY = "static/bird_images_cache"
SPECIES_FILE = "species_list.csv"
IMAGES_PER_SPECIES = 3
BIRDNET_API_BASE = "http://localhost:8080"
MIN_IMAGE_WIDTH = 800
MIN_IMAGE_HEIGHT = 600
MAX_WORKERS = 3  # Number of parallel download threads (reduced to avoid triggering rate limits)
REQUEST_DELAY = 0.5  # Delay between requests in seconds (reduced since we're mimicking browser better)
SKIP_QUALITY_CHECKS = False  # Set to True to skip description checks for faster caching (saves ~50% of page fetches)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

# Thread-safe print lock
print_lock = threading.Lock()

# Session will be created when needed
_session = None
_last_request_time = 0
_request_lock = threading.Lock()

def get_session():
    """Get or create a requests session for connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
    return _session

def rate_limited_get(url, timeout=10, max_retries=3):
    """Make a GET request with rate limiting and retry logic for 429 errors."""
    global _last_request_time

    for attempt in range(max_retries):
        # Rate limiting: ensure minimum delay between requests with natural variation
        with _request_lock:
            current_time = time.time()
            time_since_last = current_time - _last_request_time
            # Add random variation (±30%) to look more human
            actual_delay = REQUEST_DELAY * random.uniform(0.7, 1.3)
            if time_since_last < actual_delay:
                time.sleep(actual_delay - time_since_last)
            _last_request_time = time.time()

        try:
            response = get_session().get(url, timeout=timeout)

            # Handle 429 rate limit errors with exponential backoff
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 5))
                backoff_time = min(retry_after, 2 ** attempt * 5)  # Exponential backoff, max based on retry-after
                with print_lock:
                    print(f"[RATE LIMIT] 429 error. Waiting {backoff_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(backoff_time)
                continue

            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            with print_lock:
                print(f"[RETRY] Request failed, attempt {attempt + 1}/{max_retries}: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff

    raise requests.exceptions.RequestException(f"Failed after {max_retries} attempts")

# Color codes for terminal output
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
GREEN = '\033[0;32m'
NC = '\033[0m'  # No Color

# --- Helper Functions ---
def format_author_name(author_str):
    if not author_str: return ""
    cleaned_author = author_str.split('[a]')[0].strip()
    if len(cleaned_author) > 20:
        cut_off_point = cleaned_author.rfind(' ', 0, 20)
        return cleaned_author[:cut_off_point] + " ..." if cut_off_point != -1 else cleaned_author[:20] + " ..."
    return cleaned_author

UNWANTED_KEYWORDS = ("egg", "map", "illustration", "scanned", "specimen", "habitat", "distribution", "preserved")

def extract_description_text(page_soup):
    """Try to extract a short description from a Wikimedia file page."""
    candidates = []
    desc_div = page_soup.find('div', class_=re.compile('description', re.I))
    if desc_div:
        candidates.append(desc_div.get_text(" ", strip=True))
    content_div = page_soup.find('div', id='mw-content-text')
    if content_div:
        first_p = content_div.find('p')
        if first_p:
            candidates.append(first_p.get_text(" ", strip=True))
    for text in candidates:
        if text:
            return text
    return ""

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

def check_location_settings():
    """Check if location is set in BirdNET-Go settings."""
    settings_url = f"{BIRDNET_API_BASE}/api/v2/settings"
    try:
        response = get_session().get(settings_url, timeout=10)
        response.raise_for_status()
        settings = response.json()

        # Navigate to birdnet section for lat/lon
        birdnet_settings = settings.get('birdnet', {})
        latitude = birdnet_settings.get('latitude')
        longitude = birdnet_settings.get('longitude')

        # Check if location is set to reasonable values
        # Not set if: missing keys, null, zero, or outside valid ranges
        if latitude is None or longitude is None:
            return False
        if latitude == 0 and longitude == 0:
            return False
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return False

        print(f"[INFO] Location configured: Lat {latitude}, Lon {longitude}")
        return True
    except requests.exceptions.RequestException:
        print(f"{YELLOW}[WARNING] Could not verify location settings{NC}")
        return None  # Unknown state

def fetch_species_from_api():
    """Fetches species list from BirdNET-Go API."""
    api_url = f"{BIRDNET_API_BASE}/api/v2/range/species/list"
    try:
        print(f"[INFO] Fetching species list from {api_url}")
        response = get_session().get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        species_list = []
        for species in data.get('species', []):
            common_name = species.get('commonName', '').strip()
            scientific_name = species.get('scientificName', '').strip()
            if common_name and scientific_name:
                species_list.append((common_name, scientific_name))
        print(f"[INFO] Found {len(species_list)} species from API")
        return species_list
    except requests.exceptions.ConnectionError:
        print(f"{RED}[ERROR] Cannot connect to BirdNET-Go at {BIRDNET_API_BASE}{NC}")
        print(f"{RED}[ERROR] Please ensure BirdNET-Go is running and accessible{NC}")
        return None
    except requests.exceptions.Timeout:
        print(f"{RED}[ERROR] Connection to {BIRDNET_API_BASE} timed out{NC}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"{RED}[ERROR] Failed to fetch species from API: {e}{NC}")
        return None

def save_species_to_file(species_list, filename):
    """Saves species list to CSV file."""
    try:
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Common Name', 'Scientific Name'])
            for common_name, scientific_name in species_list:
                writer.writerow([common_name, scientific_name])
        print(f"{GREEN}[INFO] Saved {len(species_list)} species to {filename}{NC}")
        return True
    except IOError as e:
        print(f"{RED}[ERROR] Failed to save species to file: {e}{NC}")
        return False

def update_species_list_from_api():
    """Updates species_list.csv from BirdNET-Go API with user confirmation."""
    # Check location settings first
    location_set = check_location_settings()
    if location_set is False:
        print(f"\n{YELLOW}[WARNING] It looks like the location used for range data is not set in BirdNET-Go.{NC}")
        print(f"{YELLOW}[WARNING] The species list may not be accurate for your location.{NC}")
        confirm = input("Would you still like to continue? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("[INFO] Operation cancelled by user")
            return False

    species_list = fetch_species_from_api()
    if not species_list:
        print(f"{RED}[ERROR] Could not fetch species list from API{NC}")
        return False

    # Check if file exists
    file_exists = os.path.exists(SPECIES_FILE)
    if file_exists:
        print(f"\n{YELLOW}[WARNING] This will overwrite the existing '{SPECIES_FILE}' file.{NC}")
        existing_list = load_species_from_file(SPECIES_FILE)
        print(f"Current file has {len(existing_list)} species, API has {len(species_list)} species.")
    else:
        print(f"\n'{SPECIES_FILE}' does not exist. A new file will be created.")

    confirm = input("Do you want to continue? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("[INFO] Operation cancelled by user")
        return False

    return save_species_to_file(species_list, SPECIES_FILE)

# --- Web Scraping and Downloading ---
def construct_optimal_thumbnail_url(thumbnail_url, target_width=1024):
    """Construct a thumbnail URL with specific size without fetching the file page."""
    try:
        # Wikimedia thumbnail URLs have pattern: .../thumb/.../filename/XXXpx-filename
        # We can construct the desired size directly
        if '/thumb/' in thumbnail_url:
            # Extract the base filename
            parts = thumbnail_url.rsplit('/', 1)
            if len(parts) == 2:
                base_path = parts[0]
                # Construct new thumbnail with target width
                # Get the original filename from the base path
                filename_match = re.search(r'/([^/]+)$', base_path.rsplit('/thumb/', 1)[1])
                if filename_match:
                    filename = filename_match.group(1)
                    # Construct the thumbnail URL
                    return f"{base_path}/{target_width}px-{filename}"
        return thumbnail_url
    except Exception:
        return thumbnail_url

def find_optimal_image_size(page_soup):
    """Find the smallest image size that meets minimum requirements from Wikimedia page."""
    # Look for the "Other resolutions" section
    resolution_span = page_soup.find('span', class_='mw-filepage-other-resolutions')
    if not resolution_span:
        return None

    # Find all resolution links
    resolution_links = resolution_span.find_all('a', class_='mw-thumbnail-link')
    suitable_images = []

    for link in resolution_links:
        url = link.get('href', '')
        text = link.get_text(strip=True)

        # Parse dimensions like "1,024 × 1,024 pixels" or "768 × 768 pixels"
        match = re.search(r'([\d,]+)\s*×\s*([\d,]+)', text)
        if match:
            width = int(match.group(1).replace(',', ''))
            height = int(match.group(2).replace(',', ''))

            # Check if meets minimum requirements
            if width >= MIN_IMAGE_WIDTH and height >= MIN_IMAGE_HEIGHT:
                suitable_images.append({
                    'url': url,
                    'width': width,
                    'height': height,
                    'total_pixels': width * height
                })

    # Sort by total pixels (ascending) and return the smallest suitable one
    if suitable_images:
        suitable_images.sort(key=lambda x: x['total_pixels'])
        return suitable_images[0]['url']

    return None

def _fetch_and_parse_wikimedia_search(search_query, num_images, existing_urls):
    """Helper function to perform a single search query on Wikimedia and parse results."""
    base_url = "https://commons.wikimedia.org"
    search_url = f"{base_url}/w/index.php?search={quote_plus(search_query)}&title=Special:MediaSearch&go=Go&type=image"
    try:
        # Use rate-limited request for search too
        response = rate_limited_get(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        result_elements = soup.select('a.sdms-image-result')
        image_data = []
        seen_urls = set()
        for result_a_tag in list(dict.fromkeys(result_elements)):
            if len(image_data) >= num_images:
                break
            file_page_url = urljoin(base_url, result_a_tag.get('href', ''))
            img_tag = result_a_tag.find('img')
            if not file_page_url or not img_tag or not img_tag.get('data-src'): continue

            try:
                thumbnail_url = img_tag['data-src']

                # Construct optimal size URL directly from thumbnail (saves a page fetch!)
                candidate_url = construct_optimal_thumbnail_url(thumbnail_url, target_width=1024)

                # Make sure it's an absolute URL
                if candidate_url.startswith('//'):
                    candidate_url = 'https:' + candidate_url
                elif candidate_url.startswith('/'):
                    candidate_url = base_url + candidate_url

                if candidate_url in existing_urls or candidate_url in seen_urls:
                    continue

                # Fetch file page for attribution and quality checks (unless skipped)
                if SKIP_QUALITY_CHECKS:
                    # Fast mode: skip quality checks, use generic attribution
                    final_attribution = "© Wikimedia Commons"
                else:
                    # Fetch page for quality checks and detailed attribution
                    # Use rate-limited request for file page
                    page_response = rate_limited_get(file_page_url, timeout=10)
                    page_soup = BeautifulSoup(page_response.text, 'html.parser')

                    # Quick description check to filter unwanted images
                    description_text = extract_description_text(page_soup)
                    if description_text:
                        desc_lower = description_text.lower()
                        matched_keyword = next((keyword for keyword in UNWANTED_KEYWORDS if keyword in desc_lower), None)
                        if matched_keyword:
                            with print_lock:
                                print(f"[SKIP] Skipping image because description mentions unwanted keyword '{matched_keyword}' for query '{search_query}'")
                            continue

                    # Get attribution
                    attribution = "Wikimedia Commons"
                    author_header = page_soup.find('td', string=re.compile(r'^\s*Author\s*$'))
                    if author_header and author_header.find_next_sibling('td'):
                        attribution_cell = author_header.find_next_sibling('td')
                        attribution = attribution_cell.get_text(strip=True, separator=' ').split('(')[0].strip()
                    formatted_attribution = format_author_name(attribution)
                    final_attribution = f"© {formatted_attribution}" if formatted_attribution else "© Wikimedia Commons"

                image_data.append({'url': candidate_url, 'attribution': final_attribution})
                seen_urls.add(candidate_url)

            except requests.exceptions.RequestException: continue
        return image_data
    except requests.exceptions.RequestException as e:
        print(f"Error scraping Wikimedia for query '{search_query}': {e}")
        return []

def scrape_wikimedia_for_image_data(common_name, scientific_name, num_images, existing_urls):
    """Searches Wikimedia with a priority of queries to find the best quality images."""
    # Use a single, more specific query that's most likely to succeed
    # Scientific name + common name gives best results in one query
    primary_query = f"{scientific_name} {common_name}"
    collected = []

    # Try primary query with higher limit to get all needed images in one search
    image_data = _fetch_and_parse_wikimedia_search(primary_query, num_images * 2, existing_urls)
    collected.extend(image_data[:num_images])

    # Only try fallback queries if we didn't get enough images
    if len(collected) < num_images:
        needed = num_images - len(collected)
        fallback_query = f"{common_name} bird"
        image_data = _fetch_and_parse_wikimedia_search(fallback_query, needed, existing_urls | {img['url'] for img in collected})
        collected.extend(image_data)

    return collected

def download_image_and_attribution(image_info, folder_path, file_name_base, existing_urls):
    """Downloads an image and saves its attribution, skipping if files already exist or cached URL matches."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path, exist_ok=True)
    file_ext = os.path.splitext(image_info['url'].split('(')[0])[-1] or ".jpg"
    image_file_path = os.path.join(folder_path, f"{file_name_base}{file_ext}")
    attr_file_path = os.path.join(folder_path, f"{file_name_base}.txt")
    if image_info['url'] in existing_urls:
        with print_lock:
            print(f"[SKIP] URL already cached for {file_name_base}")
        return
    if os.path.exists(image_file_path) and os.path.exists(attr_file_path): return
    try:
        image_response = rate_limited_get(image_info['url'], timeout=15)
        with open(image_file_path, 'wb') as f: f.write(image_response.content)
        with open(attr_file_path, 'w', encoding='utf-8') as f:
            f.write(f"URL: {image_info['url']}\n")
            f.write(f"Attribution: {image_info['attribution']}")
        existing_urls.add(image_info['url'])
        with print_lock:
            print(f"Successfully cached {os.path.basename(image_file_path)}")
    except (requests.exceptions.RequestException, IOError) as e:
        with print_lock:
            print(f"Failed to download/save for {file_name_base}. Error: {e}")

# --- Main Cache Building Process ---
def process_species(species_info):
    """Process a single species - fetch and download images."""
    common_name, scientific_name = species_info
    species_folder_name = "".join(c for c in common_name if c.isalnum() or c in ' _').rstrip().replace(' ', '_')
    species_folder_path = os.path.join(CACHE_DIRECTORY, species_folder_name)
    existing_urls = set()
    if os.path.isdir(species_folder_path):
        for fname in os.listdir(species_folder_path):
            if fname.lower().endswith('.txt'):
                try:
                    with open(os.path.join(species_folder_path, fname), 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith("URL:"):
                                existing_urls.add(line.split("URL:", 1)[1].strip())
                except OSError:
                    continue

    # Check if already cached
    if os.path.isdir(species_folder_path):
        images_found = len([f for f in os.listdir(species_folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        if images_found >= IMAGES_PER_SPECIES:
            with print_lock:
                print(f"✓ Cache for '{common_name}' is already complete ({images_found} images). Skipping.")
            return common_name, True

    # Fetch and download images
    current_images = len([f for f in os.listdir(species_folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]) if os.path.isdir(species_folder_path) else 0
    needed = max(IMAGES_PER_SPECIES - current_images, 0)
    image_infos = scrape_wikimedia_for_image_data(common_name, scientific_name, needed, existing_urls)
    if not image_infos:
        with print_lock:
            print(f"✗ No images found for '{common_name}'")
        return common_name, False

    for i, info in enumerate(image_infos):
        download_image_and_attribution(info, species_folder_path, f"{species_folder_name}_{i+1+current_images}", existing_urls)

    return common_name, True

def ensure_cache_is_built():
    """Checks for and builds the offline image cache with parallel processing."""
    print("--- Checking local image cache... ---")
    bird_species_to_cache = load_species_from_file(SPECIES_FILE)
    if not bird_species_to_cache:
        print(f"WARNING: '{SPECIES_FILE}' not found or empty. Cannot build cache.")
        return

    total_species = len(bird_species_to_cache)
    print(f"Processing {total_species} species with {MAX_WORKERS} parallel workers...")

    completed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_species = {executor.submit(process_species, species): species for species in bird_species_to_cache}

        # Process completed tasks
        for future in as_completed(future_to_species):
            species_name, success = future.result()
            completed += 1
            with print_lock:
                print(f"[{completed}/{total_species}] Completed: {species_name}")

    print("--- Image cache check complete. ---")

def resize_cached_images():
    """Resizes large images to fill the target screen size while maintaining aspect ratio (multi-threaded with progress)."""
    print("--- Checking and resizing large cached images... ---")
    target_width = 800
    target_height = 600

    # Collect all image paths first
    image_paths = []
    for root, _, files in os.walk(CACHE_DIRECTORY):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_paths.append(os.path.join(root, file))

    total = len(image_paths)
    if total == 0:
        print("[INFO] No cached images found to resize.")
        return

    bar_len = 30
    resized = 0
    skipped = 0
    errors = 0
    completed = 0

    def resize_one(image_path):
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                # Skip if already at or below target size
                if w <= target_width and h <= target_height:
                    return False, image_path

                scale = max(target_width / w, target_height / h)
                new_width = int(w * scale)
                new_height = int(h * scale)

                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                resized_img.save(image_path)
                return True, image_path
        except Exception:
            return None, image_path

    def print_progress():
        filled = int(bar_len * (completed / total))
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\r[{completed}/{total}] [{bar}] resized:{resized} skipped:{skipped} errors:{errors}", end="", flush=True)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(resize_one, path): path for path in image_paths}
        for future in as_completed(futures):
            result, path = future.result()
            with print_lock:
                completed += 1
                if result is True:
                    resized += 1
                elif result is False:
                    skipped += 1
                else:
                    errors += 1
                print_progress()

    print()  # newline after progress bar
    print(f"--- Image resizing complete. Resized: {resized}, Skipped: {skipped}, Errors: {errors}. ---")

# This allows the script to be run directly from the command line
if __name__ == '__main__':
    import sys

    # Check for --update-species flag
    if '--update-species' in sys.argv:
        print("--- Updating Species List from API ---")
        if update_species_list_from_api():
            print("[SUCCESS] Species list updated successfully")
            # Ask if user wants to continue with cache building
            build_cache = input("\nDo you want to build the cache now? (yes/no): ").strip().lower()
            if build_cache not in ['yes', 'y']:
                print("[INFO] Cache building skipped")
                sys.exit(0)
        else:
            print("[ERROR] Failed to update species list")
            sys.exit(1)

    print("--- Starting Offline Image Cache Builder ---")
    ensure_cache_is_built()
    resize_cached_images()
    print("--- Cache building process complete. ---")
