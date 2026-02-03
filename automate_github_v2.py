import time
import pyautogui
import os
import mss
import mss.tools

# 1. Launch Chrome
print("Launching Chrome...")
os.system('start chrome --profile-directory="Profile 2" "https://github.com/new"')
time.sleep(8) # Long wait for load

# 2. Focus and Type
print("Attempting to focus and type...")
pyautogui.write("Mark4-Bot")
time.sleep(2)
pyautogui.press("enter")
print("Creation Enter sent.")

# 3. Wait for redirect
time.sleep(5)

# 4. Final Verification
with mss.mss() as sct:
    sct.tools.to_png(sct.grab(sct.monitors[1]).rgb, sct.grab(sct.monitors[1]).size, output="github_final_attempt.png")
    print("Verification screenshot saved.")
