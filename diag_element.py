import mmap
import struct

def diag():
    shmem = mmap.mmap(-1, 0x200000, tagname="Global\\HWiNFO_SENS_SM2", access=mmap.ACCESS_READ)
    data = shmem.read(0x200000)
    
    # Target: GPU Fan (found at 0x42998)
    start = 0x42998 - 12
    print(f"Inspecting 'GPU Fan' element starting at {hex(start)}")
    
    chunk = data[start:start+400]
    for i in range(0, len(chunk) - 8, 4):
        try:
            val = struct.unpack('<d', chunk[i:i+8])[0]
            if val > 10: 
                print(f"Offset {i}: {val:.2f}")
        except: pass
    
    shmem.close()

diag()
