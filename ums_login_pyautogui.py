"""
UMS Login Automation - 29 Jan 18:16 Version (Restored)
"""

import time
import subprocess
import pyautogui
import os
from PIL import Image, ImageGrab

# Disable fail-safe
pyautogui.FAILSAFE = False

from dotenv import load_dotenv
load_dotenv()

# LPU UMS Credentials
UMS_USERNAME = os.getenv("UMS_USERNAME")
UMS_PASSWORD = os.getenv("UMS_PASSWORD")

CAPTCHA_IMG_PATH = r"C:\Users\akshu\OneDrive\Desktop\TESTapp\ums_captcha_temp.png"

def navigate_to_url(url):
    try:
        pyautogui.hotkey('ctrl', 'l'); time.sleep(0.5)
        pyautogui.write(url, interval=0.03)
        pyautogui.press('enter')
    except: pass

def run_javascript(js_code):
    try:
        import tkinter as tk
        payload = js_code.replace("javascript:", "")
        r = tk.Tk(); r.withdraw(); r.clipboard_clear(); r.clipboard_append(payload); r.update(); r.destroy()
        
        pyautogui.hotkey('ctrl', 'l'); time.sleep(0.5) # Increased from 0.3
        pyautogui.write("javascript:", interval=0.04) # Slowed down from 0.01
        pyautogui.hotkey('ctrl', 'v'); time.sleep(0.2)
        pyautogui.press('enter')
        time.sleep(0.8) # Increased from 0.5
    except Exception as e:
        print(f"JS Error: {e}")

def ensure_chrome_focus():
    try:
        import win32gui, win32con
        def callback(hwnd, extra):
            if "Google Chrome" in win32gui.GetWindowText(hwnd):
                win32gui.SetForegroundWindow(hwnd)
        win32gui.EnumWindows(callback, None)
        time.sleep(0.3)
    except: pass

def initiate_login_step1(chrome_profile: str = "Default") -> dict:
    UMS_URL = "https://ums.lpu.in/lpuums/LoginNew.aspx"
    try:
        # Reverted to basic Chrome launch
        cmd = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", f"--profile-directory={chrome_profile}", UMS_URL]
        subprocess.Popen(cmd)
        time.sleep(6) # Original wait
        
        for _ in range(2): pyautogui.press('esc'); time.sleep(0.2)
        
        # Inject user
        js_user = f"var u=document.getElementById('txtU'); if(u){{u.value='{UMS_USERNAME}'; u.dispatchEvent(new Event('change'));}} void(0);"
        run_javascript(js_user)
        time.sleep(0.5)
        
        # Inject pass
        js_pass = f"var p=document.querySelector('input[type=\"password\"]'); if(p){{p.value='{UMS_PASSWORD}'; p.dispatchEvent(new Event('change'));}} void(0);"
        run_javascript(js_pass)
        time.sleep(0.5)
        
        # Capture captcha
        screenshot = ImageGrab.grab()
        w, h = screenshot.size
        img = screenshot.crop((int(w * 0.40), int(h * 0.40), int(w * 0.70), int(h * 0.75))).convert('L')
        img.save(CAPTCHA_IMG_PATH)
        return {"status": "captcha_needed", "image_path": CAPTCHA_IMG_PATH}
    except Exception as e: return {"status": "error", "message": str(e)}

def finalize_login_step2(code: str) -> dict:
    """Strictly types the provided code and submits login. NO background movement until called."""
    try:
        print(f"📥 Received Captcha Code: {code}. Finalizing login...")
        ensure_chrome_focus()
        
        # Focus the captcha box
        js_focus = "var c=document.getElementById('CaptchaCodeTextBox'); if(c){c.focus(); c.select();} void(0);"
        run_javascript(js_focus)
        time.sleep(0.6)
        
        # Type and Enter
        pyautogui.write(code, interval=0.1) 
        time.sleep(0.4)
        pyautogui.press('enter')
        
        # Wait for the post-login page to load
        print("⏳ Waiting for UMS to process login (10s)...")
        time.sleep(10)
        
        return {"status": "success", "message": "Login complete!"}
    except Exception as e: return {"status": "error", "message": str(e)}

