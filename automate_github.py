import time
import pyautogui
import mss
import mss.tools

try:
    # 1. Find and activate Chrome/GitHub
    all_windows = pyautogui.getAllWindows()
    github_windows = [w for w in all_windows if "GitHub" in w.title]
    
    if github_windows:
        win = github_windows[0]
        win.activate()
        time.sleep(1)
        
        # 2. Type the repo name
        pyautogui.write("Mark4-Bot")
        time.sleep(2) # Wait for availability check
        
        # 3. Submit (Usually Enter works, but let's be thorough with Tabs)
        # On GitHub /new, Name is focused. Tab x 10 or so gets to Create.
        # Actually Enter usually works if name is valid.
        pyautogui.press("enter")
        print("Repo creation signal sent.")
    else:
        print("GitHub window not found.")

    # 4. Final Verification Screenshot
    time.sleep(5)
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        mss.tools.to_png(sct_img.rgb, sct_img.size, output="github_final_check.png")
        print("Screenshot saved to github_final_check.png")

except Exception as e:
    print(f"Error: {e}")
