import deezer as deezer_api
import json
import os
import subprocess
from datetime import datetime
import hashlib
import glob
import shutil
import time
from collections import deque
from threading import Lock

USER_ID = "6605956461"
STATE_DIR = "/app/config/state"
ARTIST_STATE_DIR = f"{STATE_DIR}/artists"
FOLLOWED_ARTISTS_FILE = f"{STATE_DIR}/followed_artists.json"
RIP_CONFIG_DIR = "/app/config/streamrip"
DEEMIX_LOG_FILE = "/app/config/logs/deemix_log.txt"
RIP_LOG_FILE = f"{RIP_CONFIG_DIR}rip_log.txt"
RIP_CONFIG_FILE = f"{RIP_CONFIG_DIR}/config.toml "
MUSIC_PATH = "/music"
PLAYLISTS_PATH = f"{MUSIC_PATH}/playlists"
DOWNLOAD_ALBUMS_INSTEAD_OF_TRACKS = True

# Rate limiting settings for Deezer API: 50 requests per 5 seconds
MAX_REQUESTS = 50
TIME_WINDOW = 5.0  # seconds


class RateLimiter:
    """Thread-safe rate limiter for API calls."""
    
    def __init__(self, max_requests, time_window):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limit."""
        with self.lock:
            now = time.time()
            
            # Remove requests outside the time window
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            # If we've hit the limit, wait until the oldest request expires
            if len(self.requests) >= self.max_requests:
                sleep_time = self.requests[0] + self.time_window - now
                if sleep_time > 0:
                    print(f"Rate limit reached. Waiting {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                    # Clean up again after waiting
                    now = time.time()
                    while self.requests and self.requests[0] < now - self.time_window:
                        self.requests.popleft()
            
            # Record this request
            self.requests.append(time.time())


# Global rate limiter instance
rate_limiter = RateLimiter(MAX_REQUESTS, TIME_WINDOW)


def ensure_directories():
    """Create all necessary directories if they don't exist."""
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(ARTIST_STATE_DIR, exist_ok=True)
    os.makedirs(MUSIC_PATH, exist_ok=True)
    os.makedirs(PLAYLISTS_PATH, exist_ok=True)
    os.makedirs(RIP_CONFIG_DIR, exist_ok=True)


def fetch_all_followed_artists():
    """Fetch all artists followed by the user from Deezer API."""
    rate_limiter.wait_if_needed()
    with deezer_api.Client() as client:
        user = client.get_user(USER_ID)
        rate_limiter.wait_if_needed()
        artists = user.get_artists()
        return [{"id": a.id, "name": a.name, "link": a.link} for a in artists]


def load_followed_artists():
    """Load the list of followed artists from local storage."""
    if not os.path.exists(FOLLOWED_ARTISTS_FILE):
        return set()
    with open(FOLLOWED_ARTISTS_FILE, "r") as f:
        return json.load(f)


def save_followed_artists(artists):
    """Save the list of followed artists to local storage."""
    with open(FOLLOWED_ARTISTS_FILE, "w") as f:
        json.dump(artists, f, indent=2)


def find_all_new_releases():
    """Check all followed artists for new releases."""
    followed_artists = fetch_all_followed_artists()
    for r in followed_artists:
        print(r["name"])
        find_new_releases(r["id"], r["name"])


def fetch_all_releases(artist_id):
    """Fetch all albums/releases for a specific artist."""
    rate_limiter.wait_if_needed()
    with deezer_api.Client() as client:
        artist = client.get_artist(artist_id)
        rate_limiter.wait_if_needed()
        albums = artist.get_albums()
        return [{"id": a.id, "title": a.title, "link": a.link} for a in albums]


def load_known_releases(artist_id):
    """Load known releases for a specific artist from local storage."""
    if not os.path.exists(f"{ARTIST_STATE_DIR}/{artist_id}.json"):
        return set()
    with open(f"{ARTIST_STATE_DIR}/{artist_id}.json", "r") as f:
        return json.load(f)


