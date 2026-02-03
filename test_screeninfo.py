from screeninfo import get_monitors
import time

print("--- Screen Info Detection ---")
while True:
    monitors = get_monitors()
    print(f"Current monitors: {len(monitors)}")
    for m in monitors:
        print(f" - {m.name}: {m.width}x{m.height} (Main: {m.is_primary})")
    print("Close lid now...")
    time.sleep(2)
