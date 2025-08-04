import requests
import json
import os
import subprocess
from datetime import datetime
import hashlib
import glob
import shutil

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

def ensure_directories():
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(ARTIST_STATE_DIR, exist_ok=True)
    os.makedirs(MUSIC_PATH, exist_ok=True)
    os.makedirs(PLAYLISTS_PATH, exist_ok=True)
    os.makedirs(RIP_CONFIG_DIR, exist_ok=True)

def fetch_all_followed_artists():
    url = f"https://api.deezer.com/user/{USER_ID}/artists"
    response = requests.get(url)
    data = response.json()
    return [{"id": a["id"], "name": a["name"], "link": a["link"]} for a in data["data"]]

def load_followed_artists():
    if not os.path.exists(FOLLOWED_ARTISTS_FILE):
        return set()
    with open(FOLLOWED_ARTISTS_FILE, "r") as f:
        return json.load(f)

def save_followed_artists(artists):
    with open(FOLLOWED_ARTISTS_FILE, "w") as f:
        json.dump(artists, f, indent=2)

def find_all_new_releases():
    followed_artists = fetch_all_followed_artists()
    for r in followed_artists:
        print(r["name"])
        find_new_releases(r["id"], r["name"])



def fetch_all_releases(artist_id):
    url = f"https://api.deezer.com/artist/{artist_id}/albums"
    response = requests.get(url)
    data = response.json()
    return [{"id": a["id"], "title": a["title"], "link": a["link"]} for a in data["data"]]

def load_known_releases(artist_id):
    if not os.path.exists(f"{ARTIST_STATE_DIR}/{artist_id}.json"):
        return set()
    with open(f"{ARTIST_STATE_DIR}/{artist_id}.json", "r") as f:
        return json.load(f)

def save_known_releases(artist_id, releases):
    with open(f"{ARTIST_STATE_DIR}/{artist_id}.json", "w") as f:
        json.dump(releases, f, indent=2)

def find_new_releases(artist_id, artist_name):
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
    for r in new_releases:
        print(f"Neues Release: {r['title']} -> {r['link']}")
        # Ersetze z. B. mit:
        # os.system(f'notify-send "Neues Release: {r["title"]}"')


def deemix_download_album(album_id):

    command =  f"deemix --portable -b 128 -p {MUSIC_PATH}/ https://www.deezer.com/album/{album_id}"
    deemix_download(command)

def deemix_download_playlist(playlist_id):

    command =  f"deemix --portable -b 128 -p {MUSIC_PATH}/ https://www.deezer.com/playlist/{playlist_id}"
    deemix_download(command)

def deemix_download_track(track_id):

    command =  f"deemix --portable -b 128 -p {MUSIC_PATH}/ https://www.deezer.com/track/{track_id}"
    deemix_download(command)

def deemix_download(command):
    with open(DEEMIX_LOG_FILE , "a") as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"\n=== [{timestamp}] Command: {command} ===\n"
        log.write(header)
        print(header.strip())

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for line in process.stdout:
            print(line, end="")         # Terminal
            log.write(line)             # Logfile

def deemix_download_tracks(tracks):
    for t in tracks:
        print(t["title"])
        if DOWNLOAD_ALBUMS_INSTEAD_OF_TRACKS:
            deemix_download_album(t["album"]["id"])
        else:
            deemix_download_track(t["id"])

def rip_download_album(album_id):

    command =  f"rip --config-path {RIP_CONFIG_FILE} url https://www.deezer.com/album/{album_id}"
    rip_download(command)

def rip_download_playlist(playlist_id):

    command =  f"rip --config-path {RIP_CONFIG_FILE} url https://www.deezer.com/playlist/{playlist_id}"
    rip_download(command)

def rip_download_track(track_id):

    command =  f"rip --config-path {RIP_CONFIG_FILE} url https://www.deezer.com/track/{track_id}"
    rip_download(command)

def rip_download(command):
    with open(RIP_LOG_FILE , "a") as log:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"\n=== [{timestamp}] Command: {command} ===\n"
        log.write(header)
        print(header.strip())

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        for line in process.stdout:
            print(line, end="")         # Terminal
            log.write(line)             # Logfile

def rip_download_tracks(tracks):
    for t in tracks:
        if DOWNLOAD_ALBUMS_INSTEAD_OF_TRACKS:
            url = f"https://api.deezer.com/track/{t["id"]}"
            response = requests.get(url)
            data = response.json()

            if data["readable"]:
                rip_download_album(data["album"]["id"])
            else:
                print(f"track unavailable - url: {url}, title: {data["title"]}")
        else:
            rip_download_track(t["id"])



def fetch_playlist_meta(playlist_id):
    url = f"https://api.deezer.com/playlist/{playlist_id}"
    response = requests.get(url)
    data = response.json()
    if "error" in data:
        raise Exception(f"Fehler beim Laden der Playlist: {data['error']}")
    return data["title"], data["tracks"]["data"]

def generate_m3u_content(playlist_name, tracks):
    lines = ["#EXTM3U"]
    lines.append(f"#PLAYLIST: {playlist_name}")
    for t in tracks:
        duration = int(float(t.get("duration", 0)))
        artist = t["artist"]["name"]
        title = t["title"]
        flac_matches = glob.glob(f"{MUSIC_PATH}/**/*{title}*.flac", recursive=True)
        mp3_matches = glob.glob(f"{MUSIC_PATH}/**/*{title}*.mp3", recursive=True)
        matches = flac_matches + mp3_matches
        if matches:
            path = os.path.relpath(matches[0], PLAYLISTS_PATH)
        else:
            # Path not found
            path = t["link"]
        lines.append(f"#EXTINF:{duration},{artist} - {title}")
        lines.append(path)
    return "\n".join(lines) + "\n"

def compute_track_hash(tracks):
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
    if os.path.exists(hash_file):
        with open(hash_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def save_hash(hash_file, hash_value):
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(hash_value)

def save_m3u(m3u_file, content):
    with open(m3u_file, "w", encoding="utf-8") as f:
        f.write(content)

def sanitize_filename(name):
    # Entfernt ungültige Zeichen für Dateinamen
    return "".join(c for c in name if c.isalnum() or c in " _-").strip()

def extract_playlist(playlist_id):
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
        #deemix_download_playlist(playlist_id)

        m3u_content = generate_m3u_content(playlist_name, tracks)
        save_m3u(m3u_file, m3u_content)
        save_hash(hash_file, current_hash)
        print(f"Saved playlist: {m3u_file}")

def fetch_all_followed_playlists():
    url = f"https://api.deezer.com/user/{USER_ID}/playlists"
    response = requests.get(url)
    data = response.json()
    return [{"id": a["id"], "title": a["title"], "link": a["link"]} for a in data["data"]]

def extract_all_followed_playlists():
    playlists = fetch_all_followed_playlists()
    for r in playlists:
        print(r["title"])
        extract_playlist(r["id"])

def main():
    ensure_directories()
    find_all_new_releases()
    extract_all_followed_playlists()

if __name__ == "__main__":
    main()
