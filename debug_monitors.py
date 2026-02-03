import mss
import time
import os

with mss.mss() as sct:
    last_count = len(sct.monitors)
    print(f"Initial monitor count: {last_count}")
    print("Watching for changes... Close and open the lid now.")
    
    start_time = time.time()
    while time.time() - start_time < 30: # Watch for 30 seconds
        current_count = len(sct.monitors)
        if current_count != last_count:
            print(f"CHANGE DETECTED! New count: {current_count}")
            last_count = current_count
        time.sleep(0.5)
    print("Test finished.")
