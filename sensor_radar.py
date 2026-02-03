import mmap
import ctypes
import struct

def scan_for_jarvis():
    print("🛰️ JARVIS SENSOR RADAR STARTING...")
    names = ["Global\\HWiNFO_SENS_SM2", "Local\\HWiNFO_SENS_SM2", "HWiNFO_SENS_SM2"]
    
    for name in names:
        try:
            # Note: mmap.mmap(-1, ...) with tagname will open existing OR create.
            # We want to check if it's ALREADY there.
            shmem = mmap.mmap(-1, 0x10000, tagname=name, access=mmap.ACCESS_READ)
            data = shmem.read(0x1000)
            
            non_zero = sum(1 for b in data if b != 0)
            print(f"Checking {name}...")
            print(f" - Data Density: {non_zero} bytes populated")
            
            sig_pos = data.find(b'HWiS')
            if sig_pos != -1:
                print(f" 🎯 TARGET ACQUIRED: 'HWiS' signature found at offset {hex(sig_pos)} in {name}")
                # Analyze version
                shmem.seek(sig_pos + 4)
                ver = struct.unpack('<I', shmem.read(4))[0]
                print(f" - Sensor Protocol Version: {ver}")
            
            shmem.close()
        except Exception as e:
            print(f" - {name} unreachable: {e}")

if __name__ == "__main__":
    scan_for_jarvis()
