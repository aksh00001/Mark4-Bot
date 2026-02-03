import pyautogui
import time

print("--- Screen Resolution Tracker ---")
last_size = pyautogui.size()
print(f"Initial Resolution: {last_size}")

while True:
    current_size = pyautogui.size()
    if current_size != last_size:
        print(f"RESOLUTION CHANGE DETECTED: {current_size}")
        last_size = current_size
    time.sleep(0.5)
