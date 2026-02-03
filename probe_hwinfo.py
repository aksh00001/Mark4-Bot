import mmap
import struct

def try_read(name):
    try:
        # Open existing mapping
        shmem = mmap.mmap(-1, 4096, tagname=name, access=mmap.ACCESS_READ)
        sig = shmem.read(4)
        shmem.close()
        return sig
    except Exception as e:
        return str(e)

print(f"v1 (Global): {try_read('Global\\HWiNFO_SENS_SM')}")
print(f"v2 (Global): {try_read('Global\\HWiNFO_SENS_SM2')}")
print(f"v1 (Local): {try_read('Local\\HWiNFO_SENS_SM')}")
print(f"v2 (Local): {try_read('Local\\HWiNFO_SENS_SM2')}")
