import mmap
import os

def scan_shmem():
    name = "Global\\HWiNFO_SENS_SM2"
    try:
        # Access=READ to avoid creating it
        shmem = mmap.mmap(-1, 0x200000, tagname=name, access=mmap.ACCESS_READ)
        data = shmem.read(1024 * 10) # Read 10KB
        
        sig = data[:4]
        print(f"Signature at 0x00: {sig}")
        
        # Search for HWiS
        pos = data.find(b'HWiS')
        if pos != -1:
            print(f"Found HWiS at: {hex(pos)}")
        else:
            print("HWiS not found in first 10KB")
            
        # Search for common strings
        for s in [b"CPU", b"GPU", b"Fan", b"Temp"]:
            found = data.find(s)
            if found != -1:
                print(f"Found '{s.decode()}' at: {hex(found)}")
                
        shmem.close()
    except Exception as e:
        print(f"Error accessing {name}: {e}")

scan_shmem()
