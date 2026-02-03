import mmap
import struct

def brute_scan():
    try:
        shmem = mmap.mmap(-1, 0x200000, tagname="Global\\HWiNFO_SENS_SM2", access=mmap.ACCESS_READ)
        data = shmem.read(0x200000)
        
        targets = [b"CPU Package", b"GPU Temperature", b"CPU Fan", b"GPU Fan"]
        
        print("🔍 SENSOR BRUTE-SCAN INITIATED...")
        for t in targets:
            pos = data.find(t)
            if pos != -1:
                print(f"🎯 FOUND '{t.decode()}' at offset {hex(pos)}")
                # In Readings, Label is usually at offset 12 within the element.
                # So the start of the element is pos - 12.
                elem_start = pos - 12
                # Value (double) is usually at elem_start + 156 or nearby.
                # Let's check if there's a double nearby.
                val_data = data[elem_start+156 : elem_start+164]
                if len(val_data) == 8:
                    val = struct.unpack('<d', val_data)[0]
                    print(f"   - Potential Value: {val:.2f}")
            else:
                # Try lower case search
                pos = data.lower().find(t.lower())
                if pos != -1:
                    print(f"🎯 FOUND '{t.decode()}' (via lower) at offset {hex(pos)}")
        
        shmem.close()
    except Exception as e:
        print(f"Error: {e}")

brute_scan()
