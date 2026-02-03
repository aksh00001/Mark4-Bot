somethinimport cv2
import numpy as np
import time

cap = cv2.VideoCapture(0)
print("--- Webcam Darkness Tracker ---")
print("Close the lid now. I'll watch the brightness...")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Webcam disconnected or blocked!")
            break
        
        # Convert to grayscale to get brightness
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = np.mean(gray)
        
        print(f"Average Brightness: {avg_brightness:.2f}", end="\r")
        
        if avg_brightness < 5.0:
            print("\nLID CLOSED (Darkness detected)")
        elif avg_brightness > 20.0:
            # We don't print "Opened" every time to avoid spam
            pass
            
        time.sleep(1)
finally:
    cap.release()
