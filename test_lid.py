import wmi
try:
    c = wmi.WMI(namespace="root\\wmi")
    lid_state = c.MSLidSwitchState()
    print(f"Lid state objects found: {len(lid_state)}")
    for s in lid_state:
        print(f"Opened: {s.Opened}")
except Exception as e:
    print(f"Error: {e}")
