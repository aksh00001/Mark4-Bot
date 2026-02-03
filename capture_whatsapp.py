import pyautogui
import time

pyautogui.FAILSAFE = False

def capture_third_chat():
    try:
        w = pyautogui.getWindowsWithTitle('WhatsApp')[0]
        w.activate()
        time.sleep(1)
        # Click 3rd chat
        pyautogui.click(w.left + 250, w.top + 530)
        time.sleep(2)
        # Take screenshot of the message area
        pyautogui.screenshot('whatsapp_last_msg.png')
        print("Screenshot taken.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    capture_third_chat()
