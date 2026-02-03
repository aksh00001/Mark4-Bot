import pyautogui
import time
import tkinter as tk

pyautogui.FAILSAFE = False

def get_whatsapp_third_msg():
    try:
        w = pyautogui.getWindowsWithTitle('WhatsApp')[0]
        w.activate()
        time.sleep(1)
        
        # Click third chat position
        pyautogui.click(w.left + 250, w.top + 530) 
        time.sleep(1)
        
        # Click message area to focus
        pyautogui.click(w.left + 600, w.top + 700)
        time.sleep(0.5)
        
        # Copy last message (Right click + Copy is safer but complex, 
        # let's try just getting all and splitting or specific shortcut)
        # In WhatsApp Desktop, Ctrl+A Ctrl+C grabs the conversation history.
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.5)
        
        r = tk.Tk()
        r.withdraw()
        text = r.clipboard_get()
        r.destroy()
        
        print(f"DEBUG_TEXT_START\n{text}\nDEBUG_TEXT_END")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_whatsapp_third_msg()