def save_known_releases(artist_id, releases):
    """Save known releases for a specific artist to local storage."""
    with open(f"{ARTIST_STATE_DIR}/{artist_id}.json", "w") as f:
        json.dump(releases, f, indent=2)


def find_new_releases(artist_id, artist_name):
    """Find and download new releases for a specific artist."""
    all_releases = fetch_all_releases(artist_id)
    known_releases = load_known_releases(artist_id)
    known_ids = [r["id"] for r in known_releases]
    new_releases = [r for r in all_releases if r["id"] not in known_ids]
    
    if new_releases:
        notify_new_releases(new_releases)
        for r in new_releases:
            rip_download_album(r["id"])
    
    save_known_releases(artist_id, all_releases)


def notify_new_releases(new_releases):
    """Notify about new releases (print to console)."""
    for r in new_releases:
        print(f"New Release: {r['title']} -> {r['link']}")
        # Replace e.g. with:
        # os.system(f'notify-send "New Release: {r["title"]}"')


def deemix_download_album(album_id):
    """Download an album using deemix."""
    command = f"deemix --portable -b 128 -p {MUSIC_PATH}/ https://www.deezer.com/album/{album_id}"
    deemix_download(command)


def deemix_download_playlist(playlist_id):
    """Download a playlist using deemix."""
    command = f"deemix --portable -b 128 -p {MUSIC_PATH}/ https://www.deezer.com/playlist/{playlist_id}"
    deemix_download(command)


def deemix_download_track(track_id):
    """Download a track using deemix."""
    command = f"deemix --portable -b 128 -p {MUSIC_PATH}/ https://www.deezer.com/track/{track_id}"
    deemix_download(command)


def deemix_download(command):
    """Execute deemix download command and log output."""
    with open(DEEMIX_LOG_FILE, "a") as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"\n=== [{timestamp}] Command: {command} ===\n"
        log.write(header)
        print(header.strip())
        
        process = subprocess.Popen(
            command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True
        )
        
        for line in process.stdout:
            print(line, end="")  # Terminal
            log.write(line)  # Logfile


def deemix_download_tracks(tracks):
    """Download multiple tracks using deemix."""
    for t in tracks:
        print(t["title"])
        if DOWNLOAD_ALBUMS_INSTEAD_OF_TRACKS:
            deemix_download_album(t["album"]["id"])
        else:
            deemix_download_track(t["id"])


def rip_download_album(album_id):
    """Download an album using streamrip."""
    command = f"rip --config-path {RIP_CONFIG_FILE} url https://www.deezer.com/album/{album_id}"
    rip_download(command)


def rip_download_playlist(playlist_id):
    """Download a playlist using streamrip."""
    command = f"rip --config-path {RIP_CONFIG_FILE} url https://www.deezer.com/playlist/{playlist_id}"
    rip_download(command)


def rip_download_track(track_id):
    """Download a track using streamrip."""
    command = f"rip --config-path {RIP_CONFIG_FILE} url https://www.deezer.com/track/{track_id}"
    rip_download(command)


def rip_download(command):
    """Execute streamrip download command and log output."""
    with open(RIP_LOG_FILE, "a") as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"\n=== [{timestamp}] Command: {command} ===\n"
        log.write(header)
        print(header.strip())
        
        process = subprocess.Popen(
            command, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True
        )
        
        for line in process.stdout:
            print(line, end="")  # Terminal
            log.write(line)  # Logfile


def rip_download_tracks(tracks):
    """Download multiple tracks using streamrip, checking availability first."""
    with deezer_api.Client() as client:
        for t in tracks:
            if DOWNLOAD_ALBUMS_INSTEAD_OF_TRACKS:
                rate_limiter.wait_if_needed()
                track = client.get_track(t["id"])
                if track.readable:
                    rip_download_album(track.album.id)
                else:
                    print(f"track unavailable - id: {track.id}, title: {track.title}")
            else:
                rip_download_track(t["id"])


