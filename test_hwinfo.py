import mmap
import ctypes
import struct

class HWINFO_SHM_HEADER(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("dwSignature", ctypes.c_uint32), ("dwVersion", ctypes.c_uint32), ("dwRevision", ctypes.c_uint32),
        ("poll_time", ctypes.c_uint64), ("dwOffsetSensors", ctypes.c_uint32), ("dwSizeSensor", ctypes.c_uint32),
        ("dwNumSensors", ctypes.c_uint32), ("dwOffsetReadings", ctypes.c_uint32), ("dwSizeReading", ctypes.c_uint32),
        ("dwNumReadings", ctypes.c_uint32),
    ]

try:
    shm = mmap.mmap(-1, 65536, "Global\\HWiNFO_SENS_SM2", mmap.ACCESS_READ)
    header = HWINFO_SHM_HEADER.from_buffer_copy(shm[:ctypes.sizeof(HWINFO_SHM_HEADER)])
    
    for i in range(min(header.dwNumReadings, 20)):
        offset = header.dwOffsetReadings + (i * header.dwSizeReading)
        label = shm[offset+8 : offset+136].decode('ascii', errors='ignore').split('\0')[0]
        value = struct.unpack_from('d', shm, offset+280)[0]
        unit = shm[offset+264 : offset+280].decode('ascii', errors='ignore').split('\0')[0]
        print(f"{label}: {value} {unit}")
    shm.close()
except Exception as e:
    print(f"FAILED: {e}")