def clear_ums_popups():
    try:
        pyautogui.press('esc'); time.sleep(0.2)
        js_close = "var b=Array.from(document.querySelectorAll('input,button,a')).find(x=>(x.innerText||x.value||'').toLowerCase().includes('later')); if(b)b.click();void(0);"
        run_javascript(js_close)
        return {"status": "success"}
    except: return {"status": "error"}

def get_ums_attendance():
    URL = "https://ums.lpu.in/lpuums/Reports/rptCourseWiseStudentAttendance.aspx"
    try:
        navigate_to_url(URL)
        print("⏳ Waiting for attendance page (8s)...")
        time.sleep(8) 
        clear_ums_popups()
        
        # 1. Click 'Show' button using simple JS (standard UI interaction)
        js_show = "if(document.getElementById('ctl00_ContentPlaceHolder1_btnShow'))document.getElementById('ctl00_ContentPlaceHolder1_btnShow').click();void(0);"
        run_javascript(js_show)
        
        print("⏳ Waiting for report to render (10s)...")
        time.sleep(10)

        # 2. Strict Ctrl+A Method (No more JS extraction)
        print("⌨️ Grabbing all text via Select-All...")
        ensure_chrome_focus()
        time.sleep(0.5)
        
        # Click report area center to ensure focus
        pyautogui.click(x=pyautogui.size().width//2, y=pyautogui.size().height//2)
        time.sleep(0.5)
        
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.4)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(1.0) # Wait for clipboard
        
        import tkinter as tk
        import re
        r = tk.Tk(); r.withdraw()
        try: text = r.clipboard_get()
        except: text = ""
        r.destroy()
        
        if not text or len(text) < 50:
             return {"status": "error", "message": "Select-All failed. Clipboard empty or too short."}
        
        print(f"📄 Captured {len(text)} characters. Parsing...")
        
        extracted = ""
        normalized = re.sub(r'\s+', ' ', text).lower()
        
        # 1. Flexible Aggregate Search
        # Pattern 1: Spaced 'A g g r e g a t e'
        agg_spaced = re.search(r"a\s*g\s*g\s*r\s*e\s*g\s*a\s*t\s*e\D*(\d+)", normalized)
        # Pattern 2: Normal 'Aggregate' or 'Total'
        agg_normal = re.search(r"(?:aggregate|total)\s*attendance\D*(\d+)", normalized)
        
        if agg_spaced: extracted += f"AGGREGATE: {agg_spaced.group(1)}%\n"
        elif agg_normal: extracted += f"AGGREGATE: {agg_normal.group(1)}%\n"

        # 2. Course Parsing (Look for course codes like CSES003)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            # If line starts with a course code (uppercase letters followed by digits)
            if re.search(r"^[A-Z]{2,}\d{2,}", line):
                # Look for the last number in the next 15 lines (vertical layout)
                found_num = None
                for j in range(i + 1, min(i + 15, len(lines))):
                    if re.match(r"^\d{1,3}$", lines[j]):
                        val = int(lines[j])
                        if 0 <= val <= 100: found_num = lines[j]
                
                if found_num:
                    course_name = line[:40]
                    extracted += f"COURSE: {course_name} -> {found_num}%\n"

        if extracted:
            return {"status": "success", "data": extracted}
        
        # DEBUG: If we can't find data, send a snippet of what we caught
        snippet = text[:500].replace('\n', ' ')
        return {"status": "error", "message": f"Patterns not found. Captured summary: {snippet}"}
    except Exception as e: return {"status": "error", "message": str(e)}