def fetch_playlist_meta(playlist_id):
    """Fetch playlist metadata including title and tracks."""
    rate_limiter.wait_if_needed()
    with deezer_api.Client() as client:
        playlist = client.get_playlist(playlist_id)
        tracks = playlist.tracks
        
        # Convert track objects to dictionary format
        track_list = [
            {
                "id": track.id,
                "title": track.title,
                "duration": track.duration,
                "link": track.link,
                "artist": {
                    "name": track.artist.name
                }
            }
            for track in tracks
        ]
        
        return playlist.title, track_list


def generate_m3u_content(playlist_name, tracks):
    """Generate M3U playlist content from track list."""
    lines = ["#EXTM3U"]
    lines.append(f"#PLAYLIST: {playlist_name}")
    
    for t in tracks:
        duration = int(float(t.get("duration", 0)))
        artist = t["artist"]["name"]
        title = t["title"]
        
        # Search for local files
        flac_matches = glob.glob(f"{MUSIC_PATH}/**/*{title}*.flac", recursive=True)
        mp3_matches = glob.glob(f"{MUSIC_PATH}/**/*{title}*.mp3", recursive=True)
        matches = flac_matches + mp3_matches
        
        if matches:
            path = os.path.relpath(matches[0], PLAYLISTS_PATH)
        else:
            # Path not found, use Deezer link
            path = t["link"]
        
        lines.append(f"#EXTINF:{duration},{artist} - {title}")
        lines.append(path)
    
    return "\n".join(lines) + "\n"


def compute_track_hash(tracks):
    """Compute a hash from track list to detect changes."""
    reduced = [
        {
            "id": track["id"],
            "title": track["title"],
            "artist": track["artist"]["name"]
        }
        for track in tracks
    ]
    
    serialized = json.dumps(reduced, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_last_hash(hash_file):
    """Load the last computed hash from file."""
    if os.path.exists(hash_file):
        with open(hash_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def save_hash(hash_file, hash_value):
    """Save hash value to file."""
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(hash_value)


def save_m3u(m3u_file, content):
    """Save M3U playlist content to file."""
    with open(m3u_file, "w", encoding="utf-8") as f:
        f.write(content)


def sanitize_filename(name):
    """Remove invalid characters from filename."""
    return "".join(c for c in name if c.isalnum() or c in " _-").strip()


def extract_playlist(playlist_id):
    """Extract and download a playlist, creating an M3U file."""
    print("Loading playlist metadata")
    playlist_name, tracks = fetch_playlist_meta(playlist_id)
    safe_name = sanitize_filename(playlist_name)
    m3u_file = f"{PLAYLISTS_PATH}/{safe_name}.m3u"
    hash_file = f"{STATE_DIR}/{safe_name}.hash"
    
    print(f"Playlist name: {safe_name}")
    
    current_hash = compute_track_hash(tracks)
    last_hash = load_last_hash(hash_file)
    
    if current_hash == last_hash:
        print("Playlist unchanged - nothing to do")
    else:
        print("Playlist changed - starting download")
        rip_download_tracks(tracks)
        # deemix_download_playlist(playlist_id)
        
        m3u_content = generate_m3u_content(playlist_name, tracks)
        save_m3u(m3u_file, m3u_content)
        save_hash(hash_file, current_hash)
        print(f"Saved playlist: {m3u_file}")


def fetch_all_followed_playlists():
    """Fetch all playlists followed by the user."""
    rate_limiter.wait_if_needed()
    with deezer_api.Client() as client:
        user = client.get_user(USER_ID)
        rate_limiter.wait_if_needed()
        playlists = user.get_playlists()
        return [{"id": p.id, "title": p.title, "link": p.link} for p in playlists]


def extract_all_followed_playlists():
    """Extract all followed playlists."""
    playlists = fetch_all_followed_playlists()
    for r in playlists:
        print(r["title"])
        extract_playlist(r["id"])


def main():
    """Main entry point of the script."""
    ensure_directories()
    find_all_new_releases()
    extract_all_followed_playlists()


if __name__ == "__main__":
    main()

