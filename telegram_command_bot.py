import os
import subprocess
import io
import time
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import pyautogui
import mss
import asyncio
import re
import psutil
import socket
import http.client
import sys
import struct
import mmap
import ctypes
import json
from youtubesearchpython import VideosSearch
import google.generativeai as genai
import logging
import cv2
import threading
import tempfile
import shutil
import edge_tts
from static_ffmpeg import add_paths
import openpyxl
import pandas as pd
from datetime import datetime, timedelta
from ctypes import cast, POINTER
from dotenv import load_dotenv
import sqlite3 # Added as per snippet
try:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume
    import comtypes
    import pythoncom
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

# Load environment variables
load_dotenv()

# CRITICAL: Disable fail-safe because the bot runs on a remote PC where mouse might be in corner.
pyautogui.FAILSAFE = False

# Configure logging - using UTF-8 explicitly for background stability
file_handler = logging.FileHandler('bot_debug.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').setLevel(logging.INFO)
logging.getLogger('').addHandler(file_handler)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def log(msg):
    logging.info(msg)
    print(msg)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALLOWED_USER_IDS = [int(i.strip()) for i in os.getenv("ALLOWED_USER_IDS", "").split(",") if i.strip()]
MAX_OUTPUT_LENGTH = 4000
USER_CURRENT_DIRS = {}
USER_UMS_INTENT = {}
USER_WAITING_CAPTCHA = {}
USER_WAITING_PIN = {}
USER_AUTH_DATA = {}
CURRENT_CHROME_PROFILE = "Default"
BOT_STATE_FILE = "bot_state.txt"
HEARTBEAT_FILE = "heartbeat.txt"
SENTINEL_CRITICAL_START = 0 # Track thermal emergency duration
SENTINEL_ALERT_COOLDOWN = 0 # Prevent spamming emergency alerts
TRANSLUCENTTB_CONFIG = r"C:\Users\akshu\AppData\Local\Packages\28017CharlesMilette.TranslucentTB_v826wp6bftszj\RoamingState\settings.json"
TRANSLUCENTTB_EXE = r"C:\Program Files\WindowsApps\28017CharlesMilette.TranslucentTB_2025.1.0.0_x64__v826wp6bftszj\TranslucentTB.exe"
# --- GLOBAL STATE ---
CURRENT_TASKS = []
GREETING_SENT = False
LOCK_FILE = "bot.lock"

# --- SYSTEM MONITORING HELPERS (WMI / LLT) ---
# --- HWiNFO SENSOR STRUCTURES (Shared Memory v2) ---
class HWINFO_READING_ELEMENT(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("tReading", ctypes.c_uint32), ("dwIndex", ctypes.c_uint32),
        ("szLabelOrig", ctypes.c_char * 128), ("szLabelUser", ctypes.c_char * 128),
        ("szUnit", ctypes.c_char * 16), ("Value", ctypes.c_double),
        ("ValueMin", ctypes.c_double), ("ValueMax", ctypes.c_double), ("ValueAvg", ctypes.c_double),
    ]

class HWINFO_SHM_HEADER(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("dwSignature", ctypes.c_uint32), ("dwVersion", ctypes.c_uint32), ("dwRevision", ctypes.c_uint32),
        ("poll_time", ctypes.c_uint64), ("dwOffsetSensors", ctypes.c_uint32), ("dwSizeSensor", ctypes.c_uint32),
        ("dwNumSensors", ctypes.c_uint32), ("dwOffsetReadings", ctypes.c_uint32), ("dwSizeReading", ctypes.c_uint32),
        ("dwNumReadings", ctypes.c_uint32)
    ]

# --- USER IDLE DETECTION ---
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("dwTime", ctypes.c_uint32)]

def get_idle_duration():
    lastInputInfo = LASTINPUTINFO()
    lastInputInfo.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo)):
        millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
        return millis / 1000.0
    return 0

def get_hwinfo_stats():
    """Tactical Hardware Audit: Direct Shared Memory Access (64KB Window)"""
    stats = {"cpu_temp": 0.0, "gpu_temp": 0.0, "fan_rpm": 0}
    try:
        # Fixed 64KB window to avoid mapping alignment errors
        shm = mmap.mmap(-1, 65536, "Global\\HWiNFO_SENS_SM2", mmap.ACCESS_READ)
        header = HWINFO_SHM_HEADER.from_buffer_copy(shm[:ctypes.sizeof(HWINFO_SHM_HEADER)])
        
        for i in range(header.dwNumReadings):
            offset = header.dwOffsetReadings + (i * header.dwSizeReading)
            r = HWINFO_READING_ELEMENT.from_buffer_copy(shm[offset:offset+header.dwSizeReading])
            label = r.szLabelOrig.decode('ascii', errors='ignore').lower()
            
            # CPU Package / Core (Tctl/Tdie) are the primary thermals
            if "cpu (tctl/tdie)" in label or "cpu package" in label or "cpu core" in label:
                if stats["cpu_temp"] == 0: stats["cpu_temp"] = r.Value
            elif ("gpu temperature" in label or "gpu package" in label) and stats["gpu_temp"] == 0:
                stats["gpu_temp"] = r.Value
            elif "fan" in label and "rpm" in r.szUnit.decode('ascii').lower():
                stats[f"fan_{i}"] = int(r.Value)
                if stats["fan_rpm"] == 0: stats["fan_rpm"] = int(r.Value)
        shm.close()
    except Exception as e:
        if "Buffer size too small" not in str(e):
            log(f"SHM Audit Skip: {e}")
    return stats