def get_ums_timetable(day_to_find):
    URL = "https://ums.lpu.in/lpuums/frmMyCurrentTimeTable.aspx"
    
    # Map days to column indices (0: Time, 1: Mon, 2: Tue, 3: Wed, 4: Thu, 5: Fri, 6: Sat, 7: Sun)
    days_map = {
        "Monday": 1, "Tuesday": 2, "Wednesday": 3, 
        "Thursday": 4, "Friday": 5, "Saturday": 6, "Sunday": 7
    }
    
    target_day = day_to_find.strip().title()
    day_idx = days_map.get(target_day, 1)
    
    try:
        navigate_to_url(URL)
        print(f"⏳ Navigating to Timetable... Target: {target_day}")
        time.sleep(8)
        clear_ums_popups()
        
        # User Recommended Logic: Target specific column
        js_extract = f"""
        (function(){{
            var dayIndex = {day_idx};
            var rows = document.querySelectorAll('table tr');
            var classes = [];
            
            rows.forEach(function(row) {{
                var cells = row.cells;
                if (cells && cells.length > dayIndex) {{
                    var timeCell = cells[0].innerText.trim();
                    var classCell = cells[dayIndex].innerText.trim();
                    
                    if (classCell && classCell.length > 3) {{
                        var cleanInfo = classCell.split('\\n').join(' ').replace(/\s+/g, ' ');
                        classes.push(timeCell + " : " + cleanInfo);
                    }}
                }}
            }});
            
            var ta = document.createElement('textarea');
            ta.style.position='fixed'; ta.style.top='0'; ta.style.left='0'; ta.style.width='1px';
            ta.value = 'TT_START' + classes.join('###') + 'TT_END';
            document.body.appendChild(ta); ta.select(); document.execCommand('copy');
            document.body.removeChild(ta);
        }})();void(0);
        """
        run_javascript(js_extract)
        time.sleep(1.5)
        
        import tkinter as tk
        r = tk.Tk(); r.withdraw()
        try: text = r.clipboard_get()
        except: text = ""
        r.destroy()
        
        if "TT_START" in text:
            try:
                raw_part = text.split("TT_START")[1].split("TT_END")[0].strip()
            except:
                raw_part = ""
                
            if not raw_part:
                return {"status": "success", "data": "No classes scheduled for today! 🎉"}
            
            items = [x.strip() for x in raw_part.split("###") if x.strip()]
            if not items:
                return {"status": "success", "data": "No classes scheduled for today! 🎉"}

            # Build bulleted list
            formatted_list = []
            for item in items:
                if " : " in item:
                    try:
                        t, info = item.split(" : ", 1)
                        formatted_list.append(f"**{t.strip()}**: {info.strip()}")
                    except:
                        formatted_list.append(item)
                else:
                    formatted_list.append(item)
            
            # Combine into final message with bullets
            final_data = "· " + "\n· ".join(formatted_list)
            return {"status": "success", "data": final_data}
            
        return {"status": "error", "message": "Could not access timetable grid."}
    except Exception as e: return {"status": "error", "message": f"Timetable Error: {str(e)}"}

def get_ums_messages():
    URL = "https://ums.lpu.in/lpuums/frmStudentsMyMessages.aspx"
    try:
        navigate_to_url(URL)
        time.sleep(6)
        clear_ums_popups()
        return {"status": "success", "data": "Messages extracted"}
    except: return {"status": "error"}

def get_ums_timetable_excel(day_str="today"):
    """
    Robust Timetable Extraction via Excel Download
    1. Navigate to Timetable Page
    2. Click 'Get Excel'
    3. Wait for download
    4. Return file path
    """
    URL = "https://ums.lpu.in/lpuums/frmMyCurrentTimeTable.aspx"
    try:
        navigate_to_url(URL)
        print("⏳ Navigating to Timetable page (8s)...")
        time.sleep(8)
        clear_ums_popups()
        
        # Click 'Get Excel' button via JS
        print("🖱️ Triggering Excel Download...")
        js_download = "if(document.getElementById('btnExcel'))document.getElementById('btnExcel').click();void(0);"
        run_javascript(js_download)
        
        # Wait for download to complete
        print("⏳ Waiting for download (10s)...")
        time.sleep(10)
        
        # Find the most recent Excel file in Downloads
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        excel_files = [f for f in os.listdir(download_path) if f.endswith(('.xls', '.xlsx'))]
        if excel_files:
            # Sort by modification time (newest first)
            excel_files.sort(key=lambda x: os.path.getmtime(os.path.join(download_path, x)), reverse=True)
            latest_file = os.path.join(download_path, excel_files[0])
            
            # Verify this file is recent (within last 1 minute)
            if (time.time() - os.path.getmtime(latest_file)) < 60:
                return {"status": "success", "file_path": latest_file}
        
        return {"status": "error", "message": "Download failed or file not found."}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
