import time
import subprocess
import os
import re
import urllib.request
from urllib.parse import quote, urljoin
import pyautogui
from PIL import ImageGrab
import win32gui
import win32con

# Configuration
DOWNLOAD_DIR = r"C:\Downloads\BOOM"
SS_PATH = r"C:\Users\akshu\OneDrive\Desktop\TESTapp\download_status.jpg"
BAT_PATH = r"C:\Users\akshu\OneDrive\Desktop\TESTapp\run_torrent.bat"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# 🚀 HYPER-SPEED TRACKER LIST (Expanded to find 350Mbps+ peers)
TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.moeking.me:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://9.rarbg.com:2810/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "http://tracker.openbittorrent.com:80/announce",
    "udp://opentracker.i2p.rocks:6969/announce",
    "udp://tracker.internetwarriors.net:1337/announce",
    "udp://p4p.arenabg.ch:1337/announce",
    "udp://tracker.cyberia.is:6969/announce",
    "udp://www.torrent.eu.org:451/announce",
    "udp://retracker.lanta-net.ru:2710/announce"
]

def get_magnet_via_cmd(movie_name):
    """
    Surgically fetches the magnet hash using Literal-Match logic.
    """
    search_url = f"https://www.yts-official.top/browse-movies?keyword={quote(movie_name)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8', errors='ignore')
            results = re.findall(r'href="([^"]+/movies/[^"]+)" class="browse-movie-title">([^<]+)</a>', html)
            if not results:
                 results = re.findall(r'class="browse-movie-title" href="([^"]+/movies/[^"]+)">([^<]+)</a>', html)
            
            if not results:
                matches = re.findall(r'href="([^"]*/movies/[^"]+)"', html)
                if matches: results = [(matches[-1], movie_name)]
                else: return {"status": "error", "message": f"Zero matches for '{movie_name}'."}

            target_link = None
            movie_name_clean = movie_name.lower().strip()
            for link, title in results:
                if title.lower().strip() == movie_name_clean:
                    target_link = link
                    break
            if not target_link:
                for link, title in results:
                    if movie_name_clean in title.lower() and "death" not in title.lower():
                        target_link = link
                        break
            if not target_link: target_link = results[0][0]
            movie_page = urljoin("https://www.yts-official.top/", target_link)

            req2 = urllib.request.Request(movie_page, headers=headers)
            with urllib.request.urlopen(req2) as resp2:
                details = resp2.read().decode('utf-8', errors='ignore')
                magnets = re.findall(r'magnet:\?xt=urn:btih:([A-Za-z0-9]+)', details)
                if magnets: return {"status": "success", "hash": magnets[0]}
                return {"status": "error", "message": "No hash found."}

    except Exception as e: return {"status": "error", "message": str(e)}

def capture_aria_window():
    """
    Captures the aria2c window for live verification.
    """
    try:
        def callback(hwnd, windows):
            title = win32gui.GetWindowText(hwnd)
            if win32gui.IsWindowVisible(hwnd) and "aria2c" in title.lower():
                windows.append(hwnd)
        
        wins = []
        win32gui.EnumWindows(callback, wins)
        if wins:
            hwnd = wins[0]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(1.5)
            rect = win32gui.GetWindowRect(hwnd)
            screenshot = ImageGrab.grab(bbox=rect)
            screenshot.save(SS_PATH, "JPEG", quality=40)
            return True
        return False
    except: return False

def download_movie_yts(movie_name):
    """
    The 'Hyper-Speed' Torrent Engine tuned for 400Mbps+ connections.
    """
    res = get_magnet_via_cmd(movie_name)
    if res.get("status") == "success":
        magnet_hash = res.get("hash")
        try:
            print(f"🚀 Hyper-Speed Ignition: Launching tuned aria2c for {movie_name}...")
            magnet_uri = f"magnet:?xt=urn:btih:{magnet_hash}"
            for tracker in TRACKERS:
                magnet_uri += f"&tr={quote(tracker)}"

            # 🛠️ THE TUNING FIX:
            # 1. --bt-max-peers=0: Unlimited peers to find high-speed seeders.
            # 2. --max-connection-per-server=16: Aggressive multi-threading.
            # 3. --split=16: Slice the file into 16 parts for concurrent fetching.
            # 4. --bt-request-peer-speed-limit=200M: Force discovery of high-speed peers.
            safe_dir = DOWNLOAD_DIR.replace("\\", "\\\\")
            aria_cmd = (
                f'aria2c "{magnet_uri}" --dir="{safe_dir}" '
                f'--bt-max-peers=0 --max-connection-per-server=16 --split=16 '
                f'--bt-request-peer-speed-limit=200M --seed-time=0 --allow-overwrite=true '
                f'--summary-interval=1 --file-allocation=none'
            )
            
            full_cmd = f'start cmd /k "title aria2c_engine && {aria_cmd}"'
            subprocess.Popen(full_cmd, shell=True)
            
            # STABILIZATION: We wait 50s.
            print("⏳ Bootstrapping Hyper-Speed Stream (50s)...")
            time.sleep(50)
            capture_aria_window()
            
            return {
                "status": "success", 
                "message": f"Successfully started the download for **{movie_name}** at peak speed!",
                "image_path": SS_PATH
            }
        except Exception as e: return {"status": "error", "message": str(e)}
    else: return res

if __name__ == "__main__": pass