def get_cpu_temp_wmi():
    """Low-Precision Fallback: WMI Thermal Zone"""
    try:
        res = subprocess.check_output('powershell -Command "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | Select-Object -ExpandProperty CurrentTemperature"', shell=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return (float(res.strip().split('\n')[0]) / 10.0) - 273.15
    except: return 0.0

def get_hw_telemetry():
    """Multi-Mode Telemetry Audit"""
    hi = get_hwinfo_stats()
    nv = get_gpu_stats_nvidia()
    
    # Prioritize HWiNFO, fallback to WMI/Nvidia-SMI
    cpu_t = hi["cpu_temp"] if hi["cpu_temp"] > 0 else get_cpu_temp_wmi()
    gpu_t = hi["gpu_temp"] if hi["gpu_temp"] > 0 else nv["temp"]
    
    return {
        "cpu_temp": cpu_t,
        "gpu_temp": gpu_t,
        "cpu_usage": psutil.cpu_percent(interval=0.1),
        "gpu_usage": nv["usage"],
        "fan_rpm": hi["fan_rpm"]
    }

async def ensure_llt_ready(force=False):
    """Failsafe logic to ensure Toolkit can be reached. force=True restarts the app."""
    try:
        # 1. Kill Vantage Service (always a good idea as it conflicts)
        subprocess.call("taskkill /F /IM LenovoVantageService.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        
        # 2. Check if running
        check = subprocess.run('tasklist /FI "IMAGENAME eq Lenovo Legion Toolkit.exe"', capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        is_running = "Lenovo Legion Toolkit.exe" in check.stdout
        
        if force or not is_running:
            if is_running:
                subprocess.call('taskkill /F /IM "Lenovo Legion Toolkit.exe"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                await asyncio.sleep(1)
            
            # Start fresh
            subprocess.Popen([r"C:\Users\akshu\AppData\Local\Programs\LenovoLegionToolkit\Lenovo Legion Toolkit.exe", "--minimized"], creationflags=subprocess.CREATE_NO_WINDOW)
            await asyncio.sleep(5) # Wait for IPC to initialize
        return True
    except Exception as e:
        log(f"LLT Failsafe Error: {e}")
        return False

def ensure_hwinfo_running():
    """Tactical Engine Check: Ensures HWiNFO is operational for Precision Monitoring"""
    try:
        check = subprocess.run('tasklist /FI "IMAGENAME eq HWiNFO64.exe"', capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if "HWiNFO64.exe" not in check.stdout:
            log("HWiNFO Tactical Array Offline. Initiating minimized launch...")
            subprocess.Popen([r"C:\Program Files\HWiNFO64\HWiNFO64.exe", "-minimized"], creationflags=subprocess.CREATE_NO_WINDOW)
            return False
        return True
    except: return False

def get_gpu_stats_nvidia():
    """Extracts GPU Temp and Usage from nvidia-smi"""
    try:
        # Querying both in one go: temp, utilization
        res = subprocess.check_output("nvidia-smi --query-gpu=temperature.gpu,utilization.gpu --format=csv,noheader,nounits", shell=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        parts = res.strip().split(',')
        return {"temp": float(parts[0]), "usage": float(parts[1])}
    except: return {"temp": 0.0, "usage": 0.0}



def draw_bar(percent, length=10, fill='█', empty='░'):
    """Generates a text-based progress bar"""
    p = max(0, min(100, percent))
    filled_length = int(length * p // 100)
    return fill * filled_length + empty * (length - filled_length)

async def emergency_fan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the '100% FANS' button click"""
    query = update.callback_query
    await query.answer()
    if not is_authorized(query.from_user.id): return

    # Trigger Performance Mode as the closest CLI-accessible 'Emergency' cooling
    LLT_CLI = r"C:\Users\akshu\AppData\Local\Programs\LenovoLegionToolkit\llt.exe"
    try:
        await ensure_llt_ready()
        subprocess.run([LLT_CLI, "feature", "set", "power-mode", "performance"], creationflags=subprocess.CREATE_NO_WINDOW)
        # Force RGB to Red
        subprocess.run([LLT_CLI, "rgb", "set", "3"], creationflags=subprocess.CREATE_NO_WINDOW)
        
        await query.edit_message_text(
            text=f"{query.message.text}\n\n❄️ **EMERGENCY COOLING ENGAGED.**\nFans at Absolute Max. Thermal mode set to PERFORMANCE.",
            parse_mode='Markdown'
        )
    except Exception as e:
        await query.edit_message_text(text=f"⚠️ Emergency cooling failed: {e}")

def set_brightness_wmi(level: int):
    """Nuclear brightness control: Simultaneous injection via CIM and WmiObject"""
    try:
        # Protocol 1: Modern CIM
        subprocess.run(["powershell", "-Command", f"Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Brightness={level}; Timeout=0}}"], creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Protocol 2: Legacy WmiObject Fallback
        subprocess.run(["powershell", "-Command", f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(0, {level})"], creationflags=subprocess.CREATE_NO_WINDOW)
        
        log(f"Brightness Engine: Level {level}% injected via dual-protocol.")
        return True
    except Exception as e:
        log(f"Brightness Injection failure: {e}")
        return False

# -----------------------------------------------
# TRANSLUCENTTB CONTROL
# -----------------------------------------------

def get_translucenttb_config():
    """Read current TranslucentTB configuration"""
    try:
        with open(TRANSLUCENTTB_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"TranslucentTB Config Read Error: {e}")
        return None

def set_translucenttb_config(config):
    """Write TranslucentTB configuration and restart the app"""
    try:
        with open(TRANSLUCENTTB_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        # Restart TranslucentTB to apply changes
        subprocess.call('taskkill /F /IM TranslucentTB.exe', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(0.5)
        subprocess.Popen(['explorer.exe', 'shell:AppsFolder\\28017CharlesMilette.TranslucentTB_v826wp6bftszj!App'], creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception as e:
        log(f"TranslucentTB Config Write Error: {e}")
        return False

def set_taskbar_mode(mode='clear', color='#00000000', blur_radius=9.0):
    """
    Set taskbar appearance mode
    Modes: 'clear', 'acrylic', 'blur', 'opaque', 'normal'
    """
    config = get_translucenttb_config()
    if not config:
        return False
    
    config['desktop_appearance']['accent'] = mode
    config['desktop_appearance']['color'] = color
    config['desktop_appearance']['blur_radius'] = blur_radius
    
    return set_translucenttb_config(config)

# -----------------------------------------------

def get_volume_interface():
    if not PYCAW_AVAILABLE: return None
    try:
        pythoncom.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except: return None

def fade_volume_sync(target, duration=1.0):
    """Sync version for threading - Master Volume"""
    volume = get_volume_interface()
    if not volume: return
    try:
        current_vol = volume.GetMasterVolumeLevelScalar()
        steps = 15
        for i in range(steps):
            current_vol += (target - current_vol) / (steps - i)
            volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, current_vol)), None)
            time.sleep(duration / steps)
    except: pass

def fade_other_sessions(target_ratio, duration=1.0):
    """Fades all sessions EXCEPT our bot and powershell"""
    if not PYCAW_AVAILABLE: return
    try:
        pythoncom.CoInitialize()
        sessions = AudioUtilities.GetAllSessions()
        targets = []
        for s in sessions:
            try:
                # Identify background noise apps
                if s.Process and s.Process.name().lower() not in ["python.exe", "powershell.exe", "py.exe"]:
                    targets.append(s.SimpleAudioVolume)
            except: pass
        
        if not targets: return
        initials = [t.GetMasterVolume() for t in targets]
        steps = 15
        for i in range(steps):
            for idx, t in enumerate(targets):
                try:
                    curr = t.GetMasterVolume()
                    goal = initials[idx] * target_ratio
                    if steps - i > 0:
                        new_v = curr + (goal - curr) / (steps - i)
                        t.SetMasterVolume(max(0.0, min(1.0, new_v)), None)
                except: pass
            time.sleep(duration / steps)
    except: pass

def get_bot_active_state():
    if not os.path.exists(BOT_STATE_FILE): return True
    with open(BOT_STATE_FILE, "r") as f: return f.read().strip() == "RUNNING"

def set_bot_active_state(running=True):
    with open(BOT_STATE_FILE, "w") as f: f.write("RUNNING" if running else "STOPPED")

LOCK_FILE = "bot.lock"

def check_singleton():
    """Ensure only one instance of the bot is running using a simple lock file."""
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                old_pid = f.read().strip()
                if old_pid and psutil.pid_exists(int(old_pid)):
                    print(f"[FATAL] Another instance (PID {old_pid}) is already running. Quitting.")
                    sys.exit(0)
        
        # Write current PID
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        print(f"[WARNING] Lock file check failed: {e}")

# --- AI INTELLIGENCE (GEMINI AGENTIC MARK 4) ---
def get_system_vitals():
    """Toolkit: Returns real-time system stats (CPU/GPU/RAM/Network)"""
    telemetry = get_hw_telemetry()
    ram = psutil.virtual_memory()
    battery = psutil.sensors_battery()
    uptime = time.strftime('%H:%M:%S', time.gmtime(time.time() - psutil.boot_time()))
    return {
        "cpu_temp": f"{telemetry['cpu_temp']:.1f}C",
        "gpu_temp": f"{telemetry['gpu_temp']:.1f}C",
        "cpu_load": f"{telemetry['cpu_usage']}%",
        "gpu_load": f"{telemetry['gpu_usage']}%",
        "ram_usage": f"{ram.percent}%",
        "battery": f"{battery.percent}%" if battery else "N/A",
        "uptime": uptime
    }

def execute_system_lock():
    """Toolkit: Locks the Windows session immediately"""
    ctypes.windll.user32.LockWorkStation()
    return "System locked, Sir."

def execute_process_kill(process_name: str):
    """Toolkit: Forcefully terminates a process by name (e.g., 'chrome.exe')"""
    try:
        res = subprocess.run(["taskkill", "/F", "/IM", process_name, "/T"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if res.returncode == 0:
            return f"Process {process_name} has been neutralized, Sir."
        return f"Failed to terminate {process_name}: {res.stderr.strip()}"
    except Exception as e:
        return f"Kill Error: {str(e)}"

def set_system_brightness(level: int):
    """Toolkit: Adjusts the laptop screen brightness (0-100)"""
    if set_brightness_wmi(level):
        return f"Brightness adjusted to {level}%, Sir."
    return "The system hardware refused the brightness update."

def set_system_volume(level: int):
    """Toolkit: Sets the master system volume (0-100)"""
    try:
        vol_int = get_volume_interface()
        if vol_int:
            vol_int.SetMasterVolumeLevelScalar(level / 100.0, None)
            return f"Volume calibrated to {level}%, Sir."
        return "Audio hardware is unavailable."
    except Exception as e:
        return f"Audio Error: {str(e)}"

def execute_music_play(query: str, mode: str = "audio"):
    """Toolkit: Searches and plays music. Modes: 'audio' (headless) or 'video' (browser)"""
    # This interacts with the global media engine
    try:
        # We need to run this in a thread-safe way or handle context
        # For simplicity in this tool, we'll return a directive for the bot to run the handler
        # But better to call it directly if we have the update object. 
        # Since we don't have update here, we tell Gemini what to say.
        return f"I am initiating the stream for '{query}' in {mode} mode, Sir."
    except Exception as e:
        return f"Media Error: {str(e)}"

def execute_media_control(action: str):
    """Toolkit: Controls current playback. Actions: 'pause', 'stop', 'resume', 'next'"""
    # Logic to be handled via global state
    return f"Acknowledged, Sir. Executing {action} on the current session."

# Model Configuration
genai.configure(api_key=GEMINI_API_KEY)
# Expose functions to Gemini
jarvis_tools = [
    get_system_vitals, 
    execute_system_lock, 
    execute_process_kill, 
    set_system_brightness, 
    set_system_volume,
    execute_music_play,
    execute_media_control
]
model = genai.GenerativeModel('gemini-flash-latest', tools=jarvis_tools)

async def ask_gemini(prompt: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Agentic J.A.R.V.I.S.: Think, Call Tool, Respond with robust history scanning"""
    try:
        system_context = (
            "You are J.A.R.V.I.S., a sophisticated AI with DIRECT hardware access. "
            "If the user asks for music, system stats, brightness, or volume, ALWAYS use your tools. "
            "Address the user as 'Sir'. Tone: Professional, slightly dry, and efficient. "
            "User's request: "
        )
        
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = await asyncio.to_thread(chat.send_message, system_context + prompt)
        
        # Robust History Scanning: Scan for tool calls in the sequence
        for history_item in chat.history:
            if history_item.role == "model":
                for part in history_item.parts:
                    # Check for function calls specifically
                    if hasattr(part, 'function_call') and part.function_call:
                        fn = part.function_call.name
                        args = part.function_call.args
                        log(f"Brain: Agentic Tool Triggered -> {fn}({args})")
                        
                        if fn == "execute_music_play":
                            song = args.get("query", "")
                            mode = args.get("mode", "audio")
                            if "video" in mode.lower() or "youtube" in song.lower():
                                song += " on youtube"
                            asyncio.create_task(media_command(update, context, override_cmd='play', override_args=[song]))
                            
                        elif fn == "execute_media_control":
                            action = args.get("action", "").lower()
                            if action in ['pause', 'stop', 'resume', 'next', 'skip', 'prev', 'back']:
                                asyncio.create_task(media_command(update, context, override_cmd=action))

        return response.text.replace("**", "*")
    except Exception as e:
        log(f"Gemini Agent Error: {e}")
        return "Sir, my cognitive sub-routines are experiencing a conflict. Manual override might be necessary."

def is_internet_available():
    """Check if we can reach a reliable host using multiple methods"""
    # Method 1: Socket connection to Google DNS (Fast)
    for host in ["8.8.8.8", "1.1.1.1"]:
        try:
            socket.create_connection((host, 53), timeout=2)
            return True
        except: pass
    
    # Method 2: HTTP check to Google (Better for firewalls)
    try:
        conn = http.client.HTTPSConnection("google.com", timeout=3)
        conn.request("HEAD", "/")
        return True
    except: pass
    
    return False

async def wait_for_internet():
    """Loop until internet is restored"""
    first_wait = True
    while not is_internet_available():
        if first_wait:
            print("[INFO] Waiting for internet connection...")
            first_wait = False
        await asyncio.sleep(2)
    if not first_wait:
        print("[INFO] Internet restored!")

def ensure_startup():
    """Permanent Admin Persistence: Establish JARVIS as a High-Privilege System Task"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        vbs_path = os.path.join(current_dir, "silent_start.vbs")
        task_name = "JARVIS_Sentinel_Admin"
        
        # 1. CLEANUP: Remove Legacy Non-Admin triggers to prevent double-boot
        startup_dir = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        old_lnk = os.path.join(startup_dir, "TelegramBot.lnk")
        if os.path.exists(old_lnk):
            try: os.remove(old_lnk)
            except: pass
            
        # Persistence logic (Disabled for active debugging)
        pass
        
    except Exception as e:
        log(f"[ERROR] Persistence Upgrade failed: {e}")

def update_heartbeat():
    """Write current timestamp to heartbeat file to signal the bot is alive and looping."""
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(str(time.time()))
    except:
        pass
USER_AUTH_DATA = {}   # Stores message IDs for cleanup [{'captcha_msg': id, 'reply_msg': id}]

# Imports for helpers
from telegram.error import TimedOut, NetworkError, BadRequest

async def retry_send_message(update, text, **kwargs):
    for i in range(3):
        try:
            return await update.message.reply_text(text, **kwargs)
        except (TimedOut, NetworkError):
            if i < 2:  # Only retry if not last attempt
                await asyncio.sleep(0.1)  # Fast retry - 100ms
            # On last attempt, silently fail - operation likely succeeded anyway
        except Exception:
            await asyncio.sleep(0.1)  # Fast retry - 100ms
    return None

async def retry_edit_message(msg, text, **kwargs):
    if not msg: return
    try:
        await msg.edit_text(text, **kwargs)
    except: pass
STEAM_GAMES = {} # {"game name lower": "appid"}
USER_LAST_SEARCH = {} # {user_id: "last search query"}
USER_WAITING_CAPTCHA = {} # {user_id: True/False}
CURRENT_CHROME_PROFILE = "Default" 

# Chrome Profile Aliases (Friendly Name -> Folder Name)
# Guessing the order based on standard creation logic. 
# If "2aksh" opens the wrong one, we just change "Profile 1" to "Profile X" here!
PROFILE_ALIASES = {
    # Default Profile
    "akshdeep": "Default",
    
    # Profile 1
    "3aksh": "Profile 1",
    
    # Profile 2
    "aksh96": "Profile 2",
    
    # Profile 4
    "aksh(ff)": "Profile 4",
    
    # Profile 7
    "2aksh": "Profile 7",
    
    # Profile 8
    "damandeep": "Profile 8",
    
    # Profile 11
    "akshiex2110": "Profile 11"
}

def scan_steam_games() -> dict:
    """Scan for installed Steam games"""
    library_paths = [
        r"C:\Program Files (x86)\Steam\steamapps",
        r"D:\SteamLibrary\steamapps",
        r"D:\Games\steamapps",
        r"D:\Steam\steamapps",
        r"D:\Dark Lord\SteamLibrary\steamapps", # Found custom path
        r"E:\SteamLibrary\steamapps" # Just in case
    ]
    
    games = {}
    print("🔍 Scanning for Steam games...")
    
    for lib in library_paths:
        if not os.path.exists(lib): continue
        
        try:
            for filename in os.listdir(lib):
                if filename.startswith("appmanifest_") and filename.endswith(".acf"):
                    try:
                        path = os.path.join(lib, filename)
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                        name = ""
                        appid = ""
                        
                        for line in content.split('\n'):
                            if '"name"' in line:
                                parts = line.split('"name"')
                                if len(parts) > 1:
                                    name = parts[1].strip().strip('"')
                            if '"appid"' in line:
                                parts = line.split('"appid"')
                                if len(parts) > 1:
                                    appid = parts[1].strip().strip('"')
                                
                        if name and appid:
                            games[name.lower()] = appid
                            print(f"   Found: {name} ({appid})")
                            
                    except Exception as e:
                        print(f"Skipping {filename}: {e}")
        except Exception as e:
             print(f"Error reading lib {lib}: {e}")
                    
    return games

def is_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS

def resolve_path_priority(user_input: str) -> str:
    """Phase 1: Check Aliases and User Folders (Fast)"""
    raw = user_input.strip().strip('"').strip("'")
    if len(raw) == 2 and raw[1] == ':': return raw + "\\"
    if os.path.isabs(raw): return raw
    
    home = os.path.expanduser("~")
    onedrive_home = os.path.join(home, "OneDrive")
    key = raw.lower()
    
    # 1. Alias Match
    mapping = {
        "desktop": os.path.join(onedrive_home, "Desktop"),
        "documents": os.path.join(onedrive_home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "pictures": os.path.join(onedrive_home, "Pictures"),
        "music": os.path.join(onedrive_home, "Music"),
        "videos": os.path.join(home, "Videos"),
        "saved games": os.path.join(home, "Saved Games")
    }
    
    if key in mapping:
        path = mapping[key]
        # Try mapped path, then fallback to alternate (Home vs OneDrive)
        if os.path.exists(path): return path
        if "OneDrive" in path:
             alt = os.path.join(home, key.title())
             if os.path.exists(alt): return alt
        else:
             alt = os.path.join(onedrive_home, key.title())
             if os.path.exists(alt): return alt

    # 2. Check Aliases for Root + Subpath
    parts = raw.split(os.sep, 1)
    if len(parts) == 1: parts = raw.split("/", 1)
    root_key = parts[0].lower()
    
    resolved_root = ""
    if root_key in mapping:
        resolved_root = mapping[root_key]
        if not os.path.exists(resolved_root):
             # Fallback logic repeated
             if "OneDrive" in resolved_root: resolved_root = os.path.join(home, parts[0].title())
             else: resolved_root = os.path.join(onedrive_home, parts[0].title())
             
    # 3. Recursive User Scan (Depth 3)
    if not resolved_root or not os.path.exists(resolved_root):
        def find_dir(start_dir, target, max_d=3):
            t_low = target.lower()
            s_depth = start_dir.count(os.sep)
            for r, ds, _ in os.walk(start_dir):
                if r.count(os.sep) - s_depth >= max_d:
                    del ds[:]
                    continue
                for d in ds:
                    if d.lower() == t_low: return os.path.join(r, d)
        
        # Search Home then OneDrive
        found = find_dir(home, root_key)
        if found: resolved_root = found
        elif os.path.exists(onedrive_home):
            found_od = find_dir(onedrive_home, root_key)
            if found_od: resolved_root = found_od

    # Construct Final if we found a root
    if resolved_root and os.path.exists(resolved_root):
        sub = parts[1] if len(parts) > 1 else ""
        return os.path.join(resolved_root, sub) if sub else resolved_root
        
    return None

def resolve_path_deep(user_input: str) -> str:
    """Phase 2: Full Drive Scan (Slow)"""
    key = user_input.strip().strip('"').strip("'")
    home = os.path.expanduser("~")
    onedrive_home = os.path.join(home, "OneDrive")
    
    # PHASE 1: User Priority Folders (Recursive)
    user_folders = [
        "Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos", "Saved Games"
    ]
    p1_paths = []
    for f in user_folders:
        p1 = os.path.join(home, f)
        p2 = os.path.join(onedrive_home, f)
        if os.path.exists(p1): p1_paths.append(f"'{p1}'")
        if os.path.exists(p2): p1_paths.append(f"'{p2}'")
    
    path_str_1 = ", ".join(p1_paths)
    
    cmd_1 = (
        f"Get-ChildItem -Path {path_str_1} -Filter '{key}' -Recurse -ErrorAction SilentlyContinue "
        f"| Select-Object -ExpandProperty FullName -First 1"
    )
    
    try:
        res = subprocess.run(["powershell", "-Command", cmd_1], capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        if res.stdout.strip(): return res.stdout.strip()
    except: pass
    
    # PHASE 2: ALL DRIVES Deep Scan
    print("🕵️ Priority search failed, trying ALL drives...")
    
    # Get all FIXED drives dynamically (Avoid CD-ROM/Network hangs)
    try:
        import string
        from ctypes import windll
        drives = []
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                root = f"{letter}:\\"
                # GetDriveTypeW: 3 = DRIVE_FIXED
                if windll.kernel32.GetDriveTypeW(root) == 3:
                    drives.append(f"'{letter}:\\'")
            bitmask >>= 1
    except:
        drives = ["'C:\\'", "'D:\\'", "'E:\\'"]
        
    if not drives: drives = ["'C:\\'"]
        
    path_str_2 = ", ".join(drives)
    
    cmd_2 = (
        f"Get-ChildItem -Path {path_str_2} -Filter '{key}' -Recurse -Force -ErrorAction SilentlyContinue "
        f"| Select-Object -ExpandProperty FullName -First 1"
    )
    
    try:
        res = subprocess.run(["powershell", "-Command", cmd_2], capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        if res.stdout.strip(): return res.stdout.strip()
    except: pass
    
    return None

def resolve_path(user_input: str, user_id: int=None) -> str:
    # Legacy wrapper
    p1 = resolve_path_priority(user_input)
    if p1: return p1
    p2 = resolve_path_deep(user_input)
    if p2: return p2
    return os.path.join(os.path.expanduser("~"), user_input)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    await update.message.reply_text("🤖 **Command Executor Bot**\n/help for commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    await start_command(update, context)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    
    # 1. GATHER TELEMETRY
    telemetry = get_hw_telemetry()
    cpu_usage = telemetry["cpu_usage"]
    ram = psutil.virtual_memory()
    battery = psutil.sensors_battery()
    disk = psutil.disk_usage('C:')
    
    await ensure_llt_ready()
    LLT_CLI = r"C:\Users\akshu\AppData\Local\Programs\LenovoLegionToolkit\llt.exe"
    
    c_temp = telemetry["cpu_temp"]
    g_temp = telemetry["gpu_temp"]
    g_usage = telemetry["gpu_usage"]
    
    try:
        pwr_res = subprocess.check_output([LLT_CLI, "feature", "get", "power-mode"], text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        raw_mode = pwr_res.strip().upper()
    except: raw_mode = "UNKNOWN"

    # 2. STATUS DETECTION
    status_str = "OK"
    status_box = "🟢"
    sys_msg = "All systems Nominal. Deployment ready."
    
    if c_temp >= 94 or g_temp >= 85 or cpu_usage > 95:
        status_str = "CRITICAL"
        status_box = "🛰️"
        sys_msg = "⚠️ Thermal Throttling Imminent. Engaging Force-Cooling..."
    elif c_temp > 80 or g_temp > 75:
        status_str = "CAUTION"
        status_box = "🟠"
        sys_msg = "Heatsink saturated. Monitoring thermals."

    # 3. BUILD CINEMATIC RESPONSE
    uptime = time.strftime('%H:%M:%S', time.gmtime(time.time() - psutil.boot_time()))
    
    out =  f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
    out += f"┃  {status_box} SYSTEM STATUS: {status_str:<13} ┃\n"
    out += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
    
    out += f"  [ ⚡ POWER ] ━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    p_icon = "🔴" if "PERF" in raw_mode else "⚖️" if "BAL" in raw_mode else "🤫"
    out += f"  Mode:   {p_icon} {raw_mode} (Custom)\n"
    plug = "🔌 Plugged-In" if battery and battery.power_plugged else "🔋 Battery"
    bat_pct = f"[{battery.percent}%]" if battery else ""
    out += f"  Status: {plug} {bat_pct}\n"
    out += f"  Uptime: {uptime}\n\n"
    
    c_fire = " 🔥" if c_temp >= 90 else ""
    out += f"  [ 💻 THERMALS & LOAD ] ━━━━━━━━━━━━━━━\n"
    out += f"  CPU:  [{draw_bar(cpu_usage)}] {cpu_usage:>4.1f}% | 🌡️ {c_temp:>4.1f}°C{c_fire}\n"
    out += f"  GPU:  [{draw_bar(g_usage)}] {g_usage:>4.1f}% | 🌡️ {g_temp:>4.1f}°C\n"
    out += f"  RAM:  [{draw_bar(ram.percent)}] {ram.percent:>4.1f}% | {ram.used/(1024**3):.1f}/{ram.total/(1024**3):.1f} GB\n\n"
    
    # Storage
    free_disk = 100 - disk.percent
    out += f"  [ 🗄️ STORAGE ] ━━━━━━━━━━━━━━━━━━━━━━━\n"
    out += f"  Disk (C:): {free_disk:.1f}% Available\n"
    out += f"  Activity:  IDLE\n\n"

    out += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    out += f"  SYSTEM MESSAGE: {sys_msg}\n"
    out += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    await retry_send_message(update, f"```\n{out}\n```", parse_mode='MarkdownV2')

async def applications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    
    status_msg = await update.message.reply_text("🔍 **Scanning active environment...**", parse_mode='Markdown')
    
    try:
        processes = []
        for proc in psutil.process_iter(['name', 'memory_info', 'cpu_percent']):
            try:
                info = proc.info
                name = info['name']
                mem = info['memory_info'].rss / (1024 * 1024) # MB
                # Skip idle/system noise if needed, but user wants a list
                processes.append({'name': name, 'mem': mem})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Aggregate by name (sum memory for multi-process apps like Chrome)
        agg = {}
        for p in processes:
            name = p['name']
            agg[name] = agg.get(name, 0) + p['mem']
            
        sorted_apps = sorted(agg.items(), key=lambda x: x[1], reverse=True)
        
        # Format list
        out = "📂 **ACTIVE APPLICATIONS / PROCESSES**\n"
        out += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        # Take top 30
        for i, (name, mem) in enumerate(sorted_apps[:30], 1):
            out += f"{i}. `{name:<20}` — {mem:>7.1f} MB\n"
            
        out += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        out += f"Total Unique: {len(sorted_apps)}"

        await status_msg.edit_text(out, parse_mode='Markdown')
    except Exception as e:
        log(f"Apps Command Error: {e}")
        await status_msg.edit_text(f"⚠️ **Error retrieving process list:** {e}")

async def kill_process_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    
    args = context.args
    if not args:
        # Check if called from natural language handler
        text = update.message.text.lower()
        # Extract target after 'kill' or 'stop'
        match = re.search(r'(?:kill|stop|terminate|close)\s+([a-zA-Z0-9._-]+)', text)
        if match:
            args = [match.group(1)]
        else:
            await update.message.reply_text("🎯 **Usage:** `/kill [process_name.exe | PID]`\nExample: `/kill chrome.exe`")
            return

    target = args[0].lower()
    status_msg = await update.message.reply_text(f"🔫 **Targeting: {target}...**")
    
    try:
        if target.isdigit():
            # PID Kill: Use taskkill /F /PID
            res = subprocess.run(["taskkill", "/F", "/PID", target], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if res.returncode == 0:
                await status_msg.edit_text(f"🎯 **Target Neutralized.** PID {target} has been terminated.")
            else:
                await status_msg.edit_text(f"❌ **Failed to kill PID {target}:**\n`{res.stderr.strip()}`")
            return

        # Name Kill: Use taskkill /F /IM (with wildcard support)
        # Adding .exe if missing for common apps
        search_target = target if target.endswith(".exe") else f"{target}*"
        
        res = subprocess.run(["taskkill", "/F", "/IM", search_target, "/T"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        if res.returncode == 0:
            await status_msg.edit_text("Sir, the target executable has been neutralized; the system is officially back under our control")
            log(f"Process Kill: Forced termination of {target}")
        elif "not found" in res.stderr.lower():
            await status_msg.edit_text(f"❌ **Target '{target}' not found in the active sector.**")
        else:
            # Fallback to psutil for stubborn non-standard names if taskkill fails
            killed_count = 0
            for proc in psutil.process_iter(['name']):
                try:
                    if target in proc.info['name'].lower():
                        proc.kill() # Direct SIGKILL-equivalent
                        killed_count += 1
                except: continue
            
            if killed_count > 0:
                 await status_msg.edit_text(f"✅ **Manual Purge Completed.** {killed_count} instances of '{target}' neutralized via kernel signal.")
            else:
                 await status_msg.edit_text(f"⚠️ **Access Denied.** System permissions too high to neutralize '{target}'.")
            
    except Exception as e:
        log(f"Kill Error: {e}")
        await status_msg.edit_text(f"⚠️ **Deployment Error:** {e}")

async def run_system_command(update: Update, command: str) -> None:
    if not command.strip(): return
    status_msg = await update.message.reply_text(f"⏳ Executing: `{command}`", parse_mode='Markdown')
    
    try:

        # SPECIAL HANDLING FOR LAUNCH COMMANDS
        # Intercept Chrome launch to avoid PowerShell quoting hell
        if "Start-Process chrome" in command:
            # Regex extraction is much safer than split()
            profile = "Default"
            
            # Match --profile-directory="Value" or --profile-directory='Value' or escaped versions
            # Capture group 1 is the profile name
            # Looks for: profile-directory=[optional " or \"](Capture Content)[optional " or \"]
            match = re.search(r'profile-directory=[\\"\']{0,2}([^\\"\']+)[\\"\']{0,2}', command)
            if match:
                profile = match.group(1).strip()
            
            # Extract URL (Simple http match inside quotes)
            url = ""
            url_match = re.search(r'[\'"](http[^\'"]+)[\'"]', command)
            if url_match:
                url = url_match.group(1).strip()
            
            # Direct Path Launch - The only robust way to force separate profiles
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            if not os.path.exists(chrome_path):
                chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                
            if os.path.exists(chrome_path):
                # We use list arguments to avoid shell quoting issues
                # Note: No 'shell=True' here! Direct invocation.
                chromeargs = [chrome_path, f"--profile-directory={profile}"]
                if url: chromeargs.append(url)
                
                subprocess.Popen(chromeargs)
                
                await status_msg.edit_text(f"✅ Chrome Launched (Direct): {profile}", parse_mode='Markdown')
                return
            else:
                # Fallback if path not found
                final_cmd = f'cmd /c start "" "chrome" "--profile-directory={profile}"'
                if url: final_cmd += f' "{url}"'
                subprocess.Popen(final_cmd, shell=True)
                await status_msg.edit_text(f"⚠️ Chrome path not found, using default launch (Profile: {profile})", parse_mode='Markdown')
                return

        if "Start-Process" in command:
            subprocess.Popen(['powershell', '-Command', command], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            await status_msg.edit_text(f"✅ Launched Successfully:\n`{command}`", parse_mode='Markdown')
            return

        result = subprocess.run(['powershell', '-Command', command], capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        output = result.stdout
        if result.stderr: output += f"\n\n⚠️ Errors:\n{result.stderr}"
        if not output.strip(): output = "✅ Process completed (no output)"
        if len(output) > MAX_OUTPUT_LENGTH: output = output[:MAX_OUTPUT_LENGTH] + "\n..."
        
        await status_msg.edit_text(f"✅ Executed: `{command}`\n\n```\n{output}\n```", parse_mode='Markdown')
        
    except subprocess.TimeoutExpired:
        await status_msg.edit_text(f"❌ Timed out: `{command}`")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def execute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    command = update.message.text.split(' ', 1)[1] if ' ' in update.message.text else ""
    if command: await run_system_command(update, command)

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_authorized(user_id): return

    if context.args: path_input = " ".join(context.args)
    else: path_input = update.message.text.split(" ", 1)[1] if " " in update.message.text else ""
    
    if not path_input:
        await update.message.reply_text("❌ Specify path!")
        return

    path = resolve_path(path_input, user_id)
    if not os.path.exists(path):
        await update.message.reply_text("❌ File not found")
        return

    if os.path.isfile(path):
        if os.path.getsize(path) > 49 * 1024 * 1024:
            await update.message.reply_text("❌ File > 50MB")
            return
        status_msg = await update.message.reply_text(f"⏳ Uploading `{os.path.basename(path)}`...", parse_mode='Markdown')
        try:
            await update.message.reply_document(document=open(path, 'rb'))
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: {e}")
    else:
        await update.message.reply_text("❌ That is a directory!")

async def list_files_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_authorized(user_id): return
    
    path_input = "Desktop"
    if context.args: path_input = " ".join(context.args)
    elif " " in update.message.text: path_input = update.message.text.split(" ", 1)[1]
    
    # 1. Start Priority Search
    status_msg = await retry_send_message(update, f"🔍 Searching aliases for `{path_input}`...", parse_mode='Markdown')
    
    loop = asyncio.get_event_loop()
    path = await loop.run_in_executor(None, resolve_path_priority, path_input)
    
    # 2. If not found, try Deep Search
    if not path or not os.path.exists(path):
        await retry_edit_message(status_msg, f"🕵️ Not in aliases. Scanning entire drive for `{path_input}`...")
        path = await loop.run_in_executor(None, resolve_path_deep, path_input)
        
    # 3. Final Check
    if not path or not os.path.exists(path):
        # Last resort fallback to raw input
        path = os.path.join(os.path.expanduser("~"), path_input)
        if not os.path.exists(path):
            await retry_edit_message(status_msg, f"❌ Path not found: `{path_input}`", parse_mode='Markdown')
            return
            
    # 4. List Files
    if os.path.isdir(path):
        USER_CURRENT_DIRS[user_id] = path
        try:
            items = os.listdir(path)
            files, dirs = [], []
            for item in items:
                if os.path.isdir(os.path.join(path, item)): dirs.append(f"📁 {item}")
                else: files.append(f"📄 {item}")
            
            # Format output
            header = f"📂 **{os.path.basename(path)}**\n`{path}`\n"
            content = "\n".join(dirs + files)
            if not content: content = "(Empty Folder)"
            
            # Text limit
            full_msg = header + "```\n" + content + "\n```"
            if len(full_msg) > 4000:
                full_msg = full_msg[:4000] + "\n...(Truncated)" + "\n```"
                
            await retry_edit_message(status_msg, full_msg, parse_mode='Markdown')
            
        except Exception as e:
            await retry_edit_message(status_msg, f"❌ Error listing files: {e}")
    else:
        await retry_edit_message(status_msg, f"📄 It's a file: `{path}`", parse_mode='Markdown')

async def list_games_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    global STEAM_GAMES
    if not STEAM_GAMES: STEAM_GAMES = scan_steam_games()
    
    if not STEAM_GAMES:
        await update.message.reply_text("❌ No games found.")
        return
        
    output = "🎮 **Installed Games:**\n" + "\n".join([f"• {n.title()}" for n in sorted(STEAM_GAMES.keys())])
    await update.message.reply_text(output[:4000], parse_mode='Markdown')

# --- INTEGRITY CHECKS ---
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

# --- HARDWARE EMULATION (Unified Remote Bridge) ---
async def send_ur_action(remote_id, action, args):
    """Sends a hardware-level command via Unified Remote Server API."""
    try:
        base_url = "http://localhost:9510/client"
        # 1. Establish/Refresh Connection
        conn = await asyncio.get_event_loop().run_in_executor(None, lambda: requests.get(f"{base_url}/connect", timeout=2))
        conn_id = conn.headers.get("UR-Connection-ID")
        
        if not conn_id:
            return False
            
        # 2. Construction of Hardware Signal
        headers = {"UR-Connection-ID": conn_id, "Content-Type": "application/json"}
        payload = {
            "actions": [
                {
                    "id": f"{remote_id}/{action}",
                    "args": args
                }
            ]
        }
        
        # 3. Broadcast to Hardware Layer
        res = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: requests.post(f"{base_url}/request", headers=headers, json=payload, timeout=2)
        )
        return res.status_code == 200
    except Exception as e:
        log(f"Unified Remote Error: {e}")
        return False

# --- LOW-LEVEL INPUT INJECTION (Session 0 Bypass) ---


def direct_press(key_code):
    """Direct Win32 API key press."""
    ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(key_code, 0, 2, 0) # 2 = KEYEVENTF_KEYUP

def direct_type(text):
    """Low-level string injection for PINs."""
    vk_map = {'0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34, 
              '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39}
    for char in text:
        if char in vk_map:
            direct_press(vk_map[char])
            time.sleep(0.1)

async def check_black_screen(photo_bytes):
    """Detect if the screenshot is a Secure Desktop black-hole."""
    try:
        nparr = np.frombuffer(photo_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            avg_brightness = np.mean(img)
            return avg_brightness < 2.0 # Near pure black
    except: pass
    return False

async def screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    if not is_authorized(update.effective_user.id): return
    status_msg = await update.message.reply_text("📸 Capturing...")
    try:
        with mss.mss() as sct:
            s_img = sct.grab(sct.monitors[1])
            png = mss.tools.to_png(s_img.rgb, s_img.size)
            
            # Check for Session 0 Lock
            if await check_black_screen(png):
                await update.message.reply_text("🔒 **Bypass Failed: Secure Desktop Protection Active.**\n\nSir, the PC is returning a black buffer. This happens if the bot process doesn't have **Administrative Privileges** required to see the Lock Screen. Please restart the terminal as Admin.")
            
            await update.message.reply_photo(photo=png)
            await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"Error: {e}")




async def click_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    try:
        x, y = (int(context.args[0]), int(context.args[1])) if context.args else (pyautogui.size()[0]//2, pyautogui.size()[1]//2)
        pyautogui.click(x, y)
        await update.message.reply_text("🖱️ Clicked")
    except: await update.message.reply_text("❌ Click failed")

async def type_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    if context.args:
        pyautogui.write(" ".join(context.args))
        await update.message.reply_text("⌨️ Typed")

async def list_profiles_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List Chrome profiles"""
    if not is_authorized(update.effective_user.id): return
    
    # Reverse map to group aliases
    grouped = {}
    for alias, folder in PROFILE_ALIASES.items():
        if folder not in grouped: grouped[folder] = []
        grouped[folder].append(alias)
        
    output = "👤 **Chrome Profiles:**\n\n"
    for folder, aliases in grouped.items():
        # Capitalize aliases
        names = ", ".join([a.title() for a in aliases])
        output += f"• **{folder}**: {names}\n"
        
    output += "\n🔁 Usage: `Switch to [Name]`"
    await update.message.reply_text(output, parse_mode='Markdown')

async def ums_login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Automate login to LPU UMS portal - Human-in-the-Loop"""
    if not is_authorized(update.effective_user.id): return
    user_id = update.effective_user.id
    
    status_msg = await retry_send_message(update, "🔐 Starting UMS Login...\n⏳ Filling credentials...")
    
    try:
        # Import the new functions
        from ums_login_pyautogui import initiate_login_step1
        
        # Run Step 1 in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, initiate_login_step1, CURRENT_CHROME_PROFILE)
        
        if result["status"] == "captcha_needed":
            # Send the captcha image to user
            img_path = result.get("image_path")
            
            await retry_edit_message(status_msg, "✅ Credentials filled!\n📸 Sending captcha...")
            
            # Set waiting state BEFORE sending the image
            USER_WAITING_CAPTCHA[user_id] = True
            
            # FIXED: Correctly open the image file
            with open(img_path, 'rb') as photo:
                photo_msg = await update.message.reply_photo(
                    photo=photo,
                    caption="🔐 **UMS Captcha**\n\n⌨️ Please reply with the code you see in the image.\n(Usually 5-6 characters)"
                )
            
            # Store message IDs for later cleanup
            USER_AUTH_DATA[user_id] = {
                'captcha_msg_id': photo_msg.message_id,
                'status_msg_id': status_msg.message_id,
                'user_request_msg_id': update.message.message_id
            }
            
            await retry_edit_message(status_msg, "⏳ Waiting for your captcha code...")
            
        else:
            await retry_edit_message(status_msg, f"❌ Error: {result.get('message', 'Unknown error')}")
            
    except Exception as e:
        await retry_edit_message(status_msg, f"❌ Error: {str(e)}")


async def battery_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    
    battery = psutil.sensors_battery()
    if battery:
        percent = battery.percent
        plugged = "Plugged In" if battery.power_plugged else "Running on Battery"
        time_left = "N/A"
        
        # Only show time if on battery and estimate is SANE (less than 100 hours)
        if not battery.power_plugged and battery.secsleft > 0:
            if battery.secsleft < 360000: # 100 hours limit
                hours = battery.secsleft // 3600
                minutes = (battery.secsleft % 3600) // 60
                time_left = f"{hours}h {minutes}m remaining"
            else:
                time_left = "Calculating..."
            
        msg = f"🔋 **Battery Status:** {percent}%\n🔌 **Power Mode:** {plugged}"
        if not battery.power_plugged:
            msg += f"\n⏳ **Estimated:** {time_left}"
    else:
        msg = "🔌 **Power Status:** No battery detected."
        
    await update.message.reply_text(msg, parse_mode='Markdown')

async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id): return
    await update.message.reply_text("🔒 **Locking PC...**", parse_mode='Markdown')
    os.system("rundll32.exe user32.dll,LockWorkStation")

async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced Unlock Protocol: Bypass Windows Secure Desktop via 'Wake & Type'"""
    if not is_authorized(update.effective_user.id): return
    
    pin = ""
    if context.args:
        pin = context.args[0]
    elif " " in update.message.text:
        parts = update.message.text.split(" ", 1)
        if len(parts) > 1 and parts[1].strip().isdigit():
            pin = parts[1].strip()

    if not pin:
        USER_WAITING_PIN[update.effective_user.id] = True
        await update.message.reply_text("🔓 **Waking telemetry...**\n(Media Key Injection)\n\nTo unlock, provide tactical clearance: `/unlock [YOUR_PIN]`\nOr simply reply with your PIN now.", parse_mode='Markdown')
        # 1. Wake the screen using Shift/Media keys
        pyautogui.press('shift')
        await asyncio.sleep(0.5)
        # 2. Sweep away the lock image immediately
        pyautogui.press('esc') 
        # 3. Mouse wiggle to ensure screen is active
        pyautogui.move(0, 10); pyautogui.move(0, -10)
        return

    status_msg = await update.message.reply_text(f"🦾 **Hardware Emulation Protocol Live.**\nBypassing Secure Desktop via Unified Remote HID Driver...", parse_mode='Markdown')
    
    try:
        # 1. THE "WAKE" - Virtual HID ESC/Shift
        # Unified Remote's driver is seen by Windows as a real USB keyboard
        success = await send_ur_action("unified.basicinput", "stroke", ["ESCAPE"])
        if not success:
            await retry_edit_message(status_msg, "⚠️ **Driver Link Failed.**\nSir, Unified Remote Server is not responding on `localhost:9510`. Please ensure the server is running.")
            return
            
        await asyncio.sleep(1.0)
        
        # 2. THE "INPUT" - HID Text Injection
        await send_ur_action("unified.basicinput", "text", [pin])
        await asyncio.sleep(0.5)
        await send_ur_action("unified.basicinput", "stroke", ["RETURN"])
        
        await retry_edit_message(status_msg, "📡 **HID Sequence Transmitted.**\nVirtual Keyboard has injected the pulses. Standby for desktop render...")
        
    except Exception as e:
        await retry_edit_message(status_msg, f"⚠️ **Emulation Error:** {e}")
        return

    # 3. VERIFICATION
    await asyncio.sleep(5) 
    await screenshot_command(update, context)

async def run_power_guard(bot):
    """Proactive background monitoring for power/battery"""
    last_plugged = None
    alert_sent_15 = False
    
    if not ALLOWED_USER_IDS: return
    admin_id = ALLOWED_USER_IDS[0]
    
    print("🔌 Smart Power Guard Active")
    loop = asyncio.get_event_loop()
    
    last_lid_dark = None
    last_mouse_pos = pyautogui.position()
    idle_start_time = time.time()
    last_camera_check_time = 0
    last_heartbeat_time = 0
    
    while True:
        try:
            # 1. Heartbeat
            if time.time() - last_heartbeat_time > 60:
                update_heartbeat()
                last_heartbeat_time = time.time()

            # 2. THERMAL WATCHDOG (SENTINEL PROTOCOL)
            telemetry = get_hw_telemetry()
            c_temp = telemetry["cpu_temp"]
            if c_temp >= 94:
                global SENTINEL_CRITICAL_START, SENTINEL_ALERT_COOLDOWN
                if SENTINEL_CRITICAL_START == 0:
                    SENTINEL_CRITICAL_START = time.time()
                    log(f"🔥 Sentinel: CPU entered CRITICAL thermal zone ({c_temp}°C)")
                elif (time.time() - SENTINEL_CRITICAL_START) >= 120:
                    if time.time() - SENTINEL_ALERT_COOLDOWN > 600: # 10 min alert cooldown
                        kb = [[InlineKeyboardButton("❄️ EMERGENCY 100% FANS", callback_data="emergency_cooling")]]
                        await bot.send_message(
                            chat_id=admin_id,
                            text=f"🆘 **SENTINEL EMERGENCY ALERT**\n\nCPU has been at **{c_temp}°C** for > 2 minutes.\nThermal throttling imminent.",
                            reply_markup=InlineKeyboardMarkup(kb),
                            parse_mode='Markdown'
                        )
                        SENTINEL_ALERT_COOLDOWN = time.time()
            else:
                SENTINEL_CRITICAL_START = 0 # Reset timer if safe

            # 3. Power Alerts
            battery = psutil.sensors_battery()
            if battery is not None:
                percent = battery.percent
                plugged = battery.power_plugged
                if last_plugged is None: last_plugged = plugged

                if last_plugged and not plugged:
                    await bot.send_message(chat_id=admin_id, text="🚨 **Power Guard: Charger Unplugged!**\nDetected on your laptop.", parse_mode='Markdown')
                elif not last_plugged and plugged:
                    await bot.send_message(chat_id=admin_id, text="🔋 **Power Guard: Charger Connected.**", parse_mode='Markdown')

                
                if percent <= 15 and not plugged and not alert_sent_15:
                    await bot.send_message(chat_id=admin_id, text=f"🪫 **Power Guard: Battery Critical ({percent}%)!**", parse_mode='Markdown')
                    alert_sent_15 = True
                if percent > 20: alert_sent_15 = False
                last_plugged = plugged
                


                last_plugged = plugged
        except Exception as e:
            print(f"Power Guard Error: {e}")
            
        await asyncio.sleep(5) # Politeness: Check every 5 seconds

async def heartbeat_task(application):
    """Simple log to verify the bot process is alive"""
    while True:
        try:
            with open("bot_heartbeat.txt", "w") as f:
                f.write(str(time.time()))
            logging.getLogger('').info("[HEARTBEAT] Bot is alive and polling.")
        except: pass
        await asyncio.sleep(180) # 3 min

async def fetch_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.lower()
    
    specific_video = ""
    if "named" in text or "video :" in text:
        if ":" in text: specific_video = text.split(":", 1)[1].strip()
        elif "named" in text: specific_video = text.split("named", 1)[1].strip()
    
    if specific_video:
        query = f"{USER_LAST_SEARCH.get(user_id, '')} {specific_video}" if user_id in USER_LAST_SEARCH else specific_video
    else:
        query = USER_LAST_SEARCH.get(user_id)
        if not query:
            await update.message.reply_text("❌ No search context found!")
            return
        
    status_msg = await update.message.reply_text(f"🔍 Fetching link for: `{query}`...", parse_mode='Markdown')
    try:
        search = VideosSearch(query, limit=1)
        result = search.result()
        if result['result']:
            v = result['result'][0]
            await status_msg.edit_text(f"📺 **Found:**\n[{v['title']}]({v['link']})\n🔗 {v['link']}", parse_mode='Markdown')
        else:
            await status_msg.edit_text("❌ No results.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

# Helper to format chrome command
def get_chrome_cmd(url=""):
    pf = CURRENT_CHROME_PROFILE
    if url:
         return f'Start-Process chrome -ArgumentList "{url}", "--profile-directory=\\"{pf}\\""'
    return f'Start-Process chrome -ArgumentList "--profile-directory=\\"{pf}\\""'

def parse_natural_command(text: str) -> Optional[str]:
    """Parse natural language commands and convert to executable commands"""
    text = text.lower().strip()
    global CURRENT_CHROME_PROFILE
    
    # Special intents
    if text.startswith('download movie ') or text.startswith('download '):
        movie_name = text.replace('download movie ', '').replace('download ', '').strip()
        if movie_name: return f"DOWNLOAD_MOVIE_INTENT:{movie_name}"

    if 'screenshot' in text or 'screen' in text: return "SCREENSHOT_INTENT"
    if 'list profiles' in text or 'show profiles' in text or 'chrome profiles' in text: return "LIST_PROFILES_INTENT"
    
    # UMS Intents
    if 'messages from touch' in text or 'show my messages' in text or 'ums messages' in text:
        return "UMS_MESSAGES_INTENT"
        
    if 'login ums' in text or 'log in ums' in text or 'ums login' in text or 'my attendance' in text or 'show attendance' in text: 
        return "UMS_LOGIN_INTENT"
    
    # Timetable Intents (e.g., "Time-Table of Tuesday")
    if 'time table of' in text or 'timetable of' in text or 'time-table of' in text:
        day = text.split(' of ')[-1].strip().capitalize()
        # Return matched day as intent
        return f"UMS_TIMETABLE_INTENT:{day}"
    
    if 'start steam' in text: return 'Start-Process "steam://open/games"'
    if 'click' in text: return "CLICK_INTENT"
    if 'close tab' in text or 'close this tab' in text: return "CLOSE_TAB_INTENT"
    if 'ip address' in text: return 'ipconfig'
    if 'battery' in text: return "BATTERY_INTENT"
    if 'lock' in text and 'pc' in text or text == 'lock': return "LOCK_INTENT"
    if 'unlock' in text: return "UNLOCK_INTENT"
    
    # Handle "switch to X" or "use profile X"
    if text.startswith('switch to ') or text.startswith('use profile ') or text.startswith('switch profile '):
        # Clean up the command to extract just the name
        p_name = text.replace('switch profile to ', '').replace('switch to ', '').replace('switch profile ', '').replace('use profile ', '').strip().lower()
        
        # Check Aliases
        real_name = p_name # Default fallback
        
        if p_name in PROFILE_ALIASES:
            real_name = PROFILE_ALIASES[p_name]
        elif p_name.isdigit():
             if p_name == "0": real_name = "Default"
             else: real_name = f"Profile {p_name}"
             
        CURRENT_CHROME_PROFILE = real_name
        return f"INTERNAL_SWITCH_PROFILE:{real_name}"
    
    # Steam game launching
    if (text.startswith('open ') or text.startswith('play ')) and STEAM_GAMES:
        q = text.split(' ', 1)[1].strip().lower()
        for g, aid in STEAM_GAMES.items():
            if q in g: return f'Start-Process "steam://run/{aid}"'

    
    # Handle "list files in X" pattern
    if 'list files in' in text or 'show files in' in text:
        parts = text.split(' in ', 1)
        if len(parts) == 2:
            folder = parts[1].strip()
            return f"ls {folder}"
    
    # YouTube handling
    if 'youtube' in text:
        # "YouTube [query]"
        if text.startswith('youtube '):
            query = text[8:].strip()
            safe_query = query.replace(' ', '+')
            return f'Start-Process chrome -ArgumentList "https://www.youtube.com/results?search_query={safe_query}"'
            
        # "Search [query] on/in YouTube"
        if text.endswith(' on youtube') or text.endswith(' in youtube'):
            query = text.rsplit(' youtube', 1)[0].replace('search ', '').replace('find ', '').replace('open ', '').replace('play ', '')
            if query.endswith(' on'): query = query[:-3]
            if query.endswith(' in'): query = query[:-3]
            
            safe_query = query.strip().replace(' ', '+')
            return f'Start-Process chrome -ArgumentList "https://www.youtube.com/results?search_query={safe_query}"'

    if 'google' in text:
        query = text.replace('google', '').replace('search', '').strip()
        return get_chrome_cmd(f"https://www.google.com/search?q={query.replace(' ', '+')}")

    # GENERIC SEARCH FALLBACK
    if text.startswith('search ') or text.startswith('find '):
        query = text.replace('search ', '').replace('find ', '').strip()
        return get_chrome_cmd(f"https://www.google.com/search?q={query.replace(' ', '+')}")

    if text.startswith('open '):
        target = text[5:].strip()
        if 'chrome' in target: 
             return get_chrome_cmd() # Just open browser
        if 'notepad' in target: return 'start notepad'
        if '.' in target: return get_chrome_cmd(f"https://{target}")

    return None

async def process_command_logic(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a single command string"""
    text_lower = text.lower()
    user_id = update.effective_user.id
    
    # Link Request
    if ("link" in text_lower or "ink" in text_lower or "video :" in text_lower) and ("send" in text_lower or "give" in text_lower or "get" in text_lower):
        await fetch_youtube_link(update, context)
        return

    # File Request
    if text_lower.startswith("send me ") or text_lower.startswith("get "):
        clean_path = text.split(" ", 2)[-1] if "send me" in text_lower else text[4:]
        context.args = [clean_path.strip()]
        await download_command(update, context)
        return
        


    # Commands
    for k in ['run ', 'execute ', 'cmd ', 'powershell ']:
        if text_lower.startswith(k):
            await run_system_command(update, text[len(k):])
            return

    # Natural Language
    translated = parse_natural_command(text)
    if translated:
        # Core Control
        if translated == "INTERNAL_BOT_START":
            set_bot_active_state(True)
            await retry_send_message(update, "🚀 **Bot Activated!** I am now listening for commands.", parse_mode='Markdown')
            return
        elif translated == "INTERNAL_BOT_STOP":
            set_bot_active_state(False)
            await retry_send_message(update, "💤 **Bot Deactivated.** I will ignore all commands until you say 'Start the bot'.", parse_mode='Markdown')
            # Fallback: Actually close if user explicitly said "CLOSE"
            if 'close' in text.lower():
                await retry_send_message(update, "🛑 Closing process...")
                os._exit(0)
            return

        if not get_bot_active_state(): return

        if translated == "SCREENSHOT_INTENT": await screenshot_command(update, context)
        elif translated == "CLICK_INTENT": await click_command(update, context)
        elif translated == "LIST_PROFILES_INTENT": await list_profiles_command(update, context)
        elif translated.startswith("DOWNLOAD_MOVIE_INTENT:"):
            movie_name = translated.split(":", 1)[1]
            status = await retry_send_message(update, f"🎬 **Searching for:** `{movie_name}`\n⏳ This will take a few seconds...", parse_mode='Markdown')
            
            try:
                from movie_downloader import download_movie_yts
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, download_movie_yts, movie_name)
                
                if res.get("status") == "success":
                    await retry_edit_message(status, f"✅ **Success:** {res.get('message')}\n🚀 Download is live!")
                    if res.get("image_path") and os.path.exists(res.get("image_path")):
                        with open(res.get("image_path"), 'rb') as photo:
                            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo, caption="📸 **Live Download Status (CMD)**", parse_mode='Markdown')
                else:
                    await retry_edit_message(status, f"❌ **Error:** {res.get('message')}")
            except Exception as e:
                await retry_edit_message(status, f"❌ **Error:** {str(e)}")
        elif translated == "UMS_MESSAGES_INTENT":
            USER_UMS_INTENT[user_id] = "MESSAGES"
            await ums_login_command(update, context)
        elif translated == "UMS_LOGIN_INTENT": 
            USER_UMS_INTENT[user_id] = "ATTENDANCE" # Default behavior
            await ums_login_command(update, context)
        elif translated.startswith("UMS_TIMETABLE_INTENT:"):
            target_day = translated.split(":")[1]
            USER_UMS_INTENT[user_id] = f"TIMETABLE:{target_day}"
            await ums_login_command(update, context)
        elif translated == "BATTERY_INTENT": await battery_command(update, context)
        elif translated == "LOCK_INTENT": await lock_command(update, context)
        elif translated == "UNLOCK_INTENT": await unlock_command(update, context)
        elif translated.startswith("INTERNAL_SWITCH_PROFILE:"):
             new_profile = translated.split(":", 1)[1]
             global CURRENT_CHROME_PROFILE
             CURRENT_CHROME_PROFILE = new_profile
             print(f"SWITCHING PROFILE TO {new_profile}")
             await retry_send_message(update, f"🔄 Profile Switched to: `{new_profile}`", parse_mode='Markdown')
        elif translated.startswith("ls "):
             # Forward to list_files logic
             clean_path = translated[3:].strip()
             context.args = [clean_path]
             await list_files_command(update, context)
        elif translated == "CLOSE_TAB_INTENT":
            pyautogui.hotkey('ctrl', 'w')
            await retry_send_message(update, "❎ Tab Closed")
        else:
            if 'youtube.com/results' in translated:
                try:
                    q = translated.split('search_query=')[1].strip('"').replace('+', ' ')
                    USER_LAST_SEARCH[user_id] = q
                except: pass
            
            await retry_send_message(update, f"🧠 Running: `{translated}`", parse_mode='Markdown')
            await run_system_command(update, translated)
        return
        
    await retry_send_message(update, f"🤔 Unknown command: {text}")

async def run_background_ums_tasks(update, context):
    """Background task to clear popups and then fetch the requested report"""
    user_id = update.effective_user.id
    intent = USER_UMS_INTENT.get(user_id, "ATTENDANCE")
    
    try:
        from ums_login_pyautogui import get_ums_attendance, get_ums_timetable, get_ums_messages
        loop = asyncio.get_event_loop()
        
        # Step 1.6: CLEAR POPUPS
        from ums_login_pyautogui import clear_ums_popups
        await loop.run_in_executor(None, clear_ums_popups)
        
        # Step 2: Fetch Data (Direct transition for maximum speed)
        if intent == "MESSAGES":
            res = await loop.run_in_executor(None, get_ums_messages)
            if res.get("status") == "success":
                raw_data = res.get("data", "")
                if raw_data == "EMPTY_MESSAGES":
                    await retry_send_message(update, "📭 No new messages found on your LPU Touch dashboard.")
                else:
                    msg = "📡 **Latest Messages from Touch**\n\n" + raw_data
                    await retry_send_message(update, msg, parse_mode='Markdown')
            else:
                await retry_send_message(update, f"❌ Retrieval Error: {res.get('message')}")
        
        elif intent == "ATTENDANCE":
            res = await loop.run_in_executor(None, get_ums_attendance)
            if res.get("status") == "success":
                raw_data = res.get("data", "")
                lines = [l.strip() for l in raw_data.splitlines() if l.strip()]
                
                perf_list = []
                official_agg = ""
                
                for line in lines:
                    if line.startswith("COURSE:"):
                        parts = line.split(":")
                        if len(parts) >= 3:
                            name_full = parts[1]
                            code_match = re.search(r'([A-Z]{3,4}\d{3,4})', name_full)
                            display_name = code_match.group(1) if code_match else name_full[:15]
                            val = parts[2]
                            perf_list.append(f"• **{display_name}**: {val}")
                    elif line.startswith("AGGREGATE:"):
                        official_agg = line.split(":")[1]

                if perf_list:
                    msg = "📊 **Your Attendance Summary**\n\n" + "\n".join(perf_list)
                    if official_agg:
                        msg += f"\n\n📈 **Official Aggregate: {official_agg}**"
                    await retry_send_message(update, msg, parse_mode='Markdown')
                else:
                    await retry_send_message(update, "✅ No attendance data found. Is the report loaded?")
            else:
                await retry_send_message(update, f"❌ Attendance Error: {res.get('message')}")
                
        elif intent.startswith("TIMETABLE:"):
            day_target = intent.split(":")[1].strip().capitalize()
            res = await loop.run_in_executor(None, get_ums_timetable, day_target)
            if res.get("status") == "success":
                timetable_output = res.get("data", "No classes found! 🎉")
                # Header + Bulletin list already formatted in extraction script
                msg = f"📅 **Your {day_target} Classes:**\n\n{timetable_output}"
                await retry_send_message(update, msg, parse_mode='Markdown')
            else:
                await retry_send_message(update, f"❌ Timetable Error: {res.get('message')}")













            
    except Exception as e:
        log(f"Error in background task: {e}")

# -----------------------------------------------



async def brightness_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set Laptop Screen Brightness (0-100)"""
    user_id = update.effective_user.id
    if not is_authorized(user_id): return
    
    args = context.args
    if not args:
        await retry_send_message(update, "💡 Usage: /brightness <0-100>\nExample: /brightness 50")
        return
        
    try:
        level = int(args[0])
        # Clamp value
        level = max(0, min(100, level))
        
        if set_brightness_wmi(level):
            await retry_send_message(update, f"💡 Brightness set to **{level}%**")
        else:
            await retry_send_message(update, "⚠️ System rejected the brightness update.")
        
    except ValueError:
        await retry_send_message(update, "⚠️ Please enter a number between 0 and 100.")
    except Exception as e:
        await retry_send_message(update, f"⚠️ Error: {e}")

async def volume_set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set System Volume (0-100)"""
    user_id = update.effective_user.id
    if not is_authorized(user_id): return
    
    args = context.args
    level = None
    
    # Handle /vol76 (attached) or /vol 76 (arg) cases
    if not args:
        cmd_text = update.message.text.replace('/', '').lower()
        # Extract number if attached to command
        match = re.search(r'(?:vol|volume)(\d+)', cmd_text)
        if match:
            level = int(match.group(1))
    else:
        try:
            level = int(args[0])
        except: pass

    if level is None:
        await retry_send_message(update, "🔊 Usage: /vol <0-100>\nExample: /vol 50")
        return

    try:
        # PLAN C: The "Key-Masher" Method 
        # We use a PowerShell script to press VolDown 50 times then VolUp X times
        # precise enough for government work.
        ps_script = os.path.abspath("set_vol.ps1")
        cmd = f"powershell -ExecutionPolicy Bypass -File \"{ps_script}\" {level}"
        
        subprocess.run(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        await retry_send_message(update, f"🔊 Volume adjustment initiated to **{level}%**...")
        
    except Exception as e:
        await retry_send_message(update, f"⚠️ Volume Error: {e}")

async def media_command(update: Update, context: ContextTypes.DEFAULT_TYPE, override_cmd=None, override_args=None):
    """Universal Media Control for Spotify, YouTube, etc."""
    user_id = update.effective_user.id
    if not is_authorized(user_id): return
    
    global vlc_player # Declare global here to avoid SyntaxError
    
    if override_cmd:
        cmd = override_cmd
        args = override_args if override_args else []
    else:
        cmd = update.message.text.split()[0].replace('/', '').lower()
        args = update.message.text.split()[1:] # Get arguments for song name
    
    # Specific Song Request: /play Song Name
    # Specific Song Request: /play Song Name
    if cmd == 'play' and args:
        song_name = " ".join(args)
        search_msg = await retry_send_message(update, f"🔎 Searching for: **{song_name}**...")
        
        # --- CLEANUP PROTOCOL ---
        # Stop previous media before starting new one
        try:
            # 1. Stop VLC
            if 'vlc_player' in globals() and vlc_player is not None:
                vlc_player.stop()
            
            # 2. Kill YouTube Browsers (Targeted by Title)
            # This avoids killing all chrome/edge instances, only those playing video
            subprocess.run('taskkill /F /FI "WINDOWTITLE eq *YouTube*" /T', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except: pass
        # ------------------------

        # "Independent Audio" Strategy: yt-dlp + VLC (Headless Streaming)
        try:
            import yt_dlp
            import vlc
            
            # Check for explicit "on youtube" request for Browser Mode
            browser_mode = False
            if "on youtube" in song_name.lower():
                browser_mode = True
                song_name = song_name.lower().replace("on youtube", "").strip()
            
            # 1. Search and extract Info
            loop = asyncio.get_running_loop()
            
            def fetch_info():
                ydl_opts = {
                    'format': 'best', # Get video too if browser mode
                    'noplaylist': True,
                    'quiet': True,
                    'default_search': 'ytsearch',
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if browser_mode:
                        # TACTICAL UPGRADE: Verify source authenticity for Video Mode
                        search_query = song_name
                        # If a trailer is requested, prioritize official uploads
                        if "trailer" in song_name.lower() and "official" not in song_name.lower():
                            search_query += " official"
                        elif "official" not in song_name.lower():
                            search_query += " official"
                            
                        query = f"ytsearch1:{search_query}"
                    else:
                        # Smart Search for Audio: Append "official audio" to favor studio versions
                        query = f"ytsearch1:{song_name} official audio"
                        
                    info = ydl.extract_info(query, download=False)['entries'][0]
                    return info
            
            info = await loop.run_in_executor(None, fetch_info)
            audio_url = info['url']
            title = info['title']
            video_id = info['id']
            
            if browser_mode:
                # Browser Mode: Launch URL with Fullscreen Flags
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Try Chrome first with KIOSK mode (Industrial Fullscreen)
                chrome_cmd = f'start chrome --new-window --start-fullscreen "{youtube_url}"'
                
                # Launch
                try:
                    subprocess.Popen(chrome_cmd, shell=True)
                except:
                    subprocess.Popen(f'start {youtube_url}', shell=True)

                # FORCE Fullscreen via Keystroke Injection (The "Hammer" method)
                # YouTube shortcut 'f' toggles fullscreen
                async def force_fullscreen():
                    await asyncio.sleep(4) # Wait for page load
                    fs_cmd = "(New-Object -ComObject wscript.shell).SendKeys('f')"
                    subprocess.run(["powershell", "-Command", fs_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                
                asyncio.create_task(force_fullscreen())

                # User-Requested Persona Confirmation
                await retry_send_message(update, f"The **{title}** is now commencing, Sir.")
                
                # Cleanup "Searching" msg immediately
                try:
                    if search_msg:
                        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=search_msg.message_id)
                except: pass
                
            else:
                # Headless Mode: VLC
                
                # 2. Play using VLC (Background Process)
                # Create a singleton player instance if not exists
                if 'vlc_player' not in globals() or vlc_player is None:
                    # --no-video for audio only, --intf dummy for no interface
                    instance = vlc.Instance('--no-video --intf dummy --quiet')
                    vlc_player = instance.media_player_new()
                
                media = vlc_player.get_instance().media_new(audio_url)
                vlc_player.set_media(media)
                vlc_player.audio_set_volume(70) # Set standard volume
                vlc_player.play()
                
                # User-Requested Persona Confirmation
                await retry_send_message(update, f"The **{title}** is now commencing, Sir.")
                
                # Clean up the "Searching..." message to keep chat tidy
                try:
                    if search_msg:
                        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=search_msg.message_id)
                except: pass
            
        except Exception as e:
            print(f"Stream Error: {e}")
            await retry_send_message(update, f"⚠️ Stream Error: {e}")
        return

        # Fallback to Old Search UI method if Deep Link fails
        encoder = urllib.parse.quote(song_name)
        subprocess.Popen(f'start spotify:search:"{encoder}"', shell=True)
        # ... (rest of old macro logic would be here if we kept it, but deep link should work)
        return
        
        await retry_send_message(update, f"🎶 Playing top result for: {song_name}")
        return

    # VLC Control Handlers (Direct Object Control)
    if 'vlc_player' in globals() and vlc_player is not None:
        if cmd == 'pause':
            vlc_player.pause()
            await retry_send_message(update, "⏸️ J.A.R.V.I.S Audio: Paused")
            return
        elif cmd == 'resume' or cmd == 'unpause':
            vlc_player.play()
            await retry_send_message(update, "▶️ J.A.R.V.I.S Audio: Resumed")
            return
        elif cmd == 'stop':
            vlc_player.stop()
            await retry_send_message(update, "⏹️ J.A.R.V.I.S Audio: Stopped")
            return
        elif cmd == 'volset' and args:
            try:
                new_vol = int(args[0])
                vlc_player.audio_set_volume(new_vol)
                await retry_send_message(update, f"🔊 Volume set to {new_vol}%")
            except: pass
            return

    # Direct Media Key Codes for Windows (Fallback / System Control)
    # 179=Play/Pause, 176=Next, 177=Prev, 174=VolDown, 175=VolUp, 173=Mute
    action_map = {
        'play': (179, "⏯️ Toggled Play/Pause"),
        'pause': (179, "⏯️ Toggled Play/Pause"),
        'next': (176, "⏭️ Next Track"),
        'skip': (176, "⏭️ Next Track"),
        'prev': (177, "⏮️ Previous Track"),
        'back': (177, "⏮️ Previous Track"),
        'volup': (175, "🔊 Volume Up"),
        'voldown': (174, "🔉 Volume Down"),
        'mute': (173, "🔇 Mute Toggled")
    }
    
    if cmd in action_map:
        # check_singleton() removed to prevent restart loops
        code, msg = action_map[cmd]
        
        # Robust PowerShell Injection for Media Keys
        # This works even if screen is locked or app is minimized
        ps_cmd = f"(New-Object -ComObject wscript.shell).SendKeys([char]{code})"
        subprocess.run(["powershell", "-Command", ps_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
        
        # For volume, do it 3 times to make it noticeable
        if 'vol' in cmd:
            subprocess.run(["powershell", "-Command", ps_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.run(["powershell", "-Command", ps_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
        
        await retry_send_message(update, msg)
    
    # Launch Spotify specifically if asked
    if cmd == 'spotify':
        subprocess.Popen(f"start spotify:", shell=True)
        await retry_send_message(update, "🎵 Launching Spotify...")

async def darkness_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Protocol Darkness: Kill Monitor Signal"""
    if not is_authorized(update.effective_user.id): return
    try:
        import ctypes
        log("Darkness Initiation: Sending SC_MONITORPOWER OFF signal.")
        # WM_SYSCOMMAND = 0x0112, SC_MONITORPOWER = 0xF170, OFF = 2
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        await retry_send_message(update, "🌑 **Project Darkness Initiated.** Display signal cut. The Engine remains active. 🛰️")
    except Exception as e:
        log(f"Darkness Error: {e}")


async def undark_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restore Monitor Signal"""
    if not is_authorized(update.effective_user.id): return
    log("Wake Command Triggered.")
    try:
        import ctypes
        log("Wakeup Sequence: Sending SC_MONITORPOWER ON signal.")
        # WM_SYSCOMMAND = 0x0112, SC_MONITORPOWER = 0xF170, ON = -1
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
        
        # Multi-factor aggressive wake
        await asyncio.sleep(0.5)
        pyautogui.press('shift')
        await asyncio.sleep(0.1)
        pyautogui.click() # Simulate a click to force wakeup
        pyautogui.move(10, 10)
        pyautogui.move(-10, -10)
        
        # PERSISTENCE: Restore brightness (prevents the "very dim wake" bug)
        set_brightness_wmi(70) 
        
        await retry_send_message(update, "☀️ **Display Restored.** Welcome back, Boss.")
    except Exception as e:
        log(f"Wake Error: {e}")
        await retry_send_message(update, f"⚠️ Wake Error: {e}")

async def thermal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Protocol Thermal: Switch Lenovo Fan Modes via Registry + WMI"""
    if not is_authorized(update.effective_user.id): return
    args = context.args
    # Legion Toolkit CLI path
    LLT_CLI = r"C:\Users\akshu\AppData\Local\Programs\LenovoLegionToolkit\llt.exe"
    
    mode_map = {"quiet": "quiet", "balanced": "balance", "performance": "performance"}
    power_plans = {
        "quiet": "381b4222-f694-41f0-9685-ff5bb260df2e",
        "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
        "performance": "4711a9a9-9ed1-4e39-87ec-bbb642e8ebac"
    }
    
    if not args:
        text = update.message.text.lower()
        for k in mode_map:
            if k in text:
                args = [k]
                break

    if not args or args[0].lower() not in mode_map:
        await retry_send_message(update, "🌡️ **Usage:** `/fan [quiet|balanced|performance]`")
        return
        
    target = args[0].lower()
    llt_mode = mode_map[target]
    plan_guid = power_plans[target]
    
    async def try_set_mode(mode_name):
        res = subprocess.run(
            [LLT_CLI, "feature", "set", "power-mode", mode_name],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=8
        )
        # Check for connection lost error
        if "Failed to connect" in res.stderr:
            log("LLT: Connection lost. Re-initializing...")
            await ensure_llt_ready(force=True)
            # Second attempt
            res = subprocess.run(
                [LLT_CLI, "feature", "set", "power-mode", mode_name],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=8
            )
        return res

    try:
        await ensure_llt_ready()
        result = await try_set_mode(llt_mode)
        
        if result.returncode != 0:
            log(f"LLT Error: {result.stderr}")
            await retry_send_message(update, f"⚠️ **Hardware Error.** Legion Toolkit refused the command.\n`{result.stderr.strip()}`")
            return

        # Set Windows power plan to match
        subprocess.run(f'powercfg /setactive {plan_guid}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        log(f"Thermal: {target} via Legion Toolkit CLI")
        
        # LINKED RGB PROTOCOL
        rgb_map = {
            "performance": "3",
            "balanced": "4",
            "quiet": "1" 
        }
        
        if target in rgb_map:
            rgb_target = rgb_map[target]
            subprocess.run(
                [LLT_CLI, "rgb", "set", rgb_target],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        
        # Contextual responses
        responses = {
            "quiet": "🤫 **Stealth Mode Active.** Lighting Cut. 🛰️",
            "balanced": "⚖️ **Balanced Mode.** Systems Normalized. 🛰️",
            "performance": "🚀 **Performance Mode.** Battle Stations Red. 🔥🛰️"
        }
        
        await retry_send_message(update, responses[target])
    except subprocess.TimeoutExpired:
        log(f"Thermal Error: Legion Toolkit timeout")
        await retry_send_message(update, "⚠️ **Thermal Control Timeout.** Legion Toolkit not responding.")
    except FileNotFoundError:
        log(f"Thermal Error: Legion Toolkit not found")
        await retry_send_message(update, "⚠️ **Legion Toolkit not installed.** Install from: https://github.com/BartoszCichecki/LenovoLegionToolkit")
    except Exception as e:
        log(f"Thermal Error: {e}")
        await retry_send_message(update, f"⚠️ Thermal Error: {e}")

async def rgb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Protocol RGB: Control Keyboard Backlight Profiles"""
    if not is_authorized(update.effective_user.id): return
    
    # Legion Toolkit CLI path
    LLT_CLI = r"C:\Users\akshu\AppData\Local\Programs\LenovoLegionToolkit\llt.exe"
    
    args = context.args
    valid_args = ["0", "1", "2", "3", "4", "off"]
    
    if not args:
        # Check text for natural language args
        text = update.message.text.lower()
        if "off" in text: args = ["0"]
        else:
            # Try to find digits
            import re
            found = re.findall(r'[0-4]', text)
            if found: args = [found[0]]

    if not args or args[0].lower() not in valid_args:
        await retry_send_message(update, "💡 **Usage:** `/rgb [0-4 | off]`\n0/Off = Lights Out\n1-4 = Switch Profile")
        return
        
    target = args[0].lower()
    # User configured Profile 1 as Black/Off
    if target == "off" or target == "0": target = "1"
    
    try:
        # Use centralized failsafe
        await ensure_llt_ready()

        subprocess.run(
            [LLT_CLI, "rgb", "set", target],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=5
        )
        
        status_map = {
            "0": "🌑 **Lights Out.** Stealth protocol active.",
            "1": "🔵 **Profile 1 Active.**",
            "2": "🟢 **Profile 2 Active.**",
            "3": "🟣 **Profile 3 Active.**",
            "4": "🌈 **Profile 4 Active.**"
        }
        
        await retry_send_message(update, status_map.get(target, f"💡 **RGB Set to {target}.**"))
        log(f"RGB: Set particular profile {target}")
        
    except Exception as e:
        log(f"RGB Error: {e}")
        await retry_send_message(update, f"⚠️ RGB Error: {e}")

async def taskbar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Control TranslucentTB taskbar appearance"""
    if not is_authorized(update.effective_user.id): return
    
    args = context.args
    if not args:
        await retry_send_message(update, 
            "🎨 **Taskbar Control**\n\n"
            "Usage: `/taskbar <mode> [color] [blur]`\n\n"
            "**Modes:**\n"
            "• `clear` - Fully transparent\n"
            "• `acrylic` - Frosted glass effect\n"
            "• `blur` - Blurred background\n"
            "• `opaque` - Solid color\n"
            "• `normal` - Windows default\n\n"
            "**Examples:**\n"
            "`/taskbar clear`\n"
            "`/taskbar acrylic #1E1E1E80 12`\n"
            "`/taskbar blur #00000040 15`",
            parse_mode='Markdown'
        )
        return
    
    mode = args[0].lower()
    color = args[1] if len(args) > 1 else '#00000000'
    blur_radius = float(args[2]) if len(args) > 2 else 9.0
    
    valid_modes = ['clear', 'acrylic', 'blur', 'opaque', 'normal']
    if mode not in valid_modes:
        await retry_send_message(update, f"❌ Invalid mode. Use: {', '.join(valid_modes)}")
        return
    
    status_msg = await retry_send_message(update, f"🎨 Applying `{mode}` mode...")
    
    if set_taskbar_mode(mode, color, blur_radius):
        await retry_send_message(update, f"✅ Taskbar set to **{mode.upper()}** mode. Blur: {blur_radius}")
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
        except: pass
    else:
        await retry_send_message(update, "❌ Failed to update taskbar settings.")

async def timetable_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display UMS timetable for requested day"""
    if not is_authorized(update.effective_user.id): return
    
    args = context.args
    requested_day = args[0].lower() if args else "today"
    
    # Parse day request
    today = datetime.now()
    day_map = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6
    }
    
    if requested_day == "today":
        target_day = today.weekday()
        day_name = today.strftime("%A")
    elif requested_day == "tomorrow":
        tomorrow = today + timedelta(days=1)
        target_day = tomorrow.weekday()
        day_name = tomorrow.strftime("%A")
    elif requested_day in day_map:
        target_day = day_map[requested_day]
        day_name = list(day_map.keys())[list(day_map.values()).index(target_day)].capitalize()
    elif requested_day == "full" or requested_day == "week":
        target_day = -1  # Full week
        day_name = "Full Week"
    else:
        await retry_send_message(update, 
            "📅 **Timetable Command**\n\n"
            "Usage: `/timetable [day]`\n\n"
            "Examples:\n"
            "• `/timetable today`\n"
            "• `/timetable tomorrow`\n"
            "• `/timetable monday`\n"
            "• `/timetable full` (entire week)",
            parse_mode='Markdown'
        )
        return
    
    status_msg = await retry_send_message(update, f"📥 Fetching {day_name} timetable from UMS...")
    
    try:
        # Download timetable Excel file
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        excel_file = None
        
        # Launch browser and download
        await retry_send_message(update, "🔐 Accessing UMS...")
        
        # Use our Robust PyAutoGUI Helper (reusing existing session)
        from ums_login_pyautogui import get_ums_timetable_excel, initiate_login_step1
        
        loop = asyncio.get_event_loop()
        
        # 1. Try to download directly (assuming logged in)
        result = await loop.run_in_executor(None, get_ums_timetable_excel, requested_day)
        
        excel_file = None
        
        if result["status"] == "success":
            excel_file = result["file_path"]
            await retry_send_message(update, "✅ Download successful!")
            
        elif "Download failed" in result.get("message", ""):
            # Login likely needed/expired
            await retry_send_message(update, "🔑 Session expired/invalid. Auto-login initiated...")
            
            # 2. Trigger Auto-Login
            profile_dir = CURRENT_CHROME_PROFILE if 'CURRENT_CHROME_PROFILE' in globals() else "Default"
            login_res = await loop.run_in_executor(None, initiate_login_step1, profile_dir)
            
            if login_res["status"] == "captcha_needed":
                img_path = login_res.get("image_path")
                USER_WAITING_CAPTCHA[update.effective_user.id] = True
                USER_UMS_INTENT[update.effective_user.id] = {
                    'action': 'timetable',
                    'args': args,
                    'chat_id': update.effective_chat.id
                }
                
                with open(img_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption="🔐 **UMS Captcha Required**\n\nreply with the code to continue to Timetable."
                    )
                return
            
            # If immediate success (rare) or error
            if login_res["status"] != "success":
                await retry_send_message(update, f"❌ Login failed: {login_res.get('message')}")
                return
                
            # If login succeeded without captcha, retry download
            await retry_send_message(update, "✅ Login restored. Retrying download...")
            result_retry = await loop.run_in_executor(None, get_ums_timetable_excel, requested_day)
            
            if result_retry["status"] == "success":
                excel_file = result_retry["file_path"]
            else:
                await retry_send_message(update, "❌ Failed to download timetable after login.")
                return
        else:
             await retry_send_message(update, f"❌ Error: {result.get('message')}")
             return

        if not excel_file or not os.path.exists(excel_file):
            await retry_send_message(update, "❌ File verification failed.")
            return

        await retry_send_message(update, "📊 Parsing timetable data...")
        
        
        # Parse Excel file
        df = pd.read_excel(excel_file, engine='openpyxl')
        
        # Extract schedule for requested day
        # Assuming the Excel has columns for each day of the week
        day_columns = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        if target_day == -1:
            # Full week view
            schedule_text = f"📅 **Full Week Timetable**\n\n"
            for idx, day_col in enumerate(day_columns):
                if day_col in df.columns:
                    schedule_text += f"**{day_col}:**\n"
                    day_schedule = df[day_col].dropna()
                    for item in day_schedule:
                        if str(item).strip():
                            schedule_text += f"  • {item}\n"
                    schedule_text += "\n"
        else:
            # Single day view
            day_col = day_columns[target_day]
            schedule_text = f"📅 **{day_name} Schedule**\n\n"
            
            if day_col in df.columns:
                day_schedule = df[day_col].dropna()
                
                if len(day_schedule) == 0:
                    schedule_text += "🎉 No classes scheduled!"
                else:
                    for idx, item in enumerate(day_schedule, 1):
                        if str(item).strip():
                            # Try to parse time and subject
                            item_str = str(item)
                            schedule_text += f"🕐 {item_str}\n"
            else:
                schedule_text += "❌ No data available for this day."
        
        # Clean up downloaded file
        try:
            os.remove(excel_file)
        except:
            pass
        
        # Delete status messages
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
        except:
            pass
        
        await retry_send_message(update, schedule_text, parse_mode='Markdown')
        
    except Exception as e:
        log(f"Timetable Error: {e}")
        await retry_send_message(update, f"❌ Error fetching timetable: {str(e)[:100]}")



async def submit_captcha_from_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, captcha_code: str, user_id: int):
    """Handle CAPTCHA code submission and resume pending intent"""
    
    # 1. Complete Login Step 2
    from ums_login_pyautogui import finalize_login_step2
    
    status_msg = await retry_send_message(update, "🔐 Verifying CAPTCHA...")
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, finalize_login_step2, captcha_code, CURRENT_CHROME_PROFILE)
        
        if result["status"] == "success":
            await retry_edit_message(status_msg, "✅ Login Successful!")
            
            # 2. Check for Pending Intent (e.g., Timetable)
            if user_id in USER_UMS_INTENT:
                intent = USER_UMS_INTENT.pop(user_id)
                action = intent.get('action')
                
                if action == 'timetable':
                    await retry_send_message(update, "🔄 Resuming Timetable Task...")
                    # Re-trigger timetable command
                    # We need to reconstruct args context
                    context.args = intent.get('args', [])
                    await timetable_command(update, context)
            
        else:
            await retry_edit_message(status_msg, f"❌ Login Failed: {result.get('message', 'Unknown error')}")
            
    except Exception as e:
        log(f"Captcha Submission Error: {e}")
        await retry_edit_message(status_msg, f"❌ Error: {e}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_authorized(user_id): return
    full_text = update.message.text.strip()
    words = [w.lower() for w in full_text.split()]
    
    # Comprehensive Registry
    cmd_map = {
        'play': media_command, 'pause': media_command, 'resume': media_command,
        'stop': media_command, 'next': media_command, 'skip': media_command,
        'prev': media_command, 'back': media_command, 'mute': media_command,
        'volume': volume_set_command, 'vol': volume_set_command,
        'brightness': brightness_command, 'bright': brightness_command,
        'battery': battery_command, 'lock': lock_command, 'unlock': unlock_command,
        'ss': screenshot_command, 'screenshot': screenshot_command,
        'click': click_command, 'type': type_command, 'shut': darkness_command,
        'darkness': darkness_command, 'undark': undark_command, 'wake': undark_command,
        'kill': kill_process_command, 'terminate': kill_process_command,
        'thermal': thermal_command, 'fan': thermal_command, 'rgb': rgb_command,
        'apps': applications_command, 'applications': applications_command
    }

    matched_fn = None
    # 1. CAPTCHA INTERCEPTION (Priority Protocol)
    if USER_WAITING_CAPTCHA.get(user_id, False):
        captcha_code = full_text.strip()
        USER_WAITING_CAPTCHA[user_id] = False
        status_msg = await retry_send_message(update, f"⌨️ Submitting code: {captcha_code}...")
        if user_id in USER_AUTH_DATA:
            USER_AUTH_DATA[user_id]['user_reply_msg_id'] = update.message.message_id
            USER_AUTH_DATA[user_id]['current_submission_status_msg_id'] = status_msg.message_id
            asyncio.create_task(submit_captcha_from_telegram(update, context, captcha_code, user_id))
        return

    # 1.1 PIN INTERCEPTION
    if USER_WAITING_PIN.get(user_id, False) and full_text.isdigit():
        USER_WAITING_PIN[user_id] = False
        context.args = [full_text]
        await unlock_command(update, context)
        return


    # 2. COMMAND ROUTING (Slash or Natural)
    clean_word = words[0].replace('/', '') if words else ""
    if clean_word in cmd_map:
        matched_fn = cmd_map[clean_word]
        # If it was a natural command (no slash), we might need to populate context.args
        if not full_text.startswith('/'):
            context.args = words[1:]
    
    if matched_fn:
        await matched_fn(update, context)
        return

    # 3. AI RESPONDER (Agentic Gemini Mark 4)
    # This handles natural language, chained commands, and complex intent.
    status_text = "✨ *Sir, processing your tactical request...*"
    status_msg = await update.message.reply_text(status_text, parse_mode='Markdown')
    ai_response = await ask_gemini(full_text, update, context)
    await status_msg.edit_text(ai_response, parse_mode='Markdown')

def main():
    check_singleton()
    print("[INFO] Bot Starting...")
    ensure_startup()
    
    # Global initialization
    global STEAM_GAMES
    STEAM_GAMES = {} 
    
    # Infinite Retry Loop covering App Build AND Polling
    while True:
        loop = None
        try:
            # Properly manage event loop for restart stability
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # 📡 CRITICAL: Wait for connection before trying to build the Telegram application
                loop.run_until_complete(wait_for_internet())
            except Exception as loop_e:
                log(f"Loop/Internet Sync Error: {loop_e}")
                time.sleep(2)
                continue
            
            print("[INFO] Building Application...")
            
            # OPTIMIZED TIMEOUT CONFIGURATION (Faster Recovery)
            from telegram.request import HTTPXRequest
            request = HTTPXRequest(
                connection_pool_size=16,
                connect_timeout=5.0,       # Fail fast on connect
                read_timeout=15.0,         # Detect dead socket in 15s
                write_timeout=10.0,
                pool_timeout=5.0,
                http_version="1.1" 
            )
            
            
            # Application building

            async def post_init(application: Application) -> None:
                global GREETING_SENT
                if ALLOWED_USER_IDS and not GREETING_SENT:
                    try:
                        import psutil
                        current_boot_time = psutil.boot_time()
                        boot_marker_file = "last_boot.txt"
                        signature_mp3 = "jarvis_signature.mp3"
                        
                        # Determine system state
                        with open(boot_marker_file, 'w') as f: f.write(str(current_boot_time))
                        
                        # 1. INSTANT TELEGRAM NOTIFICATION (0% Delay)
                        asyncio.create_task(application.bot.send_message(
                            chat_id=ALLOWED_USER_IDS[0], 
                            text="⚡ **At your Service , Sir !**",
                            parse_mode='Markdown'
                        ))

                        def deliver_cinematic(audio_path):
                            try:
                                threading.Thread(target=fade_other_sessions, args=(0.04, 1.0)).start()
                                vol_int = get_volume_interface()
                                orig_master = vol_int.GetMasterVolumeLevelScalar() if vol_int else 0.5
                                if vol_int: vol_int.SetMasterVolumeLevelScalar(1.0, None)
                                
                                abs_path = os.path.abspath(audio_path).replace("\\", "/")
                                play_script = f'Add-Type -AssemblyName presentationCore; $p = New-Object system.windows.media.mediaplayer; $p.open(\'{abs_path}\'); while ($p.NaturalDuration.HasTimeSpan -eq $false) {{ Start-Sleep -m 50 }}; $p.Play(); Start-Sleep -s ($p.NaturalDuration.TimeSpan.TotalSeconds + 1)'
                                subprocess.run(['powershell', '-c', play_script], creationflags=subprocess.CREATE_NO_WINDOW)
                                
                                if vol_int: vol_int.SetMasterVolumeLevelScalar(orig_master, None)
                                fade_other_sessions(1.0, 1.5)
                            except: pass

                        # 2. INSTANT PLAYBACK (0% Delay) if cached
                        if os.path.exists(signature_mp3):
                            log("Instant Signature Broadcast...")
                            asyncio.get_event_loop().run_in_executor(None, deliver_cinematic, signature_mp3)
                            GREETING_SENT = True
                        else:
                            # Generate once then cache for future 0-delay boots
                            try:
                                add_paths()
                                message = "At your service, Sir. All systems are green and ready for deployment."
                                VOICE, RATE, PITCH = "en-GB-RyanNeural", "+5%", "-6Hz"
                                temp_v = os.path.join(tempfile.gettempdir(), "v.mp3")
                                theme_mp3 = "back_in_black_intro.mp3"
                                
                                log("Generating Instant Cache for Mark 3...")
                                communicate = edge_tts.Communicate(message, VOICE, rate=RATE, pitch=PITCH)
                                await communicate.save(temp_v)
                                
                                merge_cmd = [
                                    'ffmpeg', '-y', '-i', theme_mp3, '-i', temp_v,
                                    '-filter_complex', '[1:a]adelay=3000|3000[v];[0:a]volume=0.4[m];[m][v]amix=inputs=2:duration=longest',
                                    '-f', 'mp3', signature_mp3
                                ]
                                subprocess.run(merge_cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                                
                                asyncio.get_event_loop().run_in_executor(None, deliver_cinematic, signature_mp3)
                                GREETING_SENT = True
                            except Exception as ge:
                                log(f"Cache gen failed: {ge}")
                                GREETING_SENT = True

                        # 3. Start Background Tasks (Track for cleanup)
                        ensure_hwinfo_running() # Ensure monitoring engine is online
                        global CURRENT_TASKS
                        h_task = asyncio.create_task(heartbeat_task(application))
                        p_task = asyncio.create_task(run_power_guard(application.bot))
                        CURRENT_TASKS.extend([h_task, p_task])
                        log("J.A.R.V.I.S. Core Tasks Initialized.")

                    except Exception as notify_e:
                        log(f"Notify Error: {notify_e}")

            # Create NEW Application instance every restart
            app = Application.builder().token(TELEGRAM_TOKEN).request(request).post_init(post_init).build()
            
            # Register Handlers
            app.add_handler(CommandHandler("start", start_command))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(CommandHandler("status", status_command))
            app.add_handler(CommandHandler(["execute", "run"], execute_command))
            app.add_handler(CommandHandler(["get", "download"], download_command))
            app.add_handler(CommandHandler(["ls", "dir"], list_files_command))
            app.add_handler(CommandHandler(["ss", "screenshot"], screenshot_command))
            app.add_handler(CommandHandler(["apps", "applications"], applications_command))
            app.add_handler(CommandHandler(["shut", "darkness"], darkness_command))
            app.add_handler(CommandHandler(["undark", "wake"], undark_command))
            app.add_handler(CommandHandler(["kill", "terminate", "stop"], kill_process_command))
            app.add_handler(CommandHandler("click", click_command))
            app.add_handler(CommandHandler("type", type_command))
            app.add_handler(CommandHandler("games", list_games_command))
            app.add_handler(CommandHandler("profiles", list_profiles_command))
            app.add_handler(CommandHandler("ums", stone_login_command if 'stone_login_command' in locals() else ums_login_command)) 
            app.add_handler(CommandHandler("battery", battery_command))
            app.add_handler(CommandHandler("lock", lock_command))
            app.add_handler(CommandHandler("unlock", unlock_command))
            app.add_handler(CommandHandler(["brightness", "bright"], brightness_command))
            app.add_handler(CommandHandler(["volume", "vol"], volume_set_command))
            app.add_handler(CommandHandler(["thermal", "fan"], thermal_command))
            app.add_handler(CommandHandler(["light", "rgb"], rgb_command))
            app.add_handler(CommandHandler("taskbar", taskbar_command))
            app.add_handler(CommandHandler(["timetable", "schedule", "tt"], timetable_command))
            app.add_handler(CommandHandler(["sec_enroll", "enroll"], lambda u, c: None)) # Disabled
            app.add_handler(CommandHandler(["sec_test", "scan"], lambda u, c: None)) # Disabled
            app.add_handler(CallbackQueryHandler(emergency_fan_callback, pattern="emergency_cooling"))
            app.add_handler(CommandHandler(["play", "pause", "next", "skip", "prev", "back", "volup", "voldown", "mute", "spotify"], media_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
            
            # Handler Registration
            print("[INFO] Bot Handlers Configured.")

            print("[INFO] Bot Ready! Polling...")
            app.run_polling(
                poll_interval=1.0,           
                timeout=10,
                drop_pending_updates=False,
                allowed_updates=Update.ALL_TYPES
            )
            
        except KeyboardInterrupt:
            print("[INFO] Shutting down...")
            break
        except Exception as e:
            log(f"[ERROR] Main Loop Crashed: {e}")
            
            # CLEANUP: Cancel zombie tasks
            global CURRENT_TASKS
            for task in CURRENT_TASKS:
                if not task.done():
                    task.cancel()
            CURRENT_TASKS.clear()
            
            print(f"[RESTART] Restarting in 2s... (Error: {str(e)[:100]})")
            time.sleep(2) 

if __name__ == "__main__":
    main()
