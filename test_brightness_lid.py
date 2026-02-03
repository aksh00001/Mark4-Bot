import wmi
import time

c = wmi.WMI(namespace="root\\wmi")
print("--- Brightness Detection Test ---")
print("Close the lid for 5 seconds now...")

while True:
    try:
        brightness_list = c.WmiMonitorBrightness()
        count = len(brightness_list)
        print(f"Active Brightness Controllers: {count}", end="\r")
        if count == 0:
            print("\nLID CLOSED DETECTED (No Brightness Controller)")
    except Exception as e:
        print(f"\nError or Closed: {e}")
    time.sleep(1)
