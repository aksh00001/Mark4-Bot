import mmap
import struct

def find_data():
    try:
        shmem = mmap.mmap(-1, 0x200000, tagname="Global\\HWiNFO_SENS_SM2", access=mmap.ACCESS_READ)
        data = shmem.read(0x200000)
        
        # Check header
        print(f"Signature: {data[:4]}")
        
        # In HWiNFO 7.x/8.x with Version 2:
        # Header size is usually 132 bytes or 256 bytes
        # Let's find common offsets for NumSensors
        # Standard Version 2 Layout:
        # 0: Signature (4)
        # 4: Version (4)
        # 8: Revision (4)
        # 12: PollTime (8)
        # 20: OffsetNumSensors (4)
        # 24: SizeSensorElement (4)
        # 28: OffsetNumReadings (4)
        # 32: SizeReadingElement (4)
        
        # Let's unpack with this assumption
        off_sens = struct.unpack('<I', data[20:24])[0]
        sz_sens = struct.unpack('<I', data[24:28])[0]
        off_read = struct.unpack('<I', data[28:32])[0]
        sz_read = struct.unpack('<I', data[32:36])[0]
        
        print(f"Offsets: Sens={off_sens}, szSens={sz_sens}, Read={off_read}, szRead={sz_read}")
        
        if off_read < 0x200000 and sz_read > 0:
            # Let's look at the first reading
            shmem.seek(off_read)
            chunk = shmem.read(sz_read)
            label = chunk[12:12+128].split(b'\x00')[0].decode('utf-8', 'ignore').strip()
            print(f"First Reading Label: {label}")
        
        shmem.close()
    except Exception as e:
        print(f"Error: {e}")

find_data()
