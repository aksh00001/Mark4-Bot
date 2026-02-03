
import ctypes
import time
import sys

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("dwTime", ctypes.c_uint32)]

def get_idle_duration():
    lastInputInfo = LASTINPUTINFO()
    lastInputInfo.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo)):
        millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
        return millis / 1000.0
    return 0

print("Monitoring Idle Time (10s test)... Don't touch input devices!")
for i in range(10):
    idle = get_idle_duration()
    sys.stdout.write(f"\rIdle Time: {idle:.2f} seconds")
    sys.stdout.flush()
    time.sleep(1)

print("\n\nNow move the mouse!")
time.sleep(2)
idle = get_idle_duration()
print(f"Idle Time after move: {idle:.2f} seconds")
